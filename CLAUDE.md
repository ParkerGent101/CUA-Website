# Coming Up Aces — Claude Code Agent Context

## What this project is
Static website for Coming Up Aces, a classic rock band from NWA (Parker Gent on lead guitar/keys/harmonica, Nate Poplin on vocals/rhythm, Brandon Hargis on bass, Riley Gent on drums). Sound: Lynyrd Skynyrd + Tom Petty + grunge. Live at comingupaces.net.

## Tech stack
- Pure HTML + CSS + vanilla JS (no framework, no build step, intentionally simple)
- Shows and videos pulled from JSON files and rendered client-side by app.js
- Served by nginx in a Docker container on Google Cloud Run
- Deployed automatically via GitHub Actions on push to `main`

## Repos & deployment
- GitHub: github.com/ParkerGent101/CUA-Website (private)
- Cloud Run service: `cua-website`, region: `europe-west1`
- Live URL: https://comingupaces.net
- Deploy trigger: `git push origin main` → GitHub Actions → Cloud Run (takes ~1 min)
- If CI fails with version conflict: re-run the failed workflow (it's a GCP timing race, not a code bug)

## Key files
- `shows.json` — upcoming show data; dates in `YYYY-MM-DD`; past shows auto-hide in app.js
- `videos.json` — YouTube/Drive video embeds
- `index.html` — main public site
- `epk.html` — electronic press kit
- `app.js` — client-side rendering of shows and videos
- `style.css` — all styling
- `photos/` — press and hero images (optimize before committing)
- `scripts/cua.py` — the tool that edits shows.json/videos.json (see Content update workflow)
- `UPDATING.md` — human-friendly update instructions
- `AGENTS.md` — technical rules for this codebase

## Content update workflow
**Scripted** (preferred, and the only supported path): `scripts/cua.py` edits the JSON, validates it,
and optionally commits + pushes. Every command is non-interactive, so agents and humans use the same tool.
```bash
python scripts/cua.py list
python scripts/cua.py add-show --date 2026-11-01 --event "Fall Show" --venue "Georges Majestic" --city "Fayetteville, AR" --doors 20:00 --time 21:00
python scripts/cua.py edit-show --match "Georges" --tickets https://...
python scripts/cua.py remove-show --index 2
python scripts/cua.py push -m "add November show"
```
Nothing is pushed unless you pass `--push` (or run `push`). `scripts\cua-update.ps1` is a prompt-driven
wrapper over the same tool for interactive use.

**Do not hand-edit shows.json with PowerShell.** `ConvertTo-Json` in PS 5.1 reindents the file to
4 spaces, escapes `&` as a unicode escape, and corrupts the em-dashes in the Local Fest entries into
mojibake. `cua.py` writes `json.dumps(indent=2, ensure_ascii=False)`, which is byte-identical to what's committed.

## Show data format
`doors` and `time` are 24-hour `HH:MM` and optional; `app.js` formats them to 12-hour and omits the
line when both are absent. `event` is stored for commit messages and the EPK — the show card itself
renders venue/city.
```json
{
  "date": "2026-06-25",
  "event": "Georges Showcase",
  "venue": "Georges Majestic Music Lounge",
  "city": "Fayetteville, AR",
  "doors": "20:00",
  "time": "21:00",
  "tickets": "",
  "notes": ""
}
```

## Rules
- Keep the stack static — no frameworks unless Parker explicitly asks
- Show dates must be `YYYY-MM-DD` for the auto-hide logic to work
- Optimize photos before committing (no raw camera exports)
- Never commit: node_modules, .env, build/, dist/, *.log, .DS_Store
- Test both desktop and mobile layouts when changing page structure
- Do not break the `data-date` attribute on show cards in app.js — past shows rely on it to auto-hide

## Scripts
| Script | Purpose |
|--------|---------|
| `python scripts\cua.py list` | Every show and video with its index |
| `python scripts\cua.py add-show \| edit-show \| remove-show` | Show CRUD, non-interactive |
| `python scripts\cua.py add-video \| remove-video` | Video CRUD, validates the embed URL |
| `python scripts\cua.py push -m "..."` | Commit + push shows/videos (deploys the site) |
| `python scripts\cua.py status` | Live site ping + recent GitHub Actions deploys |
| `scripts\cua-update.ps1` | Prompt-driven wrapper over `cua.py` (`-AddShow`, `-RemoveShow`, `-AddVideo`, `-Status`) |
| `scripts\clean.ps1` | Preview/remove generated artifacts |

## Relationship to Mission Control
**Mission Control no longer touches this repo.** It used to carry a Band module with a `push_site`
tool that wrote shows.json/videos.json here via the GitHub API; that was removed when Mission Control
was cut down to a finance-only app (2026-08-30). `scripts/cua.py` in this repo replaced it and is now
the only tool that edits this content. `shows.json` here was always canonical and still is.
