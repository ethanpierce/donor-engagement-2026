"""Verify a finished video folder (main mp4 + clips/). Exit 1 on any failed check.

  python3 verify.py OUT_DIR [--sheet] [--stt]

Checks per mp4: 1920x1080 H.264 30 fps, AAC audio, mov_text subtitles, integrated loudness within 1 LU of -16 LUFS
(env LUFS_TARGET), true peak <= -1 dBTP,
SRT cues >= 1.5 s, no overlap, last cue ends before the video. --sheet writes contact-sheet.png (1 frame / 4 s) and
five full-size frames into OUT_DIR/../check/. --stt asks Gemini to transcribe the main mix and judge the music balance.
"""
import glob, json, os, re, subprocess, sys, time

def sh(*a): return subprocess.run(a, capture_output=True, text=True)
def tsec(s): h, m, x = s.split(':'); sec, ms = x.split(','); return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000

def check(f):
    j = json.loads(sh('ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', f).stdout)
    st = {s['codec_type']: s for s in j['streams']}; v, a, s = st.get('video', {}), st.get('audio', {}), st.get('subtitle', {})
    d = float(j['format']['duration'])
    e = sh('ffmpeg', '-nostats', '-i', f, '-map', '0:a', '-af', 'ebur128=peak=true', '-f', 'null', '-').stderr.split('Summary')[-1]
    I = float(re.search(r'I:\s+(-?[\d.]+) LUFS', e).group(1)); tp = float(re.search(r'Peak:\s+(-?[\d.]+) dBFS', e).group(1))
    cs = [(tsec(x), tsec(y)) for x, y in re.findall(r'(\d\d:\d\d:\d\d,\d\d\d) --> (\d\d:\d\d:\d\d,\d\d\d)', open(f[:-4] + '.srt').read())]
    probs = []
    if (v.get('width'), v.get('height'), v.get('codec_name'), v.get('r_frame_rate')) != (1920, 1080, 'h264', '30/1'): probs.append('video format')
    if a.get('codec_name') != 'aac': probs.append('audio codec')
    if s.get('codec_name') != 'mov_text': probs.append('no mov_text subtitles')
    if tp > -1.0: probs.append(f'true peak {tp}')
    if abs(I - float(os.environ.get('LUFS_TARGET', '-16'))) > 1.0: probs.append(f'loudness {I} LUFS')
    if any(cs[i][1] > cs[i + 1][0] for i in range(len(cs) - 1)): probs.append('srt overlap')
    if any(y - x < 1.5 - 1e-3 for x, y in cs): probs.append('srt cue < 1.5 s')
    if cs and cs[-1][1] > d: probs.append('srt ends after video')
    print(f"{os.path.basename(f):24s} {d:7.2f}s I={I:.1f} LUFS TP={tp:.1f} cues={len(cs)}" + ('  ERROR: ' + ', '.join(probs) if probs else ''))
    return not probs

def sheet(main, out):
    os.makedirs(out, exist_ok=True)
    sh('ffmpeg', '-v', 'error', '-y', '-i', main, '-vf', "fps=1/4,scale=480:-1,drawtext=text='%{pts\\:hms}':x=8:y=8:fontsize=20:fontcolor=white:"
       "box=1:boxcolor=black@0.6,tile=6x10:padding=4", '-frames:v', '1', os.path.join(out, 'contact-sheet.png'))
    d = float(sh('ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', main).stdout)
    for i in range(1, 6):
        t = d * i / 6; sh('ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.2f}', '-i', main, '-frames:v', '1', os.path.join(out, f'frame_{int(t)}.png'))
    print('sheet and frames in', out)

def stt(main):
    from google import genai
    mp3 = main[:-4] + '_check.mp3'; sh('ffmpeg', '-v', 'error', '-y', '-i', main, '-vn', '-b:a', '160k', mp3)
    c = genai.Client(); f = c.files.upload(file=mp3)
    while f.state.name == 'PROCESSING': time.sleep(2); f = c.files.get(name=f.name)
    print(c.models.generate_content(model='gemini-2.5-pro', contents=[f, 'Soundtrack of a demo video: a narrator over background music. '
          '1) Transcribe all narration verbatim, one line per sentence with start timestamps. 2) Is any word masked by the music? '
          'Is the music ever too loud? Any vocals in the music?']).text); os.remove(mp3)

if __name__ == '__main__':
    out = sys.argv[1]; files = sorted(glob.glob(os.path.join(out, '*.mp4'))) + sorted(glob.glob(os.path.join(out, 'clips', '*.mp4')))
    ok = all([check(f) for f in files])
    if '--sheet' in sys.argv: sheet(files[0], os.path.join(os.path.dirname(os.path.abspath(out)), 'check'))
    if '--stt' in sys.argv: stt(files[0])
    sys.exit(0 if ok else 1)
