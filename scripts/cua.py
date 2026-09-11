#!/usr/bin/env python3
"""Coming Up Aces — site content tool.

Edits shows.json / videos.json and (optionally) commits + pushes, which triggers
the GitHub Actions deploy to Cloud Run. This is the workhorse behind
scripts/cua-update.ps1; it exists as Python rather than PowerShell because
PowerShell 5.1's ConvertTo-Json cannot round-trip these files — it reindents to
4 spaces, escapes '&' to \\u0026, and mangles any em-dash in an
event name to mojibake. json.dumps(indent=2, ensure_ascii=False) is byte-identical
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
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# The Windows console defaults to cp1252, which can't print em-dashes in event
# names. Only affects display — files are always written as UTF-8.
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

# Fields app.js actually reads off a show. 'event' is the card's headline as of the
# 2026-09 rebuild — public-facing copy, not just a commit-message label.
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
    # "whatever is already edited" — shows, videos, and a synced gallery.
    do_push(args.message or "Update site content", CONTENT_PATHS + GALLERY_PATHS)


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


# ── photos ────────────────────────────────────────────────────────────────────
#
# sync-photos pulls the curated Drive folder — the one Parker drops
# website-worthy shots into — optimizes each image, and writes gallery.json for
# the hero slideshow. The Drive folder is the entire publish gate: a photo is on
# the site because it's in that folder, and gone because it isn't.
#
# Everything here is deliberately deploy-time, not runtime: nginx serves plain
# WebP files out of the container, so the live site never talks to Drive and a
# Drive outage can't blank the hero.

GALLERY_FILE = ROOT / "gallery.json"
GALLERY_DIR = ROOT / "photos" / "gallery"
GALLERY_PATHS = ["gallery.json", "photos/gallery", "index.html"]

# Widths for the hero srcset. Sources are only ever scaled down, never up.
SLIDE_WIDTHS = [1280, 1920, 2560]
WEBP_QUALITY = 82
LQIP_WIDTH = 24

# Ceilings for optimize-stills. The hero and press photos go full-bleed, so they
# get the wide cap; the `member-*` portraits only ever render inside a ~300px
# band card, where 1800px is several times more pixels than any screen asks for.
STILL_MAX_WIDTH = 1800
MEMBER_MAX_WIDTH = 900

DRIVE_API = "https://www.googleapis.com/drive/v3/files"
# Pillow can't open HEIC without pillow-heif, and iPhones shoot HEIC by default.
HEIC_EXT = {".heic", ".heif"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"} | HEIC_EXT


def read_dotenv() -> dict:
    """Tiny .env reader — the Drive key lives there and .env is gitignored."""
    env = {}
    f = ROOT / ".env"
    if not f.exists():
        return env
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip("'\"")
    return env


def drive_folder_id(raw: str) -> str:
    """Accept a folder ID or any of the URL shapes Drive hands out when sharing."""
    m = re.search(r"/folders/([A-Za-z0-9_-]+)", raw) or re.search(r"[?&]id=([A-Za-z0-9_-]+)", raw)
    return m.group(1) if m else raw.strip()


def drive_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def drive_list(folder: str, key: str) -> list[dict]:
    """Every non-trashed file in one folder, ordered by name."""
    files, token = [], None
    while True:
        q = urllib.parse.urlencode({
            "q": f"'{folder}' in parents and trashed = false",
            "key": key,
            "fields": "nextPageToken,files(id,name,mimeType,md5Checksum,size)",
            "pageSize": "1000",
            "orderBy": "name_natural",
            **({"pageToken": token} if token else {}),
        })
        try:
            page = json.loads(drive_get(f"{DRIVE_API}?{q}"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:400]
            die(
                f"Drive returned HTTP {e.code} listing folder {folder!r}.\n"
                f"  {body}\n"
                "  Check: the folder is shared 'Anyone with the link — Viewer', the API key\n"
                "  has the Drive API enabled, and any key restrictions allow this machine."
            )
        except urllib.error.URLError as e:
            die(f"could not reach the Drive API: {e.reason}")
        files.extend(page.get("files", []))
        token = page.get("nextPageToken")
        if not token:
            break
    return files


def gather_sources(args) -> list[dict]:
    """Normalize either source into {key, name, bytes} records, ordered by name.

    Ordering is by filename so the slideshow sequence is controlled by renaming
    in Drive — prefix with 01-, 02- to pin an order.
    """
    if args.from_local:
        d = Path(args.from_local).expanduser().resolve()
        if not d.is_dir():
            die(f"--from-local {d} is not a directory")
        found = [p for p in d.iterdir()
                 if p.is_file() and p.suffix.lower() in IMAGE_EXT
                 and p.stem.lower() != "og"]          # og.jpg is a generated artifact
        # optimize-stills leaves hero.webp next to hero.JPG, and both would come
        # through as separate slides of the same photograph. One per stem, and
        # prefer the original over a derivative to avoid re-encoding twice.
        rank = {".webp": 1}
        best: dict[str, Path] = {}
        for p in found:
            k = p.stem.lower()
            if k not in best or rank.get(p.suffix.lower(), 0) < rank.get(best[k].suffix.lower(), 0):
                best[k] = p
        picks = sorted(best.values(), key=lambda p: p.name.lower())
        if not picks:
            die(f"no images in {d} (looked for {', '.join(sorted(IMAGE_EXT))})")
        if len(found) != len(picks):
            print(f"    ({len(found) - len(picks)} derivative(s) skipped — one slide per photo)")
        print(f"==> {len(picks)} image(s) from {d}")
        return [{"key": f"local:{p.name}", "name": p.name, "bytes": p.read_bytes()} for p in picks]

    env = read_dotenv()
    folder = args.folder or env.get("CUA_DRIVE_FOLDER", "")
    key = args.api_key or env.get("CUA_DRIVE_API_KEY", "")
    if not folder or not key:
        die(
            "need a Drive folder and an API key.\n"
            "  Put them in .env (gitignored) as:\n"
            "    CUA_DRIVE_FOLDER=<folder id or share link>\n"
            "    CUA_DRIVE_API_KEY=<key with the Drive API enabled>\n"
            "  or pass --folder/--api-key, or bootstrap offline with --from-local DIR."
        )
    folder = drive_folder_id(folder)
    listing = drive_list(folder, key)
    picks = [f for f in listing
             if f.get("mimeType", "").startswith("image/")
             or Path(f.get("name", "")).suffix.lower() in IMAGE_EXT]
    if not picks:
        die(f"no images in Drive folder {folder} ({len(listing)} file(s) there, none of them images)")
    picks.sort(key=lambda f: f.get("name", "").lower())
    print(f"==> {len(picks)} image(s) in the Drive folder")
    out = []
    for f in picks:
        print(f"    downloading {f['name']}")
        out.append({
            "key": f["id"],
            "name": f["name"],
            "bytes": drive_get(f"{DRIVE_API}/{f['id']}?alt=media&key={key}"),
        })
    return out


# Filename words that describe the file rather than the picture. "press-1.JPG"
# yielding alt="press 1" is worse than an honest generic, so these drop out.
GENERIC_WORDS = {
    "hero", "press", "band", "cua", "aces", "photo", "photos", "img", "image",
    "dsc", "dscn", "pic", "final", "edit", "edited", "copy", "web", "website",
    "slide", "shot", "export", "raw", "jpg", "jpeg", "png", "orig", "original",
}


def default_alt(name: str) -> str:
    """Derive alt from the filename, but only when the filename says something.

    Hand-written alt in gallery.json always wins and survives re-syncs.
    """
    words = [w for w in re.split(r"[\s._-]+", Path(name).stem) if w]
    words = [w for w in words
             if not w.isdigit() and len(w) >= 3 and w.lower() not in GENERIC_WORDS]
    return f"Coming Up Aces — {' '.join(words)}" if words else "Coming Up Aces live"


def build_slide(src: dict, existing: dict, dry_run: bool) -> dict | None:
    """One source image -> WebP derivatives + a manifest entry. None if unusable."""
    import base64
    import hashlib
    import io
    from PIL import Image, ImageFilter, ImageOps, ImageStat, UnidentifiedImageError

    ext = Path(src["name"]).suffix.lower()
    try:
        im = Image.open(io.BytesIO(src["bytes"]))
        im.load()
    except UnidentifiedImageError:
        if ext in HEIC_EXT:
            print(f"    !! skipped {src['name']}: HEIC needs `pip install pillow-heif`, or "
                  "re-save it as JPEG in Drive")
        else:
            print(f"    !! skipped {src['name']}: not an image Pillow can read")
        return None
    except Exception as e:
        print(f"    !! skipped {src['name']}: {e}")
        return None

    # exif_transpose first or phone photos land sideways; the re-save then drops
    # all EXIF, which also strips camera GPS tags off the band's public photos.
    im = ImageOps.exif_transpose(im).convert("RGB")
    w, h = im.size
    digest = hashlib.sha256(src["bytes"]).hexdigest()[:10]
    base = f"photos/gallery/slide-{digest}"

    widths = [x for x in SLIDE_WIDTHS if x <= w] or [w]
    if not dry_run:
        GALLERY_DIR.mkdir(parents=True, exist_ok=True)
        for tw in widths:
            out = GALLERY_DIR / f"slide-{digest}-{tw}.webp"
            if out.exists():
                continue                                        # content-hashed: same bytes, same file
            resized = im if tw == w else im.resize(
                (tw, max(1, round(h * tw / w))), Image.LANCZOS)
            resized.save(out, "WEBP", quality=WEBP_QUALITY, method=6)

    # Inline blur-up placeholder so a slide never flashes black while it decodes.
    thumb = im.resize((LQIP_WIDTH, max(1, round(h * LQIP_WIDTH / w))), Image.LANCZOS)
    thumb = thumb.filter(ImageFilter.GaussianBlur(1))
    buf = io.BytesIO()
    thumb.save(buf, "WEBP", quality=50, method=6)
    lqip = "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

    prev = existing.get(src["key"], {})
    return {
        "id": src["key"],
        "name": src["name"],
        "src": base,
        "widths": widths,
        "width": w,
        "height": h,
        # Mean luminance 0–255. Bar and stage shots come in very dark, and a
        # hero photo that reads as black defeats the slideshow — this is what
        # the sync's dark-photo warning checks.
        "lum": round(ImageStat.Stat(im.convert("L")).mean[0], 1),
        # Hand-edited alt text survives every re-sync — otherwise a sync silently
        # undoes the accessibility work.
        "alt": prev.get("alt") or default_alt(src["name"]),
        "lqip": lqip,
    }


HERO_MARKERS = [
    # (start marker, end marker, builder) — rewritten in place in index.html so
    # the first slide is in the HTML and preloaded, not waiting on gallery.json.
    ("<!-- CUA:HERO-PRELOAD:START -->", "<!-- CUA:HERO-PRELOAD:END -->", "preload"),
    ("<!-- CUA:HERO-FIRST:START -->", "<!-- CUA:HERO-FIRST:END -->", "first"),
]


def srcset_for(slide: dict) -> str:
    return ", ".join(f"{slide['src']}-{w}.webp {w}w" for w in slide["widths"])


def bake_hero(slides: list[dict], dry_run: bool) -> None:
    """Put the first slide straight into index.html.

    The hero photo is the page's largest contentful paint. If it only appears
    after gallery.json round-trips, the redesign measurably feels slower than
    what it replaced — so slide one ships in the HTML and JS only takes over the
    rotation.
    """
    page = ROOT / "index.html"
    if not page.exists() or not slides:
        return
    html = page.read_text(encoding="utf-8")
    first = slides[0]
    widest = max(first["widths"])
    blocks = {
        "preload": (
            f'<link rel="preload" as="image" href="{first["src"]}-{widest}.webp" '
            f'imagesrcset="{srcset_for(first)}" imagesizes="100vw" fetchpriority="high">'
        ),
        # The blurred placeholder goes inline as a background so there's no flash
        # of black while a ~300KB full-bleed WebP decodes. It's a data URI, so it
        # costs no request and is painted with the HTML.
        "first": (
            f'<img class="slide is-active" src="{first["src"]}-{widest}.webp" '
            f'srcset="{srcset_for(first)}" sizes="100vw" '
            f'alt="{first["alt"]}" fetchpriority="high" decoding="async"'
            + (f' style="background-image:url({first["lqip"]});'
               'background-size:cover;background-position:center 32%"'
               if first.get("lqip") else "")
            + ">"
        ),
    }
    out, missing = html, []
    for start, end, kind in HERO_MARKERS:
        if start not in out or end not in out:
            missing.append(start)
            continue
        head, rest = out.split(start, 1)
        _, tail = rest.split(end, 1)
        out = f"{head}{start}\n    {blocks[kind]}\n    {end}{tail}"
    if missing:
        print(f"    !! index.html is missing {', '.join(missing)} — hero not baked in")
    if out != html and not dry_run:
        page.write_text(out, encoding="utf-8", newline="\n")
        print("    baked the first slide into index.html")


OG_SIZE = (1200, 630)


def write_og(src_bytes: bytes, dry_run: bool) -> None:
    """Regenerate photos/og.jpg — the image link previews use.

    Deliberately a stable filename and a JPEG: the meta tag in index.html can't
    chase content-hashed names, and some link scrapers still won't take WebP.
    """
    import io
    from PIL import Image, ImageOps

    if dry_run:
        return
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(src_bytes))).convert("RGB")
    # Cover-crop to 1200x630 rather than squash it.
    im = ImageOps.fit(im, OG_SIZE, Image.LANCZOS, centering=(0.5, 0.32))
    out = ROOT / "photos" / "og.jpg"
    im.save(out, "JPEG", quality=84, optimize=True, progressive=True)
    print(f"    wrote {out.relative_to(ROOT).as_posix()} ({out.stat().st_size // 1024} KB)")


def cmd_optimize_stills(args):
    """Convert the fixed-name photos (hero, press-N, …) to WebP.

    Separate from sync-photos because these are referenced by name in
    index.html and epk.html, so they can't have content-hashed filenames. Run it
    after replacing any of the JPGs in photos/.
    """
    from PIL import Image, ImageOps

    srcs = sorted(
        p for p in (ROOT / "photos").iterdir()
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png"}
        and p.stem != "og"
    )
    if not srcs:
        die("no JPG/PNG files directly in photos/ to optimize")

    before = after = 0
    for p in srcs:
        im = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
        w, h = im.size
        cap = MEMBER_MAX_WIDTH if p.stem.startswith("member-") else STILL_MAX_WIDTH
        if w > cap:
            im = im.resize((cap, round(h * cap / w)), Image.LANCZOS)
        out = p.with_suffix(".webp")
        before += p.stat().st_size
        if args.dry_run:
            print(f"  would write {out.name} from {p.name} ({w}x{h})")
            continue
        im.save(out, "WEBP", quality=WEBP_QUALITY, method=6)
        after += out.stat().st_size
        print(f"  {p.name} -> {out.name}  "
              f"{p.stat().st_size // 1024} KB -> {out.stat().st_size // 1024} KB")
    if not args.dry_run:
        print(f"\n{len(srcs)} file(s): {before / 1_048_576:.1f} MB -> {after / 1_048_576:.1f} MB")
        print("  the .JPG originals are kept as sources; the pages reference the .webp")
    finish(args, f"optimize {len(srcs)} still photo(s)", paths=["photos"])


def cmd_sync_photos(args):
    sources = gather_sources(args)
    existing = {s["id"]: s for s in load(GALLERY_FILE) if isinstance(s, dict) and "id" in s}

    slides = []
    for src in sources:
        slide = build_slide(src, existing, args.dry_run)
        if slide:
            slides.append(slide)
    if not slides:
        die("no usable images — nothing written")
    for i, s in enumerate(slides):
        s["order"] = i

    # save()'s dry-run dumps the whole file, and every slide carries a base64
    # placeholder — unreadable. Summarize instead.
    if args.dry_run:
        print(f"--- gallery.json (dry run, not written) — {len(slides)} slide(s) ---")
        for s in slides:
            print(f"  [{s['order']}] {s['name']} -> {Path(s['src']).name} {s['widths']}")
    else:
        save(GALLERY_FILE, slides)

    # Prune derivatives whose source left the folder. This is what makes pulling
    # a photo out of Drive actually remove it from the site.
    keep = {f"{Path(s['src']).name}-{w}.webp" for s in slides for w in s["widths"]}
    stale = [p for p in GALLERY_DIR.glob("slide-*.webp")] if GALLERY_DIR.exists() else []
    stale = [p for p in stale if p.name not in keep]
    for p in stale:
        print(f"    pruning {p.name}")
        if not args.dry_run:
            p.unlink()

    bake_hero(slides, args.dry_run)

    # og.jpg tracks slide one, so the link preview matches what the site opens on.
    lead = next((s for s in sources if s["key"] == slides[0]["id"]), None)
    if lead:
        write_og(lead["bytes"], args.dry_run)

    total = sum(
        (GALLERY_DIR / f"{Path(s['src']).name}-{w}.webp").stat().st_size
        for s in slides for w in s["widths"]
        if (GALLERY_DIR / f"{Path(s['src']).name}-{w}.webp").exists()
    )
    print(f"\n{len(slides)} slide(s), {len(stale)} pruned, {total / 1_048_576:.1f} MB on disk")

    # A full-bleed hero is a wide letterbox. Portrait sources get cropped to a
    # narrow vertical slice of themselves, and anything under 1920px wide goes
    # soft when stretched across a desktop viewport. Worth saying out loud —
    # it's the main thing that decides whether the slideshow looks good.
    portrait = [s for s in slides if s["height"] > s["width"]]
    lowres = [s for s in slides if s["width"] < 1920]
    dark = [s for s in slides if s.get("lum", 255) < 50]
    if portrait or lowres or dark:
        print("\n  Heads up, for a full-bleed hero:")
        if portrait:
            print(f"    {len(portrait)} of {len(slides)} are portrait and will crop hard on desktop: "
                  + ", ".join(s["name"] for s in portrait[:4])
                  + (" …" if len(portrait) > 4 else ""))
            print("      Landscape shots fill a cinematic hero far better.")
        if lowres:
            print(f"    {len(lowres)} are under 1920px wide, so they'll soften when scaled up: "
                  + ", ".join(f"{s['name']} ({s['width']}px)" for s in lowres[:4])
                  + (" …" if len(lowres) > 4 else ""))
            print("      Originals rather than messenger/social re-exports fix this.")
        if dark:
            print(f"    {len(dark)} are very dark and will read as near-black behind the "
                  "band name: "
                  + ", ".join(f"{s['name']} (lum {s['lum']:.0f})" for s in dark[:4])
                  + (" …" if len(dark) > 4 else ""))
            print("      Nothing is altered — swap them for brighter frames if you'd rather.")

    finish(args, f"sync photos: {len(slides)} slide(s)", paths=GALLERY_PATHS)


# ── git ───────────────────────────────────────────────────────────────────────

def git(*a, check=True):
    return subprocess.run(["git", *a], cwd=ROOT, check=check,
                          capture_output=True, text=True)


CONTENT_PATHS = ["shows.json", "videos.json"]


def do_push(message: str, paths: list[str] | None = None):
    paths = paths or CONTENT_PATHS
    # Content-aware, not 'git status': this repo has core.autocrlf=true while the
    # JSON files are LF on disk, so status reports them modified when nothing changed.
    unchanged = git("diff", "--quiet", "--", *paths, check=False).returncode == 0
    # A photo sync's new WebP files are untracked, which 'diff' never reports.
    untracked = git("ls-files", "--others", "--exclude-standard", "--", *paths).stdout.strip()
    if unchanged and not untracked:
        print("nothing to commit.")
        return
    git("add", "--", *paths)
    staged = git("diff", "--cached", "--name-only").stdout.strip()
    if not staged:
        print(f"no changes staged under {', '.join(paths)} — nothing to push.")
        return
    git("commit", "-m", message)
    git("push", "origin", "main")
    print(f"pushed: {message}")
    print(f"  GitHub Actions is deploying; {LIVE_URL} updates in ~1 min.")
    print(f"  check with: python scripts/cua.py status")


def finish(args, message: str, paths: list[str] | None = None):
    """Push if asked, otherwise tell the user exactly how to."""
    if args.dry_run:
        print("(dry run — nothing written, nothing pushed)")
        return
    if args.push:
        do_push(args.message or message, paths)
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

    sp = with_common(sub.add_parser(
        "optimize-stills", help="convert the fixed-name photos/ JPGs to WebP"))
    sp.set_defaults(func=cmd_optimize_stills)

    sp = with_common(sub.add_parser(
        "sync-photos", help="pull the curated Drive folder into the hero slideshow"))
    sp.add_argument("--folder", default="",
                    help="Drive folder ID or share link (default: CUA_DRIVE_FOLDER in .env)")
    sp.add_argument("--api-key", default="",
                    help="Drive API key (default: CUA_DRIVE_API_KEY in .env)")
    sp.add_argument("--from-local", default="",
                    help="bootstrap from a local directory instead of Drive")
    sp.set_defaults(func=cmd_sync_photos)

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
