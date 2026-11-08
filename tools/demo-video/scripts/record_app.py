"""Record one desktop take of the Roomcord web app (1440x900 WebM) from a JSON step list.

  python3 record_app.py TAKE.json OUT_DIR

Env:
  ROOMCORD_WEB_URL   web app URL including the mode flag, e.g. https://web.roomcord.com/?m=p
  ROOMCORD_STATE     Playwright storage-state JSON of the logged-in demo user (never commit it)
  WORKCORD_API_URL / WORKCORD_TOKEN   used by the `workcord` CLI to poll room messages for real agent replies

TAKE.json: {"name": "r2", "steps": [
   {"open_room": "Programs and mentoring"},
   {"say": "@Agent who needs a call this week?", "wait_for": "Agent display name", "timeout": 180},
   {"post": {"url": "http://localhost:8788/api/submit/volunteer", "json": {...}}, "room": "Volunteers",
    "wait_for": ["Tidepath portal", "Tidepath Volunteers"], "timeout": 180},
   {"pause": 3}, {"screenshot": "after.png"}]}
Each wait accepts only a completed reply (no "Thinking" or "Still working" state) and logs every event with its
time in the video to OUT_DIR/<name>.log.json, so the editor can cut around the wait.
"""
import asyncio, datetime, json, os, subprocess, sys, time, urllib.request
from playwright.async_api import async_playwright

def cli(*a):
    r = subprocess.run(['workcord', *a], capture_output=True, text=True)
    try: return json.loads(r.stdout)
    except Exception: return {'data': []}
ROOMS = {}
def room_id(name):
    if not ROOMS: ROOMS.update({r['name']: r['id'] for r in cli('rooms', 'list', '--all')['data']})
    return ROOMS[name]
def now_iso(back=2): return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=back)).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
def msgs(room, since): return cli('messages', 'new', '--room', room_id(room), '--since', since).get('data', [])

class Log:
    def __init__(s): s.t0 = None; s.ev = []
    def __call__(s, k, **kw):
        e = dict(t=round(time.time() - s.t0, 2), k=k, **kw); s.ev.append(e); print(e, flush=True); return e['t']

ROWS_JS = """(name)=>{for(const e of document.querySelectorAll('flt-semantics')){const r=e.getBoundingClientRect();
 const t=(e.getAttribute('aria-label')||e.textContent||'').replace(/^G\\n/,'');
 if(r.x>60&&r.x<80&&r.width>300&&r.width<360&&r.height<80&&t.startsWith(name+'\\n')) return [r.x+r.width/2,r.y+r.height/2,r.height];} return null}"""

async def open_room(pg, log, room):
    await pg.evaluate("document.querySelector('flt-semantics-placeholder')?.click()"); await pg.wait_for_timeout(300)
    for _ in range(6):
        r = await pg.evaluate(ROWS_JS, room)
        if r and r[2] > 60 and r[1] < 800: break
        await pg.mouse.move(240, 500); await pg.mouse.wheel(0, 300); await pg.wait_for_timeout(800)
    else: raise SystemExit(f'room {room} not found in the sidebar')
    await pg.mouse.click(r[0] - 60, r[1]); await pg.wait_for_timeout(2500); log('room', room=room)

async def wait_from(pg, log, room, since, sender, timeout):
    """Wait for a completed top-level reply from sender (prefix match). Requires two equal polls (streaming finished)."""
    end = time.time() + timeout; last = None
    while time.time() < end:
        await pg.wait_for_timeout(2500)
        cand = [m for m in msgs(room, since) if m['senderName'].startswith(sender) and len(m['content']) > 20
                and not m['content'].lower().startswith('still working') and (m.get('metadata') or {}).get('a2aState', 'completed') == 'completed']
        if cand:
            m = cand[-1]
            if last and last['id'] == m['id'] and last['content'] == m['content']:
                log('reply', sender=sender, room=room, id=m['id'], content=m['content'][:300]); return m
            last = m
    log('TIMEOUT', sender=sender, room=room)

async def main(take, out):
    T = json.load(open(take)); log = Log(); room = None
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        c = await b.new_context(viewport={'width': 1440, 'height': 900}, storage_state=os.environ['ROOMCORD_STATE'],
                                record_video_dir=os.path.join(out, f"raw_{T['name']}"), record_video_size={'width': 1440, 'height': 900})
        pg = await c.new_page(); log.t0 = time.time()   # video time ~ log time (recording starts with the page)
        await pg.goto(os.environ['ROOMCORD_WEB_URL']); await pg.wait_for_timeout(9000); log('loaded')
        for st in T['steps']:
            if 'open_room' in st: room = st['open_room']; await open_room(pg, log, room)
            elif 'say' in st:
                since = now_iso(); await pg.mouse.click(900, 864); await pg.wait_for_timeout(300)
                log('type_start', text=st['say']); await pg.keyboard.type(st['say'], delay=st.get('delay', 22)); log('type_end')
                await pg.wait_for_timeout(500); await pg.keyboard.press('Enter'); log('sent')
                if st.get('wait_for'): await wait_from(pg, log, st.get('room', room), since, st['wait_for'], st.get('timeout', 180))
            elif 'post' in st:   # a public form submit or webhook that posts into the room
                since = now_iso(); rq = urllib.request.Request(st['post']['url'], data=json.dumps(st['post']['json']).encode(),
                                                              headers={'Content-Type': 'application/json'})
                res = json.loads(urllib.request.urlopen(rq, timeout=30).read()); log('posted', response=res)
                for who in st.get('wait_for', []): await wait_from(pg, log, st.get('room', room), since, who, st.get('timeout', 180))
            elif 'pause' in st: await pg.wait_for_timeout(int(st['pause'] * 1000))
            elif 'screenshot' in st: await pg.screenshot(path=os.path.join(out, st['screenshot']))
        log('end'); await c.close(); await b.close()
    json.dump(log.ev, open(os.path.join(out, f"{T['name']}.log.json"), 'w'), indent=1)

if __name__ == '__main__':
    os.makedirs(sys.argv[2], exist_ok=True); asyncio.run(main(sys.argv[1], sys.argv[2]))
