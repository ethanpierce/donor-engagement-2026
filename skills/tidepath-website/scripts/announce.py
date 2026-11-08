#!/usr/bin/env python3
"""Announcements on the Tidepath public site (static build + Cloudflare Pages deploy).

Usage:
  announce.py list [--json]
  announce.py preview --title T --body B [--link URL --link-text TEXT --tone info|urgent|celebrate
                      --starts YYYY-MM-DD --ends YYYY-MM-DD]
  announce.py publish DRAFT_ID --approved-by NAME
  announce.py remove ANNOUNCEMENT_ID --approved-by NAME
  announce.py build            # build the site with the current announcements, no deploy
  announce.py verify [--wait SECONDS]

The site is built from a read-only copy of the public repo. The announcements
list lives in the workspace (the repo is not written). Every publish and
remove rebuilds the site from the latest repo main plus that list, deploys it,
and verifies the live page.

Environment (defaults in brackets):
  SITE_URL [https://tidepathfamily.org]
  REPO_URL [https://github.com/ethanpierce/donor-engagement-2026]
  REPO_BRANCH [main]   SITE_SUBDIR [website]
  ANNOUNCEMENTS_FILE [data/announcements.json]  (relative to SITE_SUBDIR)
  SITE_BUILD_CMD [hugo --minify]
  SITE_DEPLOY_CMD [npx --yes wrangler@4.158.0 pages deploy public --project-name "$CF_PAGES_PROJECT" --branch main --commit-dirty=true]
  HUGO_VERSION [0.155.3]  Hugo extended is downloaded on first use into ~/workspace/bin
                          and checked against the release SHA256 checksums.
  CF_PAGES_PROJECT, CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID (deploy only, never printed)
Exit codes: 0 ok, 1 failed check, 2 usage or input error.
"""
import argparse
import datetime as dt
import json
import os
import hashlib
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request

TONES = ("info", "urgent", "celebrate")
MAX_TITLE, MAX_BODY = 80, 280

WS = os.environ.get("AUTOWORKER_WORKSPACE") or os.environ.get("AUTOWORKER_HUB_WORKSPACE") \
    or os.path.expanduser("~/workspace")
STATE = os.path.join(WS, "website")
DRAFTS = os.path.join(STATE, "drafts")
PUBLISHED = os.path.join(STATE, "announcements.json")
LOG = os.path.join(STATE, "log.jsonl")
REPO_DIR = os.path.join(STATE, "repo")
BUILD_DIR = os.path.join(STATE, "build")

SITE_URL = os.environ.get("SITE_URL", "https://tidepathfamily.org").rstrip("/")
REPO_URL = os.environ.get("REPO_URL", "https://github.com/ethanpierce/donor-engagement-2026")
BRANCH = os.environ.get("REPO_BRANCH", "main")
SUBDIR = os.environ.get("SITE_SUBDIR", "website")
ANN_FILE = os.environ.get("ANNOUNCEMENTS_FILE", "data/announcements.json")
BUILD_CMD = os.environ.get("SITE_BUILD_CMD", "hugo --minify")
DEPLOY_CMD = os.environ.get(
    "SITE_DEPLOY_CMD",
    'npx --yes wrangler@4.158.0 pages deploy public --project-name "$CF_PAGES_PROJECT" '
    "--branch main --commit-dirty=true")
SECRET_NAMES = ("CLOUDFLARE_API_TOKEN",)
HUGO_VERSION = os.environ.get("HUGO_VERSION", "0.155.3")
BIN_DIR = os.path.join(WS, "bin")


def die(msg, code=2):
    print("ERROR: " + msg, file=sys.stderr)
    sys.exit(code)


def now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def iso(t):
    return t.isoformat().replace("+00:00", "Z")


def parse_day(s, end=False):
    if not s:
        return None
    try:
        d = dt.date.fromisoformat(s)
    except ValueError:
        die("date must be YYYY-MM-DD: " + s)
    t = dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc)
    return iso(t + dt.timedelta(days=1) if end else t)  # end date is inclusive


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def audit(event, **kw):
    os.makedirs(STATE, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(dict(at=iso(now()), event=event, **kw), ensure_ascii=False) + "\n")


def status(a, t=None):
    t = t or iso(now())
    if a.get("startsAt") and a["startsAt"] > t:
        return "scheduled"
    if a.get("endsAt") and a["endsAt"] <= t:
        return "expired"
    return "active"


def slug(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:40].rstrip("-") or "item"


def redact(text):
    for n in SECRET_NAMES:
        v = os.environ.get(n)
        if v:
            text = text.replace(v, "<redacted>")
    return text


def run(cmd, cwd, label):
    env = dict(os.environ, PATH=BIN_DIR + os.pathsep + os.environ.get("PATH", ""))
    p = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True, env=env)
    if p.returncode != 0:
        tail = redact((p.stdout + p.stderr)[-2000:])
        die(f"{label} failed (exit {p.returncode}):\n{tail}", 1)
    return redact(p.stdout)


def card(a):
    tone = {"info": "Info", "urgent": "Urgent", "celebrate": "Celebrate"}[a["tone"]]
    lines = [f"[{tone}] {a['title']}", a["body"]]
    if a.get("link"):
        lines.append(f"Link: {a.get('linkText') or 'Learn more'} -> {a['link']}")
    when = []
    if a.get("startsAt"):
        when.append("from " + a["startsAt"][:10])
    if a.get("endsAt"):
        last = dt.datetime.fromisoformat(a["endsAt"].replace("Z", "+00:00")) - dt.timedelta(days=1)
        when.append("until " + last.date().isoformat())
    lines.append("Shows: " + (" ".join(when) if when else "now, no end date"))
    return "\n".join(lines)


# ---------- commands ----------

def cmd_list(args):
    pub = load(PUBLISHED, [])
    drafts = []
    if os.path.isdir(DRAFTS):
        for n in sorted(os.listdir(DRAFTS)):
            d = load(os.path.join(DRAFTS, n), None)
            if d and d.get("state") == "draft":
                drafts.append(d)
    if args.json:
        print(json.dumps({"published": [dict(a, status=status(a)) for a in pub], "drafts": drafts}, indent=2))
        return
    print(f"Published ({len(pub)}):" if pub else "Published: none")
    for a in pub:
        print(f"- {a['id']} [{status(a)}, {a['tone']}] {a['title']}  (by {a['updatedBy']}, {a['updatedAt'][:10]})")
    print(f"Drafts waiting for approval ({len(drafts)}):" if drafts else "Drafts waiting for approval: none")
    for d in drafts:
        print(f"- {d['draftId']} {d['announcement']['title']}")


def validate_link(link):
    if not link:
        return None
    if link.startswith("/") or link.startswith("#"):
        return link
    if re.match(r"^https://([a-z0-9-]+\.)*tidepathfamily\.org(/|$)", link):
        return link
    if re.match(r"^https://", link):
        print("WARN: link is not on tidepathfamily.org. Confirm it with Alex.", file=sys.stderr)
        return link
    die("link must be a site path (/donate) or an https URL")


def cmd_preview(args):
    title, body = args.title.strip(), args.body.strip()
    if not title or not body:
        die("title and body are required")
    if len(title) > MAX_TITLE:
        die(f"title is {len(title)} characters, max {MAX_TITLE}")
    if len(body) > MAX_BODY:
        die(f"body is {len(body)} characters, max {MAX_BODY}")
    if args.tone not in TONES:
        die("tone must be one of " + ", ".join(TONES))
    a = {"id": None, "title": title, "body": body, "tone": args.tone}
    link = validate_link(args.link)
    if link:
        a["link"] = link
        a["linkText"] = (args.link_text or "Learn more").strip()
    s, e = parse_day(args.starts), parse_day(args.ends, end=True)
    if s:
        a["startsAt"] = s
    if e:
        a["endsAt"] = e
    if s and e and e <= s:
        die("end date is before start date")
    if e and e <= iso(now()):
        die("end date is in the past")
    t = now()
    draft_id = "d-" + t.strftime("%Y%m%d-%H%M%S")
    save(os.path.join(DRAFTS, draft_id + ".json"),
         {"draftId": draft_id, "state": "draft", "createdAt": iso(t), "announcement": a})
    audit("preview", draftId=draft_id, title=title)
    print(f"PREVIEW {draft_id} (not published)\n")
    print(card(a))
    print(f"\nTo publish, Alex replies \"approve\" in the Website room. "
          f"Then run: announce.py publish {draft_id} --approved-by Alex")


def sync_repo():
    if not os.path.isdir(os.path.join(REPO_DIR, ".git")):
        os.makedirs(STATE, exist_ok=True)
        run(f"git clone --quiet --depth 50 --filter=blob:none --sparse --branch {BRANCH} {REPO_URL} {REPO_DIR}",
            STATE, "git clone")
        run(f"git sparse-checkout set {SUBDIR}", REPO_DIR, "git sparse-checkout")
    run(f"git fetch --quiet --depth 50 origin {BRANCH} && git reset --quiet --hard origin/{BRANCH}",
        REPO_DIR, "git fetch")
    return run("git rev-parse --short HEAD", REPO_DIR, "git rev-parse").strip()


def ensure_hugo():
    """Install the pinned Hugo extended binary into ~/workspace/bin once, SHA256-checked."""
    exe = os.path.join(BIN_DIR, "hugo")
    if os.path.exists(exe):
        p = subprocess.run([exe, "version"], capture_output=True, text=True)
        if f"v{HUGO_VERSION}" in p.stdout:
            return
    arch = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(platform.machine().lower())
    if not arch or platform.system() != "Linux":
        die(f"no pinned Hugo build for {platform.system()} {platform.machine()}", 1)
    name = f"hugo_extended_{HUGO_VERSION}_linux-{arch}.tar.gz"
    base = f"https://github.com/gohugoio/hugo/releases/download/v{HUGO_VERSION}/"
    try:
        sums = urllib.request.urlopen(base + f"hugo_{HUGO_VERSION}_checksums.txt", timeout=60).read().decode()
        want = next(ln.split()[0] for ln in sums.splitlines() if ln.endswith(" " + name))
        data = urllib.request.urlopen(base + name, timeout=300).read()
    except StopIteration:
        die(f"{name} not in the release checksums", 1)
    except Exception as e:  # noqa: BLE001
        die(f"Hugo download failed: {e}", 1)
    got = hashlib.sha256(data).hexdigest()
    if got != want:
        die(f"Hugo checksum mismatch for {name}: got {got}, want {want}", 1)
    os.makedirs(BIN_DIR, exist_ok=True)
    tgz = os.path.join(BIN_DIR, name)
    with open(tgz, "wb") as f:
        f.write(data)
    with tarfile.open(tgz) as t:
        t.extract(t.getmember("hugo"), BIN_DIR)
    os.remove(tgz)
    os.chmod(exe, 0o755)
    print(f"Installed Hugo extended {HUGO_VERSION} ({arch}), sha256 verified", file=sys.stderr)


def build(items):
    """Copy the repo's site dir, write the announcements file, run the build. Returns build dir and sha."""
    sha = sync_repo()
    src = os.path.join(REPO_DIR, SUBDIR)
    if not os.path.isdir(src):
        die(f"site dir {SUBDIR}/ not found in repo", 1)
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    shutil.copytree(src, BUILD_DIR, ignore=shutil.ignore_patterns("node_modules", "public", "dist", ".git"))
    target = os.path.join(BUILD_DIR, ANN_FILE)
    save(target, items)
    if BUILD_CMD.split()[0] == "hugo":
        ensure_hugo()
    run(BUILD_CMD, BUILD_DIR, "build")
    return BUILD_DIR, sha


def deploy(build_dir):
    if not os.environ.get("CLOUDFLARE_API_TOKEN"):
        die("deploy credentials missing (CLOUDFLARE_API_TOKEN not set)", 1)
    run(DEPLOY_CMD, build_dir, "deploy")


def fetch_live():
    url = f"{SITE_URL}/?v={int(time.time())}"
    req = urllib.request.Request(url, headers={"Cache-Control": "no-cache", "User-Agent": "tidepath-website-agent"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def check_live(expect_present, expect_absent):
    try:
        html = fetch_live()
    except Exception as e:  # noqa: BLE001
        return False, f"site fetch failed: {e}"
    missing = [i for i in expect_present if f'data-announcement-id="{i}"' not in html]
    stale = [i for i in expect_absent if f'data-announcement-id="{i}"' in html]
    if missing or stale:
        return False, f"missing on site: {missing or 'none'}; still on site: {stale or 'none'}"
    return True, "live"


def verify(wait, absent=()):
    pub = load(PUBLISHED, [])
    t = iso(now())
    present = [a["id"] for a in pub if status(a, t) == "active"]
    gone = list(absent) + [a["id"] for a in pub if status(a, t) != "active"]
    deadline = time.time() + wait
    while True:
        ok, msg = check_live(present, gone)
        if ok or time.time() >= deadline:
            break
        time.sleep(10)
    print(f"VERIFY {'OK' if ok else 'FAILED'}: {SITE_URL} {msg}. Active: {present or 'none'}")
    return ok


def need_approver(name):
    if not name or name.strip().lower() != "alex":
        die("publish and remove need --approved-by Alex after Alex wrote \"approve\" in the Website room")
    return name.strip()


def cmd_publish(args):
    who = need_approver(args.approved_by)
    path = os.path.join(DRAFTS, args.draft_id + ".json")
    d = load(path, None)
    if not d:
        die("no draft " + args.draft_id)
    if d.get("state") != "draft":
        die(f"draft {args.draft_id} is already {d.get('state')}")
    pub = load(PUBLISHED, [])
    a = dict(d["announcement"])
    a["id"] = "a-" + now().strftime("%Y%m%d") + "-" + slug(a["title"])
    if any(x["id"] == a["id"] for x in pub):
        a["id"] += "-" + now().strftime("%H%M%S")
    a["updatedAt"], a["updatedBy"] = iso(now()), who
    new = pub + [a]
    build_dir, sha = build(new)
    deploy(build_dir)
    save(PUBLISHED, new)
    d.update(state="published", announcementId=a["id"], approvedBy=who, publishedAt=a["updatedAt"], repoSha=sha)
    save(path, d)
    audit("publish", draftId=args.draft_id, id=a["id"], approvedBy=who, repoSha=sha)
    print(f"PUBLISHED {a['id']} (site built from repo {sha})")
    sys.exit(0 if verify(args.wait) else 1)


def cmd_remove(args):
    who = need_approver(args.approved_by)
    pub = load(PUBLISHED, [])
    if not any(a["id"] == args.id for a in pub):
        die("no published announcement " + args.id)
    new = [a for a in pub if a["id"] != args.id]
    build_dir, sha = build(new)
    deploy(build_dir)
    save(PUBLISHED, new)
    audit("remove", id=args.id, approvedBy=who, repoSha=sha)
    print(f"REMOVED {args.id} (site built from repo {sha})")
    sys.exit(0 if verify(args.wait, absent=[args.id]) else 1)


def cmd_build(args):
    build_dir, sha = build(load(PUBLISHED, []))
    print(f"BUILD OK from repo {sha} in {build_dir} (not deployed)")


def cmd_verify(args):
    sys.exit(0 if verify(args.wait) else 1)


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("list")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_list)
    s = sub.add_parser("preview")
    s.add_argument("--title", required=True)
    s.add_argument("--body", required=True)
    s.add_argument("--link")
    s.add_argument("--link-text")
    s.add_argument("--tone", default="info")
    s.add_argument("--starts")
    s.add_argument("--ends")
    s.set_defaults(fn=cmd_preview)
    s = sub.add_parser("publish")
    s.add_argument("draft_id")
    s.add_argument("--approved-by", required=True)
    s.add_argument("--wait", type=int, default=90)
    s.set_defaults(fn=cmd_publish)
    s = sub.add_parser("remove")
    s.add_argument("id")
    s.add_argument("--approved-by", required=True)
    s.add_argument("--wait", type=int, default=90)
    s.set_defaults(fn=cmd_remove)
    s = sub.add_parser("build")
    s.set_defaults(fn=cmd_build)
    s = sub.add_parser("verify")
    s.add_argument("--wait", type=int, default=0)
    s.set_defaults(fn=cmd_verify)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
