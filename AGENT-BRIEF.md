# AGENT-BRIEF — coming-up-aces

Load this instead of the wiki when you are a local model (`localcoder`, `localreviewer`, Aider).
Deliberately short: paths, the gotchas that cost real time, and pointers — never the detail
itself. The long version lives in `C:\Users\Parker\Personal PC\wiki\`, and
`wiki/projects/coming-up-aces.md` is the page that owns the detail.

## The one thing that breaks people first

**A push to `main` deploys to the live band website in about a minute.** There is no staging step and no
review gate.

| Path | Contents |
|---|---|
| `C:\Users\Parker\projects\coming-up-aces` | The repo. One branch, `main`. Remote `github.com/ParkerGent101/CUA-Website.git` |
| `.github/workflows/deploy.yml` | Fires on push to `main`: `gcloud builds submit` then `gcloud run deploy cua-website` |

So: work on a `wt/<task>` branch, commit there, and **never push**. Merging is Parker's.

## Build and test, exactly

- Run: `python -m http.server 8000` from the repo root, then `http://localhost:8000`.
- Container check: `docker build -t coming-up-aces .`
- **There are no automated tests.** Verification is opening the page — desktop **and** mobile. Do not
  claim a test passed.
- Show and video data is edited through `python scripts/cua.py` (`list`, `add-show`, `edit-show`,
  `remove-show`, `add-video`, `remove-video`, `push`, `status`) — never by hand, and never with a
  PowerShell script: PS 5.1's `ConvertTo-Json` reindents the file, escapes `&`, and mojibakes the
  em-dashes in the Local Fest entries. `scripts\cua-update.ps1` is a prompt wrapper over the same tool.
  Every `cua.py` command is non-interactive and nothing is pushed without `--push`.
- Deploy target: Cloud Run `cua-website`, region **`europe-west1`**, port 8080, GCP project
  `band-website-495219`. Note the region — the other two projects are `us-central1`.

## Rules that are decisions, not preferences

- **The stack stays static.** Plain HTML, CSS and vanilla JS: `index.html`, `epk.html`, `app.js`,
  `style.css`, `shows.json`, `videos.json`. No frameworks, no build step, unless Parker asks.
- **Show dates are `YYYY-MM-DD`, always.** Past-show auto-hide reads the `data-date` attribute in
  `app.js`; changing the date format or that attribute silently breaks the hiding logic. This is the
  single most breakable thing in the repo.
- **`shows.json` here is canonical**, and as of 2026-08-30 it is the *only* copy — Mission Control's
  Band module and its `push_site` tool were removed when that app was cut down to finance-only.
- **Optimise photos before committing them.** `photos/` is served directly.
- **Never commit** `node_modules`, `.env`, `build/`, `dist/`, `*.log`, `.DS_Store`.

## Two documented traps

1. **`doors`/`time` are 24-hour `HH:MM`, not display text.** `app.js`'s `fmtTime()` converts them to
   "Doors 8:00 PM"; anything that isn't `HH:MM` is passed through raw and looks wrong on the site.
   `UPDATING.md` used to show `"time": "9:00 PM"` and omit `event` while `CLAUDE.md` showed neither
   `doors` nor `time` — both were corrected 2026-08-30, and `cua.py` now validates the format, so the
   docs and the code finally agree.
2. **A CI "version conflict" failure is a GCP timing race, not your code.** Re-run the workflow. Do not
   start debugging the site — this has cost time before.

Also worth knowing: `videos.json` is currently the four bytes `[]`. Empty on purpose, not corrupt.

## Before you claim a task

Read `wiki/meta/agent-coordination.md` and do its four checks. This repo has no worktrees and one
branch, so the check that matters is the board: is anyone already editing `shows.json`? Two lanes
editing the same small JSON file is the collision this repo is most exposed to.

## Stop and escalate

- Anything that would push, merge, or deploy.
- Publishing show or video changes. Editing the JSON is fine; running `cua.py push` (or passing
  `--push`) deploys the band's public site, and that is Parker's call.
- Design and copy decisions about the band's public face. Those are Parker's, not a lane's.
- See `wiki/meta/agent-lanes.md` for the escalation rule and what to carry with you.
