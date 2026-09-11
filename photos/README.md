# photos/

Two different things live here.

## Fixed-name stills

Referenced by name from `index.html` and `epk.html`:

- `hero.JPG` — kept as a source; the site's hero is the slideshow now (see below)
- `press-1.JPG` … `press-10.JPG` — press photos. The EPK shows the `.webp` of each and links
  the `.JPG` next to it as the hi-res download, so **both** files have to stay. `press-2.webp`
  is also the photo in the site's About section. `press-5/6/8/9/10` were promoted out of the
  hero slideshow, so they are re-encodes of the 2560px gallery slides rather than camera
  originals — drop the originals over those names and re-run `optimize-stills` to upgrade them
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
