"""Record a phone take of a public web page at a true 390x844 CSS viewport and 2x pixels (780x1688 MP4, 30 fps).

  python3 record_phone.py TAKE.json OUT_DIR

Playwright video and the CDP screencast capture the headless window, not the emulated 2x phone. This script grabs
page.screenshot() in a loop (about 29 fps) and rebuilds a constant 30 fps video from the frame timestamps.

TAKE.json: {"name": "pv", "base_url": "http://localhost:8788", "viewport": [390, 844], "scale": 2,
  "mock_submit": {"pattern": "**/api/submit/**", "response": {"ok": true, "ref": "TP-123ABC"}},
  "steps": [{"goto": "/"}, {"click": ".lang-switch button[value=en]"}, {"type": ["#name", "Maria Alvarez"]},
            {"fill": ["#date", "2026-11-03"]}, {"pick": "label.choice:has(input[name=urgent][value=yes])"},
            {"select": ["#language", "English"]}, {"submit": "form button[type=submit]", "wait_url": "**/thanks**"}, {"pause": 3.5}]}
mock_submit answers the form POST locally. Use it when the real submit was already sent during the app take, so the
room shows exactly what the phone sends and nothing is posted twice. Every intercepted body is logged for comparison.
"""
import asyncio, json, os, subprocess, sys, time
from playwright.async_api import async_playwright

async def main(take, out):
    T = json.load(open(take)); d = os.path.join(out, f"raw_{T['name']}"); os.makedirs(d, exist_ok=True)
    vw, vh = T.get('viewport', [390, 844]); sc = T.get('scale', 2); frames, log = [], []; t0 = [0.0]
    ev = lambda k, **kw: (log.append(dict(t=round(time.time() - t0[0], 2), k=k, **kw)), print(log[-1], flush=True))
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        c = await b.new_context(viewport={'width': vw, 'height': vh}, device_scale_factor=sc, is_mobile=True, has_touch=True, locale=T.get('locale', 'en-US'))
        if T.get('mock_submit'):
            ms = T['mock_submit']
            async def handle(route):
                ev('submit_intercepted', url=route.request.url, body=json.loads(route.request.post_data or '{}')); await asyncio.sleep(0.6)
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(ms['response']))
            await c.route(ms['pattern'], handle)
        pg = await c.new_page(); stop = [False]
        async def grab():
            while not stop[0]:
                t = time.time() - t0[0]; img = await pg.screenshot(type='jpeg', quality=93, animations='allow', caret='initial')
                fn = os.path.join(d, f'f{len(frames):05d}.jpg'); open(fn, 'wb').write(img); frames.append((t, fn))
        async def scroll(sel):
            await pg.evaluate("s=>document.querySelector(s).scrollIntoView({behavior:'smooth',block:'center'})", sel); await pg.wait_for_timeout(450)
        t0[0] = time.time(); g = asyncio.ensure_future(grab())
        for st in T['steps']:
            if 'goto' in st: await pg.goto(T['base_url'] + st['goto']); await pg.wait_for_timeout(int(st.get('wait', 1.5) * 1000))
            elif 'click' in st: await pg.click(st['click']); await pg.wait_for_timeout(900)
            elif 'type' in st:
                sel, text = st['type']; await scroll(sel); await pg.click(sel); await pg.keyboard.type(text, delay=st.get('delay', 40)); await pg.wait_for_timeout(200)
            elif 'fill' in st: await scroll(st['fill'][0]); await pg.fill(*st['fill']); await pg.wait_for_timeout(300)
            elif 'pick' in st: await scroll(st['pick']); await pg.click(st['pick']); await pg.wait_for_timeout(350)
            elif 'select' in st: await scroll(st['select'][0]); await pg.select_option(st['select'][0], value=st['select'][1]); await pg.wait_for_timeout(400)
            elif 'submit' in st:
                await scroll(st['submit']); await pg.wait_for_timeout(500); ev('tap'); await pg.click(st['submit'])
                if st.get('wait_url'): await pg.wait_for_url(st['wait_url'], timeout=20000); ev('done')
            elif 'pause' in st: await pg.wait_for_timeout(int(st['pause'] * 1000))
            ev('step', step=list(st)[0])
        end = time.time() - t0[0]; stop[0] = True; await g; await c.close(); await b.close()
    lines = []
    for i, (t, fn) in enumerate(frames):
        nt = frames[i + 1][0] if i + 1 < len(frames) else end
        lines.append(f"file '{os.path.abspath(fn)}'\nduration {max(nt - t, 0.001):.4f}")
    lines.append(f"file '{os.path.abspath(frames[-1][1])}'"); open(os.path.join(d, 'list.txt'), 'w').write('\n'.join(lines) + '\n')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', os.path.join(d, 'list.txt'), '-vf',
                    f'fps=30,scale={vw * sc}:{vh * sc}:flags=lanczos,format=yuv420p', '-c:v', 'libx264', '-crf', '12', os.path.join(out, f"{T['name']}.mp4")], check=True)
    json.dump(log, open(os.path.join(out, f"{T['name']}.log.json"), 'w'), indent=1); print('frames', len(frames))

if __name__ == '__main__':
    asyncio.run(main(sys.argv[1], sys.argv[2]))
