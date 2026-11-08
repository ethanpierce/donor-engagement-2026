"""Narration-timed editor: plan JSON + takes + per-scene voiceover -> final MP4 (H.264, AAC, mov_text subtitles), SRT, clips.

Usage:
  python3 editor.py PLAN.json plan              # print the timeline (no rendering)
  python3 editor.py PLAN.json render mix clips  # full build (default: all three)
  python3 editor.py PLAN.json render mix --only S12a --name website-announcements   # one scene as a standalone clip
Scenes with "enabled": false are skipped in the full video (use them as ready-to-insert scenes or standalone clips).

Timing model (see SKILL.md): each scene lasts LEAD + narration + TAIL_GAP seconds, scenes crossfade XF seconds.
Inside a scene, every sentence gets its own caption and shot beats; beats fill the sentence time by weight.
Paths in the plan are relative to the plan file. vo/timing.json comes from vo.py.
Mix: the music bed is built from project.music (music_start, music_end, music_bpm, see music.py), plays from the
first frame (music_fade_in, default 0.3 s, so it sits under the intro card at the same level as under the outro),
ducks under the voice, and the master gain is set so the mix reaches project.loudness (default -16 LUFS).
MASTER_GAIN_DB=<dB> in the environment skips the measurement and uses that gain.
"""
import json, os, re, subprocess, sys
from multiprocessing import Pool
import overlays, comp, music
from overlays import lt_spec, card_spec, badge_spec, plain

def load(plan_path):
    P = json.load(open(plan_path)); base = os.path.dirname(os.path.abspath(plan_path))
    R = lambda p: p if p is None or os.path.isabs(p) else os.path.join(base, p)
    pr = P['project']
    cfg = dict(base=base, out=R(pr['out_dir']), work=R(pr['work_dir']), plates=R(pr.get('plates_dir')), intro=R(pr.get('intro')),
               outro=R(pr.get('outro')), music=R(pr.get('music')), vo=R(pr['vo_dir']), name=pr['name'],
               gain=float(pr.get('music_gain_db', -8.5)), duck=float(pr.get('duck_threshold', 0.05)), cover_font=R(pr.get('cover_font')),
               takes={k: R(v) for k, v in P.get('takes', {}).items()}, templates=R(pr.get('templates_dir')),
               m_start=float(pr.get('music_start', 0.0)), m_end=pr.get('music_end'), m_bpm=pr.get('music_bpm'),
               m_fade=float(pr.get('music_fade_in', 0.3)), lufs=pr.get('loudness', -16.0), badge_min=pr.get('speed_badge_min'))
    t = P.get('timing', {})
    cfg.update(XF=t.get('xfade', 0.3), LEAD=t.get('lead', 0.25), TAIL=t.get('tail_gap', 0.42), PRE=t.get('pre_card', 1.6))
    return P, cfg

def dur(f): return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], capture_output=True, text=True).stdout)
def ts(x):
    ms = int(round(x * 1000)); return f'{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}'

def focus_of(f):
    if f is None: return None
    if isinstance(f, dict): return ('bub', f['bubble'], f.get('index', -1))
    if f and isinstance(f[0], list): return [tuple(x) for x in f]
    return tuple(f)

def plan(P, cfg, only=None):
    if only:   # standalone clip: just these scenes, no intro or outro
        P = dict(P, scenes=[s for s in P['scenes'] if s['id'] in only]); cfg = dict(cfg, intro=None, outro=None)
    else: P = dict(P, scenes=[s for s in P['scenes'] if s.get('enabled', True)])
    TIM = json.load(open(os.path.join(cfg['vo'], 'timing.json')))
    XF, LEAD, TAIL, PRE = cfg['XF'], cfg['LEAD'], cfg['TAIL'], cfg['PRE']
    items = []; T = 0.0
    if cfg['intro']:
        items.append(dict(kind='asset', path=cfg['intro'], start=0.0, dur=dur(cfg['intro']), scene='intro')); T = items[0]['dur']
    voice, sents, scenes = [], [], {}
    for sc in P['scenes']:
        k = sc['id']; L = TIM[k]['L']; sp = TIM[k]['sents']; E = LEAD + L + TAIL
        caps = sc.get('captions') or [s for _, _, s in sp]
        assert [plain(c) for c in caps] == [s for _, _, s in sp], f'{k}: captions differ from the narration sentences'
        voice.append((k, T + LEAD)); scenes[k] = (T, T + E)
        c = [0.0] + [LEAD + a - 0.12 for a, _, _ in sp[1:]] + [E]
        for j, (a, b, s) in enumerate(sp): sents.append(dict(scene=k, j=j, a=T + LEAD + a, b=T + LEAD + b, text=s))
        parts = sc['parts']; cur = 0.0
        for pi, p in enumerate(parts):
            if p['type'] == 'card' and p.get('pre'): s0, s1 = 0.0, PRE
            elif p['type'] == 'card': s0, s1 = cur, c[p['sents'][-1] + 1]
            else:
                js = sorted({b['sent'] for b in p['beats']}); s0 = cur; s1 = c[js[-1] + 1]
                nxt = parts[pi + 1] if pi + 1 < len(parts) else None
                if nxt and nxt['type'] == 'shot' and nxt['beats'][0]['sent'] == js[-1]:   # the next shot shares this sentence
                    wa = sum(b.get('w', 1) for b in p['beats'] if b['sent'] == js[-1]); wb = sum(b.get('w', 1) for b in nxt['beats'] if b['sent'] == js[-1])
                    lo = max(s0, c[js[-1]]); s1 = lo + (c[js[-1] + 1] - lo) * wa / (wa + wb)
            if pi == len(parts) - 1: s1 = E
            d = s1 - s0 + XF
            if p['type'] == 'card':
                it = dict(kind='card', spec=card_spec(p['eyebrow'], p['title'], p.get('sub', ''), p.get('name', False)), plate=p.get('plate', 'skyline'), dur=round(d, 3))
            else:
                order = []
                for b in p['beats']:
                    if b['sent'] not in order: order.append(b['sent'])
                bts = []
                for jj, j in enumerate(order):
                    lo = max(s0, c[j]) if jj else s0; hi = min(s1, c[j + 1]) if jj < len(order) - 1 else s1
                    bb = [b for b in p['beats'] if b['sent'] == j]; Wt = sum(b.get('w', 1) for b in bb)
                    for b in bb:
                        bd = {kk: v for kk, v in b.items() if kk in ('freeze', 'a', 'b', 'zoom', 'who', 'eb', 'minsp')}
                        f = focus_of(b.get('focus'))
                        if f is not None: bd['focus'] = f
                        if p.get('covers'): bd['covers'] = p['covers']
                        bd['dur'] = round((hi - lo) * b.get('w', 1) / Wt, 3); bd['cap'] = caps[j]
                        if 'view' in b: bd['view'] = b['view']
                        if isinstance(b.get('badge'), str): bd['badge'] = b['badge']
                        elif cfg['badge_min'] and b.get('badge', True) and b.get('freeze') is None and 'a' in b:
                            sp = (b['b'] - b['a']) / bd['dur']   # sped-up range: show "N× speed"
                            if sp >= cfg['badge_min']: bd['badge'] = f'{sp:.0f}×'
                        bts.append(bd)
                bts[-1]['dur'] = round(bts[-1]['dur'] + XF, 3)
                it = dict(kind='shot', layout=p['layout'], src=cfg['takes'][p['take']], eb=p['eyebrow'], who=p.get('who', ''), beats=bts)
            items.append(dict(kind='r', start=T + s0, dur=d, item=it, scene=k)); cur = s1
        T += E
    if cfg['outro']:
        items.append(dict(kind='asset', path=cfg['outro'], start=T, dur=dur(cfg['outro']), scene='outro')); total = T + items[-1]['dur']
    else: total = T + XF
    return items, voice, sents, scenes, total

def cues_from(sents, t0, t1):
    """SRT cues: one sentence each, at least 1.5 s, merged with the next sentence when too short, never overlapping."""
    out = []
    for s in [s for s in sents if s['a'] >= t0 - 0.01 and s['b'] <= t1 + 0.01]:
        out.append(dict(a=s['a'], b=s['b'] + 0.3, text=s['text']))
    for i, cq in enumerate(out):
        nxt = out[i + 1]['a'] - 0.04 if i + 1 < len(out) else t1 - 0.1
        cq['b'] = min(max(cq['b'], cq['a'] + 1.5), nxt)
    res = []
    for cq in out:
        if res and res[-1]['b'] - res[-1]['a'] < 1.5: res[-1]['b'] = cq['b']; res[-1]['text'] += ' ' + cq['text']
        else: res.append(cq)
    return [(c['a'] - t0, c['b'] - t0, c['text']) for c in res]

def write_srt(path, cues):
    open(path, 'w').write(''.join(f'{i + 1}\n{ts(a)} --> {ts(b)}\n{c}\n\n' for i, (a, b, c) in enumerate(cues)))

_W = {}
def _init(seg, plates, font, ovc, tpl):
    comp.configure(seg, plates, font); overlays.configure(ovc, tpl)
def _job(it): return comp.render_item(it)

def render_video(items, total, path, XF):
    args = ['ffmpeg', '-v', 'error', '-y']
    for it in items: args += ['-i', it['path'] if it['kind'] == 'asset' else it['file']]
    fc = []
    for i, it in enumerate(items):
        pad = f',tpad=stop_mode=clone:stop_duration={XF + 0.05}' if it['kind'] == 'asset' and i == 0 else ''   # intro plays fully
        fc.append(f'[{i}:v]fps=30,scale=1920:1080,format=yuv420p,settb=AVTB,setpts=PTS-STARTPTS{pad}[v{i}]')
    prev = 'v0'
    for i in range(1, len(items)):
        fc.append(f'[{prev}][v{i}]xfade=transition=fade:duration={XF}:offset={items[i]["start"]:.4f}[x{i}]'); prev = f'x{i}'
    subprocess.run(args + ['-filter_complex', ';'.join(fc), '-map', f'[{prev}]', '-an', '-c:v', 'libx264', '-preset', 'slow', '-crf', '20',
                           '-pix_fmt', 'yuv420p', '-r', '30', '-t', f'{total:.3f}', path], check=True)

def lufs(f):
    e = subprocess.run(['ffmpeg', '-nostats', '-i', f, '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True).stderr.split('Summary')[-1]
    return float(re.search(r'I:\s+(-?[\d.]+) LUFS', e).group(1))

def mix_audio(cfg, voice, total, path):
    """Voice track (scene files already at -16 LUFS), music bed ducked ~6 dB under it with fades, master gain to the
    loudness target, true-peak limited."""
    W = os.path.dirname(path); vo, mu = f'{W}/voice.wav', f'{W}/music_ducked.wav'
    args = ['ffmpeg', '-v', 'error', '-y']
    for k, t in voice: args += ['-i', os.path.join(cfg['vo'], f'n_{k}.wav')]
    fc = [f'[{i}:a]aresample=48000,aformat=channel_layouts=mono,adelay={int(round(t * 1000))}:all=1[d{i}]' for i, (k, t) in enumerate(voice)]
    fc.append(''.join(f'[d{i}]' for i in range(len(voice))) + f'amix=inputs={len(voice)}:normalize=0,apad=whole_dur={total:.3f},atrim=0:{total:.3f},aformat=channel_layouts=stereo[o]')
    subprocess.run(args + ['-filter_complex', ';'.join(fc), '-map', '[o]', '-ar', '48000', '-c:a', 'pcm_s24le', vo], check=True)
    if cfg['music']:
        bed = f'{W}/bed.wav'
        info = music.bed(cfg['music'], bed, total + 1.0, cfg['m_start'], cfg['m_end'], cfg['m_bpm'])
        print('music bed', info, flush=True)
        fc = [f'[0:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{total:.3f},asetpts=PTS-STARTPTS,volume={cfg["gain"]}dB,'
              f'afade=t=in:st=0:d={cfg["m_fade"]},afade=t=out:st={total - 3.5:.3f}:d=3.5[m]', '[1:a]highpass=f=120[sc]',
              f'[m][sc]sidechaincompress=threshold={cfg["duck"]}:ratio=3:attack=80:release=700:knee=3:makeup=1[o]']
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', bed, '-i', vo, '-filter_complex', ';'.join(fc), '-map', '[o]', '-ar', '48000', '-c:a', 'pcm_s24le', mu], check=True)
        pre = f'{W}/premix.wav'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', vo, '-i', mu, '-filter_complex', '[0:a][1:a]amix=inputs=2:normalize=0:duration=first[o]',
                        '-map', '[o]', '-ar', '48000', '-c:a', 'pcm_s24le', pre], check=True)
    else: pre = vo
    # master gain to the loudness target, then the true-peak limiter (it lowers loudness a little: measure and correct once)
    fixed = os.environ.get('MASTER_GAIN_DB'); target = cfg['lufs']
    g = float(fixed) if fixed is not None else (target - lufs(pre) if target is not None else 0.0)
    for _ in range(2):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', pre, '-af', f'volume={g:.2f}dB,alimiter=limit=0.82:attack=3:release=60:level=disabled',
                        '-ar', '48000', '-c:a', 'pcm_s16le', path], check=True)
        got = lufs(path)
        if fixed is not None or target is None or abs(got - target) <= 0.2: break
        g += target - got
    print(f'mix: master gain {g:+.2f} dB, {got:.1f} LUFS', flush=True)

def mux(video, audio, srt, out, ss=None, to=None):
    pre = ['-ss', f'{ss:.3f}', '-to', f'{to:.3f}'] if ss is not None else []
    af = ['-af', f'afade=t=in:st=0:d=0.4,afade=t=out:st={to - ss - 0.6:.3f}:d=0.6'] if ss is not None else []
    vc = ['-c:v', 'libx264', '-preset', 'slow', '-crf', '20', '-pix_fmt', 'yuv420p', '-r', '30'] if ss is not None else ['-c:v', 'copy']
    subprocess.run(['ffmpeg', '-v', 'error', '-y', *pre, '-i', video, *pre, '-i', audio, '-i', srt, '-map', '0:v', '-map', '1:a', '-map', '2:s',
                    *vc, *af, '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-c:s', 'mov_text', '-metadata:s:s:0', 'language=eng',
                    '-metadata:s:a:0', 'language=eng', '-map_metadata', '-1', '-movflags', '+faststart', out], check=True)

def main():
    args = sys.argv[2:]; only = name = None
    if '--only' in args: i = args.index('--only'); only = args[i + 1].split(','); del args[i:i + 2]
    if '--name' in args: i = args.index('--name'); name = args[i + 1]; del args[i:i + 2]
    plan_path, steps = sys.argv[1], (args or ['render', 'mix', 'clips'])
    P, cfg = load(plan_path)
    if name: cfg['name'] = name
    if only: steps = [s for s in steps if s != 'clips']
    os.makedirs(cfg['out'], exist_ok=True); os.makedirs(cfg['work'], exist_ok=True)
    seg, ovc = os.path.join(cfg['work'], 'seg'), os.path.join(cfg['work'], 'overlays')
    _init(seg, cfg['plates'], cfg['cover_font'], ovc, cfg['templates'])
    items, voice, sents, scenes, total = plan(P, cfg, only)
    name = cfg['name']; final = os.path.join(cfg['out'], name + '.mp4'); mixwav = os.path.join(cfg['work'], 'mix.wav')
    if 'plan' in steps:
        for it in items:
            x = it.get('item', {})
            print(f"{it['scene']:6s} {it['start']:7.2f} {it['dur']:6.2f} {x.get('kind', it['kind']):5s}",
                  [(b['dur'], b.get('freeze', b.get('a'))) for b in x.get('beats', [])])
        print('total', round(total, 2)); return
    rend = [it for it in items if it['kind'] == 'r']
    specs = []
    for it in rend:
        x = it['item']
        specs += [x['spec']] if x['kind'] == 'card' else [lt_spec(b.get('eb', x['eb']), b['cap'], b.get('who', x['who'])) for b in x['beats']]
        specs += [badge_spec(b['badge']) for b in x.get('beats', []) if b.get('badge')]
    overlays.render(specs)
    if 'render' in steps:
        with Pool(int(os.environ.get('JOBS', '6')), initializer=_init, initargs=(seg, cfg['plates'], cfg['cover_font'], ovc, cfg['templates'])) as pool:
            res = pool.map(_job, [it['item'] for it in rend], chunksize=1)
        for it, (f, m) in zip(rend, res):
            it['file'] = f; assert abs(m['dur'] - it['dur']) < 0.06, (it['scene'], m['dur'], it['dur'])
        render_video(items, total, os.path.join(cfg['work'], 'video.mp4'), cfg['XF'])
    if 'mix' in steps:
        mix_audio(cfg, voice, total, mixwav)
        srt = os.path.join(cfg['out'], name + '.srt'); write_srt(srt, cues_from(sents, 0, total))
        mux(os.path.join(cfg['work'], 'video.mp4'), mixwav, srt, final)
        json.dump(dict(total=total, scenes=scenes, voice=voice, sents=sents,
                       items=[dict(scene=i['scene'], start=i['start'], dur=i['dur']) for i in items]), open(os.path.join(cfg['work'], 'plan.json'), 'w'), indent=1)
    if 'clips' in steps:
        cd = os.path.join(cfg['out'], 'clips'); os.makedirs(cd, exist_ok=True); XF = cfg['XF']
        for cl in P.get('clips', []):
            wins = [(scenes[s][0], scenes[s][1] + XF) for s in cl['scenes']]
            if not cl.get('join'): wins = [(wins[0][0], wins[-1][1])]
            parts = []
            for i, (a, b) in enumerate(wins):
                cq = cues_from(sents, a, b); s = os.path.join(cfg['work'], f'_c{i}.srt'); write_srt(s, cq)
                o = os.path.join(cfg['work'], f'_c{i}.mp4'); mux(final, mixwav, s, o, a, b); parts.append((o, b - a, cq))
            out = os.path.join(cd, cl['name'] + '.mp4'); srt = os.path.join(cd, cl['name'] + '.srt')
            if len(parts) == 1:
                os.replace(parts[0][0], out); write_srt(srt, parts[0][2])
            else:   # join windows with crossfades
                cues, off, fc, prev, aprev = [], 0.0, [], '0:v', '0:a'
                for i, (o, d, cq) in enumerate(parts):
                    cues += [(x + off, y + off, t) for x, y, t in cq]
                    if i:
                        fc.append(f'[{prev}][{i}:v]xfade=transition=fade:duration={XF}:offset={off:.3f}[v{i}]')
                        fc.append(f'[{aprev}][{i}:a]acrossfade=d={XF}[a{i}]'); prev, aprev = f'v{i}', f'a{i}'
                    off += d - XF
                write_srt(srt, cues)
                args = ['ffmpeg', '-v', 'error', '-y']
                for o, _, _ in parts: args += ['-i', o]
                subprocess.run(args + ['-i', srt, '-filter_complex', ';'.join(fc), '-map', f'[{prev}]', '-map', f'[{aprev}]', '-map', f'{len(parts)}:s',
                                       '-c:v', 'libx264', '-preset', 'slow', '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k',
                                       '-c:s', 'mov_text', '-metadata:s:s:0', 'language=eng', '-map_metadata', '-1', '-movflags', '+faststart', out], check=True)
            print('clip', cl['name'], flush=True)

if __name__ == '__main__':
    main()
