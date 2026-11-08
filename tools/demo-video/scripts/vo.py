"""Voiceover: one TTS file per scene, loudness-normalised, with sentence timings for the editor.

  python3 vo.py PLAN.json trial S1 heygen:<voice_id> heygen:<voice_id> gemini:Sulafat   # one line, several voices + Gemini verdict
  python3 vo.py PLAN.json tts [S1 S2 ...]                             # write <vo_dir>/<id>.wav (skips existing files)
  python3 vo.py PLAN.json align [S1 ...]                              # trim, -16 LUFS, word timestamps -> timing.json
  python3 vo.py PLAN.json check                                       # Gemini STT per scene vs. the script

Env: HEYGEN_API_KEY (default TTS), GEMINI_API_KEY (fallback TTS, STT and listening checks), FAL_KEY (ElevenLabs TTS via fal).
Plan "voice": {"provider": "heygen"|"gemini"|"elevenlabs", "model": ..., "voice": ..., "style": optional prompt prefix (Gemini only)}.
HeyGen: model "legacy" uses POST /v1/audio/text_to_speech with a voice id from GET /v2/voices; a v3 model name
(e.g. heygen-voice-1) uses POST /v3/models/audio/tts with a v3 voice id. If the legacy route is retired, render a
voice-only video (POST /v2/video/generate, plain color background) and extract the audio, or fall back to Gemini.
"""
import difflib, json, os, re, subprocess, sys, time, wave, urllib.request

def load(plan_path):
    P = json.load(open(plan_path)); base = os.path.dirname(os.path.abspath(plan_path))
    vo = P['project']['vo_dir']; vo = vo if os.path.isabs(vo) else os.path.join(base, vo); os.makedirs(vo, exist_ok=True)
    return P, vo

def run(*a): return subprocess.run(a, capture_output=True, text=True)
def dur(f): return float(run('ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f).stdout)
def sents(text): return re.split(r'(?<=[.!?])\s+', text.strip())

def heygen_tts(voice, text, out, model='legacy', speed=None):
    """HeyGen TTS. model 'legacy': POST /v1/audio/text_to_speech (HeyGen voice library ids, e.g. the 32-hex ids from
    GET /v2/voices; returns an MP3 URL). Otherwise POST /v3/models/audio/tts with that model name (v3 voice ids). Env HEYGEN_API_KEY."""
    import requests
    H = {'X-Api-Key': os.environ['HEYGEN_API_KEY'], 'Content-Type': 'application/json'}
    for attempt in range(6):
        if model == 'legacy':
            body = dict(text=text, voice_id=voice)
            if speed: body['speed'] = speed
            r = requests.post('https://api.heygen.com/v1/audio/text_to_speech', headers=H, json=body, timeout=180)
        else:
            r = requests.post('https://api.heygen.com/v3/models/audio/tts', headers=H, json=dict(model=model, voice_id=voice, text=text, language='en'), timeout=180)
        if r.status_code in (429, 500, 502, 503):
            time.sleep(int(r.headers.get('Retry-After', 5 * (attempt + 1)))); continue
        r.raise_for_status(); d = r.json()['data']; url = d.get('audio_url') or d.get('url') or d['audio']['url']; break
    else: raise SystemExit(f'HeyGen TTS failed: {out}')
    tmp = out + '.dl'; urllib.request.urlretrieve(url, tmp)
    run('ffmpeg', '-v', 'error', '-y', '-i', tmp, '-ac', '1', '-ar', '48000', out); os.remove(tmp)

def tts(provider, model, voice, text, out, style=''):
    if provider == 'heygen': return heygen_tts(voice, text, out, model or 'legacy')
    if provider == 'gemini':
        from google import genai
        from google.genai import types
        c = genai.Client()
        for attempt in range(4):
            try:
                r = c.models.generate_content(model=model, contents=(style + '\n' if style else '') + text, config=types.GenerateContentConfig(
                    response_modalities=['AUDIO'], speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)))))
                pcm = r.candidates[0].content.parts[0].inline_data.data; break
            except Exception as e:
                print('retry', e, flush=True); time.sleep(5)
        else: raise SystemExit(f'TTS failed: {out}')
        w = wave.open(out, 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm); w.close()
    else:   # ElevenLabs through fal, e.g. model fal-ai/elevenlabs/tts/multilingual-v2, voice Sarah
        import fal_client
        r = fal_client.subscribe(model, arguments=dict(text=text, voice=voice, stability=0.5, similarity_boost=0.75, style=0.15, speed=1.0))
        tmp = out + '.mp3'; urllib.request.urlretrieve(r['audio']['url'], tmp)
        run('ffmpeg', '-v', 'error', '-y', '-i', tmp, '-ac', '1', out); os.remove(tmp)

def gemini_ask(path, prompt, model='gemini-2.5-pro'):
    from google import genai
    c = genai.Client(); f = c.files.upload(file=path)
    while f.state.name == 'PROCESSING': time.sleep(2); f = c.files.get(name=f.name)
    return c.models.generate_content(model=model, contents=[f, prompt]).text

def cmd_trial(P, vo, scene, voices):
    text = next(s['narration'] for s in P['scenes'] if s['id'] == scene); files = []
    for v in voices:
        prov, name = v.split(':', 1); out = os.path.join(vo, f'trial_{prov}_{name}.wav')
        if prov == 'gemini': tts('gemini', 'gemini-2.5-pro-preview-tts', name, text, out, P['voice'].get('style', ''))
        elif prov == 'heygen': tts('heygen', 'legacy', name, text, out)
        else: tts('elevenlabs', 'fal-ai/elevenlabs/tts/multilingual-v2', name, text, out)
        files.append(out)
    cmp_ = os.path.join(vo, 'trial_compare.wav'); args = ['ffmpeg', '-v', 'error', '-y']
    for f in files: args += ['-i', f]
    fc = ''.join(f'[{i}:a]aresample=44100,aformat=channel_layouts=mono,apad=pad_dur=2[a{i}];' for i in range(len(files)))
    fc += ''.join(f'[a{i}]' for i in range(len(files))) + f'concat=n={len(files)}:v=0:a=1'
    run(*args, '-filter_complex', fc, cmp_)
    print(gemini_ask(cmp_, f'This file has {len(files)} takes of the same narration line by different TTS voices, in order, '
                           'separated by 2-second silences. Rate each take 1-10 for naturalness, warmth, clarity and artifacts, '
                           'note mispronunciations, then pick the best voice for a warm, natural product demo narration.'))
    print('takes:', [os.path.basename(f) for f in files])

def cmd_tts(P, vo, ids):
    v = P['voice']
    for s in P['scenes']:
        out = os.path.join(vo, f"{s['id']}.wav")
        if (ids and s['id'] not in ids) or (not ids and os.path.exists(out)): continue
        tts(v['provider'], v['model'], v['voice'], s['narration'], out, v.get('style', '')); print(s['id'], round(dur(out), 2), flush=True)

def cmd_align(P, vo, ids=()):
    from faster_whisper import WhisperModel
    model = WhisperModel(os.environ.get('WHISPER_MODEL', 'small.en'), device='cpu', compute_type='int8')
    norm = lambda w: re.sub(r'[^a-z0-9]', '', w.lower())
    old = json.load(open(os.path.join(vo, 'timing.json'))) if os.path.exists(os.path.join(vo, 'timing.json')) else {}
    out = dict(old)
    for s in P['scenes']:
        if (ids and s['id'] not in ids) or not os.path.exists(os.path.join(vo, f"{s['id']}.wav")): continue
        k = s['id']; src, tr, nf = (os.path.join(vo, f'{x}{k}.wav') for x in ('', 't_', 'n_'))
        run('ffmpeg', '-v', 'error', '-y', '-i', src, '-af', 'silenceremove=start_periods=1:start_threshold=-48dB:start_silence=0.04,areverse,'
            'silenceremove=start_periods=1:start_threshold=-48dB:start_silence=0.06,areverse,aresample=48000', tr)
        m = json.loads(re.search(r'\{[^{}]*"input_i"[^{}]*\}', run('ffmpeg', '-i', tr, '-af', 'loudnorm=I=-16:TP=-2:LRA=11:print_format=json', '-f', 'null', '-').stderr).group(0))
        run('ffmpeg', '-v', 'error', '-y', '-i', tr, '-af', f"loudnorm=I=-16:TP=-2:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
            f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,aresample=48000", '-ar', '48000', nf)
        L = dur(nf); segs, _ = model.transcribe(nf, word_timestamps=True, language='en', beam_size=5)
        words = [w for sg in segs for w in sg.words]; tw = [norm(w.word) for w in words]
        ss = sents(s['narration']); sw, owner = [], []
        for j, x in enumerate(ss):
            for w in x.split(): sw.append(norm(w)); owner.append(j)
        mp = {}
        for blk in difflib.SequenceMatcher(None, sw, tw, autojunk=False).get_matching_blocks():
            for i in range(blk.size): mp[blk.a + i] = blk.b + i
        spans = []
        for j, x in enumerate(ss):
            fi = [mp[i] for i in range(len(sw)) if owner[i] == j and i in mp]
            if not fi: raise SystemExit(f'{k}: sentence {j} not aligned; check the TTS file')
            spans.append([round(max(0.0, float(words[fi[0]].start) - 0.02), 3), round(float(words[fi[-1]].end), 3), x])
        for j in range(1, len(spans)): spans[j][0] = max(spans[j][0], spans[j - 1][1])
        spans[-1][1] = round(L, 3); out[k] = dict(L=round(L, 3), sents=spans); print(k, round(L, 2), [a for a, _, _ in spans], flush=True)
    json.dump(out, open(os.path.join(vo, 'timing.json'), 'w'), indent=1)

def cmd_check(P, vo):
    norm = lambda s: re.sub(r"[^a-z0-9' ]", ' ', s.lower().replace('-', ' ')).split()
    for s in P['scenes']:
        t = gemini_ask(os.path.join(vo, f"{s['id']}.wav"), 'Transcribe this speech verbatim. Output only the transcript.', 'gemini-2.5-flash')
        r = difflib.SequenceMatcher(None, norm(s['narration']), norm(t)).ratio()
        print(s['id'], round(r, 3), '' if r > 0.95 else '| ' + t.strip())

if __name__ == '__main__':
    P, vo = load(sys.argv[1]); c = sys.argv[2]
    if c == 'trial': cmd_trial(P, vo, sys.argv[3], sys.argv[4:])
    elif c == 'tts': cmd_tts(P, vo, sys.argv[3:])
    elif c == 'align': cmd_align(P, vo, sys.argv[3:])
    elif c == 'check': cmd_check(P, vo)
    else: raise SystemExit(__doc__)
