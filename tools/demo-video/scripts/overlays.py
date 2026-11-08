"""Render caption cards (lower thirds) and scene-card text layers from the HTML templates to transparent PNGs.

Each spec renders once to <cache>/<kind>_<hash>.png plus a .json with layout metadata. Call configure() first.
"""
import hashlib, html, json, os, re
from playwright.sync_api import sync_playwright

TEMPLATES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates')
FONTS = ('<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700;800'
         '&family=Inter:wght@500;600&display=block" rel="stylesheet">')
CFG = dict(cache=None, templates=TEMPLATES)

def configure(cache_dir, templates_dir=None):
    CFG['cache'] = cache_dir; os.makedirs(cache_dir, exist_ok=True)
    if templates_dir: CFG['templates'] = templates_dir

def md(s):
    """*word* -> lime accent."""
    return re.sub(r'\*(.+?)\*', r'<em>\1</em>', html.escape(s))
def plain(s): return s.replace('*', '')
def _key(*a): return hashlib.md5(json.dumps(a, sort_keys=True).encode()).hexdigest()[:12]

def lt_spec(eb, cap, who): return dict(kind='lt', eb=eb, cap=cap, who=who)
def card_spec(eb, title, sub, name=False): return dict(kind='card', eb=eb, title=title, sub=sub, name=name)
def path_of(spec): return os.path.join(CFG['cache'], f"{spec['kind']}_{_key(spec, 'fit1')}")

def _tpl(name):
    t = open(os.path.join(CFG['templates'], name)).read()
    return t.replace('{{fonts}}', FONTS).replace('{{tokens}}', open(os.path.join(CFG['templates'], 'tokens.css')).read())

def render(specs):
    todo = [s for s in specs if not os.path.exists(path_of(s) + '.json')]
    if not todo: return
    lt_t, card_t = _tpl('lower-third.html'), _tpl('scene-card.html')
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
        for s in todo:
            base = path_of(s)
            if s['kind'] == 'lt':
                doc = (lt_t.replace('{{eyebrow}}', html.escape(s['eb'])).replace('{{caption}}', md(s['cap']))
                       .replace('{{who}}', f'<div class="who">{md(s["who"])}</div>' if s['who'] else ''))
                pg.set_content(doc); pg.evaluate('document.fonts.ready'); pg.wait_for_timeout(150)
                # shrink-wrap each text block to its longest line so the card hugs the text
                pg.evaluate('''() => { for (const el of document.querySelectorAll('.cap,.who')) {
                    const r = document.createRange(); r.selectNodeContents(el); const L = el.getBoundingClientRect().left;
                    let m = 0; for (const q of r.getClientRects()) m = Math.max(m, q.right - L);
                    el.style.width = Math.ceil(m + 1) + 'px'; } }''')
                w = pg.locator('#wrap'); w.screenshot(path=base + '.png', omit_background=True)
                wb = w.bounding_box(); lb = pg.locator('.lt').bounding_box()
                meta = dict(w=round(wb['width']), h=round(wb['height']), bx=round(lb['x'] - wb['x']), by=round(lb['y'] - wb['y']),
                            bw=round(lb['width']), bh=round(lb['height']), r=18)
            else:
                doc = (card_t.replace('{{eyebrow}}', html.escape(s['eb'])).replace('{{title}}', md(s['title']))
                       .replace('{{title_class}}', 't name' if s['name'] else 't')
                       .replace('{{sub}}', f'<div class="s">{md(s["sub"])}</div>' if s['sub'] else ''))
                pg.set_content(doc); pg.evaluate('document.fonts.ready'); pg.wait_for_timeout(150)
                pg.screenshot(path=base + '.png', omit_background=True)
                meta = dict(layers=[])
                for sel in ('.eb', '.t', '.s'):
                    if pg.locator(sel).count():
                        bb = pg.locator(sel).bounding_box(); meta['layers'].append([round(bb['y']), round(bb['y'] + bb['height'])])
            json.dump(meta, open(base + '.json', 'w'))
        b.close()
