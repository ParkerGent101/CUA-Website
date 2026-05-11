# How to Update the Site

## Add or edit a show

Open `shows.json` and add an entry:

```json
{
  "date": "2026-07-04",
  "venue": "The Venue Name",
  "city": "City, ST",
  "time": "9:00 PM",
  "tickets": "https://link-to-tickets.com",
  "notes": "Optional note like 'Free entry' or 'With Special Guests'"
}
```

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
