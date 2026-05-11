// Set footer year
document.getElementById('year').textContent = new Date().getFullYear();

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

// Load and render shows
fetch('shows.json')
  .then(r => r.json())
  .then(shows => {
    const today = new Date();
    today.setHours(0,0,0,0);

    const upcoming = shows
      .filter(s => new Date(s.date) >= today)
      .sort((a, b) => new Date(a.date) - new Date(b.date));

    const list = document.getElementById('shows-list');
    const none = document.getElementById('no-shows');

    if (upcoming.length === 0) {
      none.style.display = '';
      return;
    }

    upcoming.forEach(show => {
      const d = new Date(show.date + 'T12:00:00');
      const card = document.createElement('div');
      card.className = 'show-card';
      card.innerHTML = `
        <div class="show-date">
          <div class="day">${d.getDate()}</div>
          <div class="month">${MONTHS[d.getMonth()]} ${d.getFullYear()}</div>
        </div>
        <div class="show-info">
          <div class="venue">${show.venue}</div>
          <div class="city">${show.city}${show.time ? ' &mdash; ' + show.time : ''}</div>
          ${show.notes ? `<div class="notes">${show.notes}</div>` : ''}
        </div>
        <div class="show-ticket">
          ${show.tickets ? `<a href="${show.tickets}" target="_blank">Tickets</a>` : ''}
        </div>
      `;
      list.appendChild(card);
    });
  })
  .catch(() => {
    document.getElementById('no-shows').style.display = '';
  });

// Load and render videos
fetch('videos.json')
  .then(r => r.json())
  .then(videos => {
    const grid = document.getElementById('video-grid');
    videos.forEach(v => {
      const embedUrl = toEmbedUrl(v.url);
      if (!embedUrl) return;
      const card = document.createElement('div');
      card.className = 'video-card';
      card.innerHTML = `
        <div class="video-embed">
          <iframe src="${embedUrl}" allowfullscreen loading="lazy"></iframe>
        </div>
        <div class="video-meta">
          <div class="title">${v.title}</div>
          ${v.date ? `<div class="date">${v.date}</div>` : ''}
        </div>
      `;
      grid.appendChild(card);
    });
  });

function toEmbedUrl(url) {
  // YouTube watch links
  const ytMatch = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([A-Za-z0-9_-]+)/);
  if (ytMatch) return `https://www.youtube.com/embed/${ytMatch[1]}`;

  // YouTube already-embed links
  if (url.includes('youtube.com/embed/')) return url;

  // Google Drive file links  -> embed
  const driveMatch = url.match(/drive\.google\.com\/file\/d\/([^/]+)/);
  if (driveMatch) return `https://drive.google.com/file/d/${driveMatch[1]}/preview`;

  return null;
}
