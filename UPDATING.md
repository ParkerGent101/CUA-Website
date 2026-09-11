# How to Update the Site

## The easy way

Run the update script and answer the prompts — it edits the JSON, checks it, commits, pushes, and
watches the deploy:

```bash
powershell -ExecutionPolicy Bypass -File scripts\cua-update.ps1 -AddShow
```

`-RemoveShow`, `-AddVideo`, and `-Status` do the other jobs. Run it with no flags to see what's
currently listed and publish anything you've edited by hand.

Prefer typing it all on one line (this is also how an agent does it — no prompts):

```bash
python scripts/cua.py add-show --date 2026-11-01 --event "Fall Show" --venue "Georges Majestic" --city "Fayetteville, AR" --doors 20:00 --time 21:00
python scripts/cua.py list
python scripts/cua.py push -m "add November show"
```

Nothing is published until you push, and the script always tells you the exact command to do it.

The rest of this page is the by-hand version.

## Add or edit a show

Open `shows.json` and add an entry:

```json
{
  "date": "2026-07-04",
  "event": "Independence Day Show",
  "venue": "The Venue Name",
  "city": "City, ST",
  "doors": "20:00",
  "time": "21:00",
  "tickets": "https://link-to-tickets.com",
  "notes": "Optional note like 'Free entry' or 'With Special Guests'"
}
```

- `date` must be `YYYY-MM-DD` — the auto-hide logic depends on it
- **`doors` and `time` are 24-hour `HH:MM`.** The site converts them to "Doors 8:00 PM · Show 9:00 PM".
  Writing `"9:00 PM"` here does *not* work. Leave either out to hide it.
- `event` shows up in the EPK and in commit messages; the show card itself renders venue + city
- `tickets` can be an empty string `""` — no button will show
- `notes` can be an empty string `""` — nothing will show
- Past shows auto-hide; only future dates appear

## Add a video

Open `videos.json` and add an entry:

```json
{
  "title": "Live at The Venue",
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "date": "2026-06-01"
}
```

Supported URL formats:
- YouTube: `https://www.youtube.com/watch?v=XXXX`
- YouTube short: `https://youtu.be/XXXX`
- Google Drive video: `https://drive.google.com/file/d/XXXX/view`

## Update links (Spotify, Instagram, Google Drive, etc.)

Open `index.html` and find the `#links` section — edit the `href` values directly.

## Push changes to the live site

```bash
git add .
git commit -m "Add show: July 4 at Venue Name"
git push
```

The site updates automatically within ~1 minute.

> **Don't edit these JSON files with a PowerShell script.** PowerShell 5.1's `ConvertTo-Json`
> reindents the file, escapes `&`, and turns any em-dash in an event name into garbage.
> Use `scripts/cua.py`, or edit by hand in a text editor.

## Change the photos in the hero slideshow

The big rotating photos at the top of the site come from **one Google Drive folder**. That folder
is the whole publish gate: a photo is on the site because you put it there, and gone because you
took it out. Nothing else needs editing.

**One-time setup.** Share the folder as *Anyone with the link — Viewer*, then create a `.env` file
in the repo root (it is gitignored, so it never gets committed):

```
CUA_DRIVE_FOLDER=<the folder's share link, or just its ID>
CUA_DRIVE_API_KEY=<a Google Cloud API key with the Drive API enabled>
```

**Every time after that:**

```bash
python scripts/cua.py sync-photos
python scripts/cua.py push -m "new photos"
```

`sync-photos` downloads the folder, rotates each photo the right way up, strips the camera's EXIF
(including GPS, so the site never publishes where a photo was taken), writes WebP copies at several
sizes into `photos/gallery/`, regenerates `gallery.json` and `photos/og.jpg`, and deletes the
copies of anything you removed from Drive. Nothing is published until you push.

Useful to know:

- **Order** follows the filename. Prefix with `01-`, `02-` in Drive to pin the sequence.
- **Landscape photos work far better than portrait.** The hero is a wide letterbox, so a portrait
  phone photo gets cropped to a narrow vertical strip of itself on a desktop screen.
- **Bigger than 1920px wide** stops photos going soft on large screens. Use the originals, not
  something re-exported through a messaging app.
- **Very dark photos read as near-black** behind the band name. The tool warns you which ones and
  changes nothing — swap them yourself if you'd rather.
- **Alt text** you write into `gallery.json` by hand is kept across every future sync. Everything
  else in that file is regenerated, so don't hand-edit the rest.
- `--dry-run` shows what would happen and writes nothing. `--from-local <folder>` syncs from a
  folder on this computer instead of Drive.

## Replace a fixed photo (press kit, About section, band portraits)

Those use fixed filenames rather than the rotating gallery. Drop the new `hero.JPG` /
`press-1.JPG` / `member-nate.JPG` / etc. into `photos/`, keeping the name and capitalisation
exactly (Cloud Run is case-sensitive), then:

```bash
python scripts/cua.py optimize-stills
```

That writes the `.webp` files the pages actually reference. The `.JPG` originals stay as sources.

The four `member-*.JPG` files are the photos on the band cards — one per person, named after them.
Portrait shots with the face in the top half crop best: the card crops to 4:5 on desktop and to a
square on phones, trimming from the bottom.

`press-1` … `press-10` are the press kit's photos. The EPK shows the `.webp` and links the `.JPG`
beside it as the download a venue or promoter actually takes, so don't delete the `.JPG` files
thinking they're only sources. Landscape band shots go in the top grid, portrait shots of one
person in the bottom one; if you add or drop a photo, edit the matching tile in `epk.html` —
the labels next to each one quote its real pixel size.
