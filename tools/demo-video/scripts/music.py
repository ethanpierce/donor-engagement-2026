"""Background music: generate a bed from the plan prompt, then listen-check candidates.

  python3 music.py PLAN.json generate OUT.mp3          # fal model from plan "music" (default fal-ai/elevenlabs/music), needs FAL_KEY
  python3 music.py analyse FILE [FILE ...]             # loudness, 10 s level/spectrum table, start/end seam
  python3 music.py listen FILE                         # Gemini listening check: vocals, mood, build-ups (GEMINI_API_KEY)
  python3 music.py bed FILE OUT.wav SECONDS [--start S] [--end S] [--bpm N]   # trimmed bed, looped to SECONDS

Pick the candidate with steady level (small rms spread), low 2-5 kHz presence (leaves room for the voice), no vocals.
The editor builds the bed itself from the plan (music_start, music_end, music_bpm), sets the level and ducks it:
- music_start skips a near-silent opening (see the first rows of `analyse`; the Tidepath bed starts at 2.3 s),
- music_end cuts before a fade-out ending,
- when the video is longer than the bed, the bed repeats with a 6 s crossfade; with music_bpm the repeat point
  moves by whole bars, so the crossfade keeps the beat.
"""
import json, math, os, subprocess, sys, time, urllib.request
import numpy as np

def generate(plan_path, out):
    import fal_client
    m = json.load(open(plan_path))['music']; model = m.get('model', 'fal-ai/elevenlabs/music')
    if 'elevenlabs' in model:
        args = dict(prompt=m['prompt'], music_length_ms=m.get('length_ms', 240000), force_instrumental=True, output_format='mp3_44100_192')
    else:   # e.g. fal-ai/stable-audio-25/text-to-audio
        args = dict(prompt=m['prompt'], seconds_total=m.get('length_ms', 190000) // 1000)
    r = fal_client.subscribe(model, arguments=args)
    urllib.request.urlretrieve((r.get('audio') or r.get('audio_file'))['url'], out); print('saved', out)

def analyse(f, sr=22050):
    x = np.frombuffer(subprocess.run(['ffmpeg', '-v', 'error', '-i', f, '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-'], capture_output=True).stdout, np.float32)
    e = subprocess.run(['ffmpeg', '-nostats', '-i', f, '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True).stderr.split('Summary')[-1]
    print(f, f'{len(x) / sr:.1f}s', ' '.join(l.strip() for l in e.splitlines() if l.strip().startswith(('I:', 'LRA:', 'Peak:'))))
    rows = []
    for i in range(0, len(x) - sr * 10 + 1, sr * 10):
        s = x[i:i + sr * 10]; S = np.abs(np.fft.rfft(s * np.hanning(len(s)))) ** 2; fr = np.fft.rfftfreq(len(s), 1 / sr); tot = S.sum() + 1e-12
        band = lambda a, b: 10 * np.log10(S[(fr >= a) & (fr < b)].sum() / tot + 1e-12)
        rows.append((i // sr, 20 * np.log10(np.sqrt((s ** 2).mean()) + 1e-9), (S * fr).sum() / tot, band(2000, 5000)))
    print('  opening rms_dB per 0.5 s:', ' '.join(f'{20 * np.log10(np.sqrt((x[i:i + sr // 2] ** 2).mean()) + 1e-9):.0f}' for i in range(0, sr * 5, sr // 2)))
    a = np.array(rows)
    print('  t  rms_dB centroid presence_2-5k_dB'); [print('  %3d %6.1f %7.0f %6.1f' % r) for r in rows]
    print(f'  rms mean {a[:, 1].mean():.1f} sd {a[:, 1].std():.1f} | presence mean {a[:, 3].mean():.1f}')

def dur(f): return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], capture_output=True, text=True).stdout)

def bed(src, out, need, start=0.0, end=None, bpm=None, beats_per_bar=4, xf=6.0, loop_from=18.0):
    """Write a 48 kHz stereo bed of at least `need` seconds from src[start:end]. When that is too short, append
    src[b0:end] copies with an xf-second crossfade. b0 >= loop_from; with bpm, end - xf - b0 is a whole number of bars."""
    L = dur(src); end = min(end or L, L); segs = [(start, end)]; total = end - start
    if total < need:
        j = end - xf; b0 = max(start, loop_from)
        if bpm: bar = beats_per_bar * 60.0 / bpm; b0 = j - math.floor((j - b0) / bar) * bar
        if b0 >= j - 1: raise SystemExit(f'music bed too short to loop: {src}')
        while total < need: segs.append((b0, end)); total += end - b0 - xf
    fc = [f'[0:a]aresample=48000,aformat=channel_layouts=stereo,asplit={len(segs)}' + ''.join(f'[s{i}]' for i in range(len(segs))) if len(segs) > 1
          else '[0:a]aresample=48000,aformat=channel_layouts=stereo[s0]']
    fc += [f'[s{i}]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS[t{i}]' for i, (a, b) in enumerate(segs)]
    prev = 't0'
    for i in range(1, len(segs)): fc.append(f'[{prev}][t{i}]acrossfade=d={xf}:c1=tri:c2=tri[x{i}]'); prev = f'x{i}'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-filter_complex', ';'.join(fc), '-map', f'[{prev}]', '-ar', '48000', '-c:a', 'pcm_s24le', out], check=True)
    return dict(segments=segs, length=round(total, 3))

def listen(f):
    from google import genai
    c = genai.Client(); up = c.files.upload(file=f)
    while up.state.name == 'PROCESSING': time.sleep(2); up = c.files.get(name=up.name)
    print(c.models.generate_content(model='gemini-2.5-pro', contents=[up,
        'Listen to the whole track. 1) Any vocals, spoken or sung words, humming, choir or vocal chops? Give timestamps and transcribe. '
        '2) Instruments and mood: hopeful or melancholic, warm and soft? 3) Abrupt changes, build-ups, drops or loud moments with timestamps. '
        '4) Does it suit a soft bed under a voiceover? Be concise.']).text)

if __name__ == '__main__':
    c = sys.argv[1]
    if c == 'analyse': [analyse(f) for f in sys.argv[2:]]
    elif c == 'listen': listen(sys.argv[2])
    elif c == 'bed':
        a = sys.argv[2:]; opt = lambda k: float(a[a.index(k) + 1]) if k in a else None
        print(bed(a[0], a[1], float(a[2]), opt('--start') or 0.0, opt('--end'), opt('--bpm')))
    elif sys.argv[2] == 'generate': generate(sys.argv[1], sys.argv[3])
    else: raise SystemExit(__doc__)
