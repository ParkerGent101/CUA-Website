#!/usr/bin/env python3
"""Coming Up Aces — site content tool.

Edits shows.json / videos.json and (optionally) commits + pushes, which triggers
the GitHub Actions deploy to Cloud Run. This is the workhorse behind
scripts/cua-update.ps1; it exists as Python rather than PowerShell because
PowerShell 5.1's ConvertTo-Json cannot round-trip these files — it reindents to
4 spaces, escapes '&' to \\u0026, and mangles the em-dashes in the Local Fest
entries to mojibake. json.dumps(indent=2, ensure_ascii=False) is byte-identical
to what's committed.

Every command is fully non-interactive so an agent can drive it the same way a
person does. Nothing is pushed unless you pass --push.

  python scripts/cua.py list
  python scripts/cua.py add-show --date 2026-11-01 --event "Fall Show" \
      --venue "Georges Majestic" --city "Fayetteville, AR" --doors 20:00 --time 21:00
  python scripts/cua.py edit-show --match "Georges" --tickets https://...
  python scripts/cua.py remove-show --index 2
  python scripts/cua.py add-video --title "Live at Georges" --url https://youtu.be/XXXX
  python scripts/cua.py push -m "add November show"
  python scripts/cua.py status
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

# The Windows console defaults to cp1252, which can't print the em-dashes in the
# Local Fest entries. Only affects display — files are always written as UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
SHOWS_FILE = ROOT / "shows.json"
VIDEOS_FILE = ROOT / "videos.json"
LIVE_URL = "https://comingupaces.net"
GH_REPO = "ParkerGent101/CUA-Website"

# Fields app.js actually reads off a show (see app.js — 'event' is stored for
# commit messages and the EPK, the card itself renders venue/city/doors/time).
SHOW_FIELDS = ["date", "event", "venue", "city", "doors", "time", "tickets", "notes"]


# ── io ────────────────────────────────────────────────────────────────────────

def load(path: Path) -> list:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    data = json.loads(text)
    if not isinstance(data, list):
        die(f"{path.name} is not a JSON array.")
    return data


def save(path: Path, data: list, dry_run: bool = False) -> None:
    # indent=2 / ensure_ascii=False / no trailing newline == the committed format.
    out = json.dumps(data, indent=2, ensure_ascii=False)
    if dry_run:
        print(f"--- {path.name} (dry run, not written) ---")
        print(out)
        return
    path.write_text(out, encoding="utf-8", newline="\n")


def die(msg: str, code: int = 1):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


# ── validation ────────────────────────────────────────────────────────────────

def valid_date(s: str) -> str:
    try:
        return dt.date.fromisoformat(s).isoformat()
    except ValueError:
        die(f"date must be YYYY-MM-DD, got {s!r}")


def valid_time(s: str, label: str) -> str:
    if s == "":
        return ""
    if not re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", s):
        die(f"{label} must be 24-hour HH:MM (the site formats it to 12-hour), got {s!r}")
    h, m = s.split(":")
    return f"{int(h):02d}:{m}"


def valid_video_url(url: str) -> str:
    """app.js's toEmbedUrl() silently drops anything it can't embed, so a bad URL
    means the video just never appears. Refuse it here instead."""
    ok = (
        re.search(r"(?:youtube\.com/watch\?v=|youtu\.be/)[A-Za-z0-9_-]+", url)
        or "youtube.com/embed/" in url
        or re.search(r"drive\.google\.com/file/d/[^/]+", url)
    )
    if not ok:
        die(
            f"unsupported video URL {url!r}.\n"
            "  Supported: youtube.com/watch?v=..., youtu.be/..., "
            "youtube.com/embed/..., drive.google.com/file/d/.../view"
        )
    return url


# ── selection ─────────────────────────────────────────────────────────────────

def resolve(items: list, index: int | None, match: str | None, fields: list[str], what: str) -> int:
    """Pick exactly one item by --index or by case-insensitive --match across fields."""
    if index is not None:
        if not 0 <= index < len(items):
            die(f"no {what} at index {index} (there are {len(items)}); run 'list' to see them")
        return index
    if not match:
        die(f"pass --index N or --match TEXT to pick a {what}")
    needle = match.lower()
    hits = [
        i for i, it in enumerate(items)
        if any(needle in str(it.get(f, "")).lower() for f in fields)
    ]
    if not hits:
        die(f"no {what} matching {match!r}; run 'list' to see them")
    if len(hits) > 1:
        lines = "\n".join(f"  [{i}] {summarize(items[i])}" for i in hits)
        die(f"{match!r} matches {len(hits)} {what}s — use --index:\n{lines}")
    return hits[0]


def summarize(item: dict) -> str:
    if "url" in item:                                    # a video
        return f"{item.get('title', '?')} — {item.get('url', '')}"
    line = " — ".join(b for b in [item.get("date", "?"), item.get("event", "")] if b)
    tail = ", ".join(b for b in [item.get("venue", ""), item.get("city", "")] if b)
    return f"{line} @ {tail}" if tail else line


# ── commands ──────────────────────────────────────────────────────────────────

def cmd_list(args):
    shows = sorted(load(SHOWS_FILE), key=lambda s: s.get("date", ""))
    today = dt.date.today().isoformat()
    print(f"Shows ({len(shows)}):")
    if not shows:
        print("  (none)")
    for i, s in enumerate(shows):
        past = "  (past)" if s.get("date", "") < today else ""
        when = " · ".join(
            x for x in [
                f"doors {s['doors']}" if s.get("doors") else "",
                f"show {s['time']}" if s.get("time") else "",
            ] if x
        )
        print(f"  [{i}] {summarize(s)}{past}")
        detail = " | ".join(x for x in [when, s.get("notes", ""), s.get("tickets", "")] if x)
        if detail:
            print(f"       {detail}")

    videos = load(VIDEOS_FILE)
    print(f"\nVideos ({len(videos)}):")
    if not videos:
        print("  (none)")
    for i, v in enumerate(videos):
        print(f"  [{i}] {summarize(v)}")


def cmd_add_show(args):
    shows = load(SHOWS_FILE)
    show = {
        "date": valid_date(args.date),
        "event": args.event.strip(),
        "venue": args.venue.strip(),
        "city": args.city.strip(),
        "doors": valid_time(args.doors, "--doors"),
        "time": valid_time(args.time, "--time"),
        "tickets": args.tickets.strip(),
        "notes": args.notes.strip(),
    }
    # Drop empty doors/time so entries without them stay as clean as the ones
    # already committed (app.js treats missing and empty identically).
    show = {k: v for k, v in show.items() if v != "" or k in ("tickets", "notes")}
    dupe = next(
        (s for s in shows
         if s.get("date") == show["date"] and s.get("venue", "").lower() == show["venue"].lower()),
        None,
    )
    if dupe and not args.force:
        die(f"a show at {show['venue']} on {show['date']} already exists — use --force to add anyway")
    shows.append(show)
    shows.sort(key=lambda s: s.get("date", ""))
    save(SHOWS_FILE, shows, args.dry_run)
    print(f"added: {summarize(show)}")
    finish(args, f"add show: {show['event']} ({show['date']})")


def cmd_edit_show(args):
    shows = load(SHOWS_FILE)
    i = resolve(shows, args.index, args.match, ["event", "venue", "city", "date"], "show")
    changes = {}
    for f in SHOW_FIELDS:
        v = getattr(args, f, None)
        if v is None:
            continue
        if f == "date":
            v = valid_date(v)
        elif f in ("doors", "time"):
            v = valid_time(v, f"--{f}")
        changes[f] = v.strip() if isinstance(v, str) else v
    if not changes:
        die("nothing to change — pass at least one of " + ", ".join(f"--{f}" for f in SHOW_FIELDS))
    before = summarize(shows[i])
    shows[i].update(changes)
    shows.sort(key=lambda s: s.get("date", ""))
    save(SHOWS_FILE, shows, args.dry_run)
    print(f"edited: {before}\n    ->  {summarize(shows[i])}")
    print("  " + ", ".join(f"{k}={v!r}" for k, v in changes.items()))
    finish(args, f"edit show: {shows[i].get('event', '')} ({shows[i].get('date', '')})")


def cmd_remove_show(args):
    shows = load(SHOWS_FILE)
    i = resolve(shows, args.index, args.match, ["event", "venue", "city", "date"], "show")
    gone = shows.pop(i)
    save(SHOWS_FILE, shows, args.dry_run)
    print(f"removed: {summarize(gone)}")
    finish(args, f"remove show: {gone.get('event', '')} ({gone.get('date', '')})")


def cmd_add_video(args):
    videos = load(VIDEOS_FILE)
    video = {
        "title": args.title.strip(),
        "url": valid_video_url(args.url.strip()),
        "date": valid_date(args.date) if args.date else dt.date.today().isoformat(),
    }
    videos.append(video)
    save(VIDEOS_FILE, videos, args.dry_run)
    print(f"added: {summarize(video)}")
    finish(args, f"add video: {video['title']}")


def cmd_remove_video(args):
    videos = load(VIDEOS_FILE)
    i = resolve(videos, args.index, args.match, ["title", "url", "date"], "video")
    gone = videos.pop(i)
    save(VIDEOS_FILE, videos, args.dry_run)
    print(f"removed: {summarize(gone)}")
    finish(args, f"remove video: {gone.get('title', '')}")


def cmd_push(args):
    do_push(args.message or "Update site content")


def cmd_status(args):
    print("==> Recent deploys")
    try:
        subprocess.run(
            ["gh", "run", "list", "--repo", GH_REPO, "--limit", "5"],
            cwd=ROOT, check=False,
        )
    except FileNotFoundError:
        print(f"  (install the GitHub CLI for this) https://github.com/{GH_REPO}/actions")
    print(f"\n==> Pinging {LIVE_URL}")
    try:
        with urllib.request.urlopen(LIVE_URL, timeout=15) as r:
            print(f"  HTTP {r.status} — site is live.")
    except Exception as e:
        print(f"  could not reach it: {e}")


# ── git ───────────────────────────────────────────────────────────────────────

def git(*a, check=True):
    return subprocess.run(["git", *a], cwd=ROOT, check=check,
                          capture_output=True, text=True)


def do_push(message: str):
    # Content-aware, not 'git status': this repo has core.autocrlf=true while the
    # JSON files are LF on disk, so status reports them modified when nothing changed.
    unchanged = git("diff", "--quiet", "--", "shows.json", "videos.json",
                    check=False).returncode == 0
    if unchanged:
        print("nothing to commit.")
        return
    git("add", "shows.json", "videos.json")
    staged = git("diff", "--cached", "--name-only").stdout.strip()
    if not staged:
        print("no shows.json/videos.json changes staged — nothing to push.")
        return
    git("commit", "-m", message)
    git("push", "origin", "main")
    print(f"pushed: {message}")
    print(f"  GitHub Actions is deploying; {LIVE_URL} updates in ~1 min.")
    print(f"  check with: python scripts/cua.py status")


def finish(args, message: str):
    """Push if asked, otherwise tell the user exactly how to."""
    if args.dry_run:
        print("(dry run — nothing written, nothing pushed)")
        return
    if args.push:
        do_push(args.message or message)
    else:
        print(f'  not pushed. to publish: python scripts/cua.py push -m "{message}"')


# ── cli ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        prog="cua.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def with_common(sp, pushable=True):
        if pushable:
            sp.add_argument("--push", action="store_true",
                            help="commit and push (deploys the live site)")
            sp.add_argument("-m", "--message", default="", help="commit message")
            sp.add_argument("--dry-run", action="store_true",
                            help="print the result without writing anything")
        return sp

    def with_picker(sp, what):
        g = sp.add_mutually_exclusive_group()
        g.add_argument("--index", type=int, help=f"{what} index from 'list'")
        g.add_argument("--match", help=f"substring identifying one {what}")
        return sp

    sp = sub.add_parser("list", help="show every show and video with its index")
    sp.set_defaults(func=cmd_list)

    sp = with_common(sub.add_parser("add-show", help="add a show"))
    sp.add_argument("--date", required=True, help="YYYY-MM-DD")
    sp.add_argument("--event", required=True)
    sp.add_argument("--venue", required=True)
    sp.add_argument("--city", required=True, help='e.g. "Fayetteville, AR"')
    sp.add_argument("--doors", default="", help="24-hour HH:MM")
    sp.add_argument("--time", default="", help="24-hour HH:MM (set time)")
    sp.add_argument("--tickets", default="")
    sp.add_argument("--notes", default="")
    sp.add_argument("--force", action="store_true", help="allow a duplicate date+venue")
    sp.set_defaults(func=cmd_add_show)

    sp = with_picker(with_common(sub.add_parser("edit-show", help="change fields on one show")), "show")
    for f in SHOW_FIELDS:
        sp.add_argument(f"--{f}", default=None)
    sp.set_defaults(func=cmd_edit_show)

    sp = with_picker(with_common(sub.add_parser("remove-show", help="delete one show")), "show")
    sp.set_defaults(func=cmd_remove_show)

    sp = with_common(sub.add_parser("add-video", help="add a video"))
    sp.add_argument("--title", required=True)
    sp.add_argument("--url", required=True, help="YouTube or Google Drive link")
    sp.add_argument("--date", default="", help="YYYY-MM-DD (defaults to today)")
    sp.set_defaults(func=cmd_add_video)

    sp = with_picker(with_common(sub.add_parser("remove-video", help="delete one video")), "video")
    sp.set_defaults(func=cmd_remove_video)

    sp = sub.add_parser("push", help="commit + push whatever is already edited")
    sp.add_argument("-m", "--message", default="")
    sp.set_defaults(func=cmd_push)

    sp = sub.add_parser("status", help="recent deploys + a ping of the live site")
    sp.set_defaults(func=cmd_status)

    args = p.parse_args()
    for attr in ("push", "dry_run", "message", "index", "match"):
        if not hasattr(args, attr):
            setattr(args, attr, None if attr in ("index", "match") else False)
    args.func(args)


if __name__ == "__main__":
    main()
