#!/usr/bin/env python3
"""Read-only view of the public Tidepath site repo.

Usage:
  repo.py sync                       # clone or update the read-only copy
  repo.py tree [PATH]                # files under PATH (default: the site dir)
  repo.py cat PATH [--lines A:B]     # print a file
  repo.py grep PATTERN [PATH]        # where is X on the site (case-insensitive)
  repo.py log [-n N] [PATH]          # what changed: recent commits
  repo.py show SHA                   # files changed in one commit, with stats

Uses an anonymous HTTPS clone of a public repo. It never commits or pushes.
Environment: REPO_URL [https://github.com/ethanpierce/donor-engagement-2026],
REPO_BRANCH [main], SITE_SUBDIR [website].
"""
import argparse
import os
import subprocess
import sys

WS = os.environ.get("AUTOWORKER_WORKSPACE") or os.environ.get("AUTOWORKER_HUB_WORKSPACE") \
    or os.path.expanduser("~/workspace")
REPO_DIR = os.path.join(WS, "website", "repo")
REPO_URL = os.environ.get("REPO_URL", "https://github.com/ethanpierce/donor-engagement-2026")
BRANCH = os.environ.get("REPO_BRANCH", "main")
SUBDIR = os.environ.get("SITE_SUBDIR", "website")


def git(*args, cwd=REPO_DIR, check=True):
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and p.returncode != 0:
        print("ERROR: git " + " ".join(args[:2]) + ": " + p.stderr.strip()[-500:], file=sys.stderr)
        sys.exit(1)
    return p.stdout


def sync(quiet=False):
    if not os.path.isdir(os.path.join(REPO_DIR, ".git")):
        os.makedirs(os.path.dirname(REPO_DIR), exist_ok=True)
        git("clone", "--quiet", "--depth", "50", "--filter=blob:none", "--sparse", "--branch", BRANCH,
            REPO_URL, REPO_DIR, cwd=os.path.dirname(REPO_DIR))
        git("sparse-checkout", "set", SUBDIR)
    git("fetch", "--quiet", "--depth", "50", "origin", BRANCH)
    git("reset", "--quiet", "--hard", "origin/" + BRANCH)
    if not quiet:
        print("SYNC OK " + git("log", "-1", "--format=%h %cs %s").strip())


def ensure():
    if not os.path.isdir(os.path.join(REPO_DIR, ".git")):
        sync(quiet=True)


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sync")
    s = sub.add_parser("tree")
    s.add_argument("path", nargs="?", default=SUBDIR)
    s = sub.add_parser("cat")
    s.add_argument("path")
    s.add_argument("--lines")
    s = sub.add_parser("grep")
    s.add_argument("pattern")
    s.add_argument("path", nargs="?", default=SUBDIR)
    s = sub.add_parser("log")
    s.add_argument("-n", type=int, default=10)
    s.add_argument("path", nargs="?")
    s = sub.add_parser("show")
    s.add_argument("sha")
    a = p.parse_args()

    if a.cmd == "sync":
        return sync()
    ensure()
    if a.cmd == "tree":
        out = git("ls-tree", "-r", "--name-only", "HEAD", "--", a.path)
        print(out.strip() or f"(nothing under {a.path})")
    elif a.cmd == "cat":
        text = git("show", "HEAD:" + a.path.strip("/"))
        if a.lines:
            lo, _, hi = a.lines.partition(":")
            rows = text.splitlines()
            lo = max(int(lo or 1), 1)
            hi = int(hi or len(rows))
            text = "\n".join(f"{i}: {r}" for i, r in enumerate(rows[lo - 1:hi], lo))
        print(text)
    elif a.cmd == "grep":
        out = git("grep", "-n", "-i", "-I", "-e", a.pattern, "HEAD", "--", a.path, check=False)
        lines = [ln.split(":", 1)[1] if ln.startswith("HEAD:") else ln for ln in out.splitlines()]
        print("\n".join(lines[:200]) or "no match")
    elif a.cmd == "log":
        args = ["log", f"-{a.n}", "--format=%h %cs %an: %s", "--stat=100", "--stat-count=8"]
        if a.path:
            args += ["--", a.path]
        print(git(*args).strip())
    elif a.cmd == "show":
        print(git("show", "--stat=100", "--format=%h %cs %an%n%s%n%b", a.sha).strip())


if __name__ == "__main__":
    main()
