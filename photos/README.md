# photos/

Two different things live here.

## Fixed-name stills

Referenced by name from `index.html` and `epk.html`:

- `hero.JPG` — kept as a source; the site's hero is the slideshow now (see below)
- `press-1.JPG` … `press-7.JPG` — press photos; `press-1/2/3` appear in the EPK,
  and `press-2.webp` is the photo in the site's About section
- `member-nate.JPG`, `member-parker.JPG`, `member-brandon.JPG`, `member-riley.JPG` —
  the portraits on the band cards in `index.html`. The name after `member-` is what ties
  the file to the card, so a new one has to reuse the existing name. These are capped at
  900px wide instead of 1800px, because they only ever render in a ~300px card

Replace a file keeping its **exact name and capitalisation** — Cloud Run is case-sensitive, so
`hero.jpg` and `hero.JPG` are different files online — then run:

```bash
python scripts/cua.py optimize-stills
```

That writes the `.webp` copies the pages actually load. The `.JPG` files stay as the sources you
re-optimise from; nothing on the site links them directly.

## Generated — do not hand-edit

- `gallery/` — content-hashed WebP slides for the hero slideshow
- `og.jpg` — the 1200x630 image used for link previews when the site is shared

Both are written by `python scripts/cua.py sync-photos`, which pulls the curated Google Drive
folder. See "Change the photos in the hero slideshow" in `UPDATING.md`.
