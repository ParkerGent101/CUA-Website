# AGENTS.md

## Project

Coming Up Aces is a static band website for comingupaces.net. It is intentionally simple: HTML, CSS, browser JavaScript, JSON data, photos, and Docker/nginx deployment files.

## Run And Preview

- Local static preview: `python -m http.server 8000`, then open `http://localhost:8000`.
- Docker preview: `docker build -t coming-up-aces .` and run with an nginx-style static container if needed.
- Live updates deploy from Git after committing and pushing the site changes.

## Important Files

- `index.html`: main public site.
- `epk.html`: electronic press kit page.
- `style.css`: shared visual styling.
- `app.js`: show/video rendering.
- `shows.json`: upcoming show data.
- `videos.json`: video embeds.
- `photos/`: press and hero images.
- `UPDATING.md`: human-facing update instructions.

## Editing Rules

- Keep the stack static unless the user explicitly asks for a build system.
- Preserve simple JSON data files. Show dates should stay in `YYYY-MM-DD` format so past shows auto-hide correctly.
- Optimize new photos before committing; avoid large original camera exports when web-sized images will do.
- Do not commit local logs, generated build folders, dependency folders, or machine-specific editor settings.
- When changing page structure, check both desktop and mobile layouts.

## Cleanup

- Run `powershell -ExecutionPolicy Bypass -File scripts/clean.ps1` to preview generated files and folders that can be removed.
- Add `-Apply` to actually remove the listed generated artifacts.
