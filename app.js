/* ═══════════════════════════════════════════════════════════════════════════
   Coming Up Aces — site behaviour

   This file is live. It used to be dead: index.html carried an inline copy of
   the show/video rendering and never linked here, so edits to this file did
   nothing. index.html now links it and carries no inline script.

   Contents: nav, hero slideshow, shows, videos, scroll reveals.
   ═══════════════════════════════════════════════════════════════════════════ */

(function () {
  'use strict';

  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function $(sel) { return document.querySelector(sel); }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  /* ─── nav ───────────────────────────────────────────────────────────────── */

  function initNav() {
    var nav = $('.nav');
    var toggle = $('.nav-toggle');
    var links = $('.nav-links');

    // Fill the nav in once it's no longer over the hero.
    var onScroll = function () {
      nav.classList.toggle('is-stuck', window.scrollY > 40);
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });

    if (!toggle || !links) return;
    var setOpen = function (open) {
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      links.classList.toggle('is-open', open);
    };
    toggle.addEventListener('click', function () {
      setOpen(toggle.getAttribute('aria-expanded') !== 'true');
    });
    // Tapping a link, or Escape, closes the panel.
    links.addEventListener('click', function (e) {
      if (e.target.closest('a')) setOpen(false);
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') setOpen(false);
    });
  }

  /* ─── hero slideshow ────────────────────────────────────────────────────── */

  var SLIDE_MS = 7000;

  function initHero() {
    var stage = $('#hero-slides');
    if (!stage) return;

    fetch('gallery.json?v=' + Date.now(), { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : []; })
      .then(function (slides) { buildSlideshow(stage, slides); })
      .catch(function () { /* the baked-in first slide stays; nothing to do */ });
  }

  function buildSlideshow(stage, data) {
    if (!Array.isArray(data) || !data.length) return;

    // Slide 0 is already in the HTML (cua.py sync-photos bakes it in and
    // preloads it, so the hero paints without waiting for this fetch). Only
    // append the ones that aren't there yet, matched on src.
    var present = {};
    Array.prototype.forEach.call(stage.querySelectorAll('.slide'), function (img) {
      var m = /(slide-[a-f0-9]+)-\d+\.webp/.exec(img.getAttribute('src') || '');
      if (m) present[m[1]] = true;
    });

    data.forEach(function (s) {
      var key = s.src.split('/').pop();
      if (present[key]) return;
      var img = el('img', 'slide');
      // src/srcset are attached on demand — see hydrate(). A 25-photo gallery
      // would otherwise fetch 25 full-bleed images on load, since every slide
      // is technically in the viewport and so never actually lazy-loads.
      img.dataset.src = s.src + '-' + Math.max.apply(null, s.widths) + '.webp';
      img.dataset.srcset = s.widths.map(function (w) {
        return s.src + '-' + w + '.webp ' + w + 'w';
      }).join(', ');
      img.sizes = '100vw';
      img.alt = s.alt || 'Coming Up Aces';
      img.decoding = 'async';
      if (s.lqip) {
        img.style.backgroundImage = 'url("' + s.lqip + '")';
        img.style.backgroundSize = 'cover';
        img.style.backgroundPosition = 'center 32%';
      }
      stage.appendChild(img);
    });

    var slides = Array.prototype.slice.call(stage.querySelectorAll('.slide'));
    if (slides.length < 2) return;

    function hydrate(i) {
      var img = slides[i];
      if (!img || !img.dataset.src) return;
      img.srcset = img.dataset.srcset;
      img.src = img.dataset.src;
      delete img.dataset.src;
      delete img.dataset.srcset;
    }

    var current = 0;
    slides.forEach(function (s, i) { s.classList.toggle('is-active', i === 0); });
    hydrate(0);
    hydrate(1);                                  // next one ready before it's needed

    var dots = $('.hero-dots');
    var buttons = [];
    if (dots) {
      slides.forEach(function (_, i) {
        var b = el('button');
        b.type = 'button';
        b.setAttribute('aria-label', 'Photo ' + (i + 1) + ' of ' + slides.length);
        b.setAttribute('aria-current', i === 0 ? 'true' : 'false');
        b.addEventListener('click', function () { show(i); restart(); });
        dots.appendChild(b);
        buttons.push(b);
      });
    }

    function show(i) {
      if (i === current) return;
      hydrate(i);
      hydrate((i + 1) % slides.length);
      slides[current].classList.remove('is-active', 'drift');
      current = i;
      var next = slides[current];
      next.classList.add('is-active');
      if (!reduceMotion) {
        // Restart the drift from scale(1) each time round.
        next.classList.remove('drift');
        void next.offsetWidth;
        next.classList.add('drift');
      }
      buttons.forEach(function (b, bi) {
        b.setAttribute('aria-current', bi === current ? 'true' : 'false');
      });
    }

    if (reduceMotion) return;                    // manual navigation only

    slides[0].classList.add('drift');
    var timer = null;
    function restart() {
      clearInterval(timer);
      timer = setInterval(function () { show((current + 1) % slides.length); }, SLIDE_MS);
    }
    restart();
    // Don't burn battery advancing a slideshow nobody is looking at.
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) clearInterval(timer);
      else restart();
    });
  }

  /* ─── shows ─────────────────────────────────────────────────────────────── */

  // "HH:MM" 24-hour -> "H:MM AM/PM". Anything else passes through, which is how
  // a malformed doors/time ends up visibly wrong rather than silently dropped.
  function fmtTime(t) {
    if (!t) return '';
    var m = /^(\d{1,2}):(\d{2})$/.exec(t);
    if (!m) return t;
    var h = +m[1];
    var ap = h < 12 ? 'AM' : 'PM';
    return (h % 12 || 12) + ':' + m[2] + ' ' + ap;
  }

  function whenLine(s) {
    return [s.doors && 'Doors ' + fmtTime(s.doors),
            s.time && 'Show ' + fmtTime(s.time)].filter(Boolean).join(' · ');
  }

  function ticketBtn(s, cls) {
    if (!s.tickets) return null;
    var a = el('a', cls, 'Tickets');
    a.href = s.tickets;
    a.target = '_blank';
    a.rel = 'noopener';
    return a;
  }

  function initShows() {
    var host = $('#show-list');
    if (!host) return;
    fetch('shows.json?v=' + Date.now(), { cache: 'no-store' })
      .then(function (r) { return r.json(); })
      .then(function (shows) { renderShows(host, shows); })
      .catch(function () { renderShows(host, []); });
  }

  function renderShows(host, shows) {
    // Past shows hide themselves: dates are YYYY-MM-DD, parsed at local noon so
    // a timezone offset can't roll a show back a day. This filter IS the
    // auto-hide mechanism — keep the date format and it keeps working.
    var today = new Date();
    today.setHours(0, 0, 0, 0);
    var upcoming = (Array.isArray(shows) ? shows : [])
      .filter(function (s) { return s && s.date && new Date(s.date + 'T12:00:00') >= today; })
      .sort(function (a, b) { return a.date < b.date ? -1 : a.date > b.date ? 1 : 0; });

    host.textContent = '';

    if (!upcoming.length) {
      var box = el('div', 'shows-empty');
      box.appendChild(el('div', 'headline', 'No dates on the books right now'));
      box.appendChild(el('p', null,
        'We’re between runs — if you book bands in Northwest Arkansas, ' +
        'we’d love to hear from you.'));
      var book = el('a', 'btn btn-solid', 'Book the band');
      book.href = 'mailto:comingupaces1@gmail.com';
      box.appendChild(book);
      host.appendChild(box);
      return;
    }

    host.appendChild(nextShowCard(upcoming[0]));
    if (upcoming.length > 1) {
      var list = el('div', 'show-list');
      upcoming.slice(1).forEach(function (s) { list.appendChild(showRow(s)); });
      host.appendChild(list);
    }
  }

  function nextShowCard(s) {
    var d = new Date(s.date + 'T12:00:00');
    var card = el('div', 'next-show reveal');
    card.appendChild(el('div', 'next-label', 'Next show'));

    var date = el('div', 'big-date');
    date.appendChild(el('span', 'm', MONTHS[d.getMonth()]));
    date.appendChild(el('span', 'd', String(d.getDate())));
    date.appendChild(el('span', 'y', String(d.getFullYear())));
    card.appendChild(date);

    var info = el('div');
    info.appendChild(el('div', 'event', s.event || s.venue || 'Live'));
    var venue = el('div', 'venue');
    venue.appendChild(el('strong', null, s.venue || ''));
    if (s.city) venue.appendChild(document.createTextNode(', ' + s.city));
    info.appendChild(venue);
    var w = whenLine(s);
    if (w) info.appendChild(el('div', 'when', w));
    if (s.notes) info.appendChild(el('div', 'notes', s.notes));
    card.appendChild(info);

    var btn = ticketBtn(s, 'btn btn-solid');
    if (btn) card.appendChild(btn);
    return card;
  }

  function showRow(s) {
    var d = new Date(s.date + 'T12:00:00');
    var row = el('div', 'show-row reveal');
    row.appendChild(el('div', 'rowdate',
      MONTHS[d.getMonth()] + ' ' + d.getDate() + ' · ' + d.getFullYear()));

    var info = el('div');
    info.appendChild(el('div', 'event', s.event || s.venue || 'Live'));
    info.appendChild(el('div', 'venue',
      [s.venue, s.city].filter(Boolean).join(', ')));
    var w = whenLine(s);
    if (w) info.appendChild(el('div', 'when', w));
    if (s.notes) info.appendChild(el('div', 'notes', s.notes));
    row.appendChild(info);

    var btn = ticketBtn(s, 'btn');
    if (btn) row.appendChild(btn);
    return row;
  }

  /* ─── videos ────────────────────────────────────────────────────────────── */

  function toEmbed(url) {
    if (!url) return null;
    var yt = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([A-Za-z0-9_-]+)/);
    if (yt) return 'https://www.youtube.com/embed/' + yt[1];
    if (url.indexOf('youtube.com/embed/') !== -1) return url;
    var gd = url.match(/drive\.google\.com\/file\/d\/([^/]+)/);
    if (gd) return 'https://drive.google.com/file/d/' + gd[1] + '/preview';
    return null;
  }

  function initVideos() {
    var grid = $('#video-grid');
    var section = $('#videos');
    if (!grid || !section) return;

    // videos.json is [] today. An empty "Videos coming soon" panel reads as an
    // unfinished site, so the whole section and its nav link come out instead.
    var drop = function () {
      section.remove();
      var link = document.querySelector('.nav-links a[href="#videos"]');
      if (link && link.parentElement) link.parentElement.remove();
    };

    fetch('videos.json?v=' + Date.now(), { cache: 'no-store' })
      .then(function (r) { return r.json(); })
      .then(function (videos) {
        var usable = (Array.isArray(videos) ? videos : [])
          .map(function (v) { return { v: v, embed: toEmbed(v && v.url) }; })
          .filter(function (x) { return x.embed; });
        if (!usable.length) return drop();

        usable.forEach(function (x) {
          var card = el('div', 'video-card reveal');
          var box = el('div', 'video-embed');
          var f = document.createElement('iframe');
          f.src = x.embed;
          f.title = x.v.title || 'Coming Up Aces video';
          f.loading = 'lazy';
          f.allowFullscreen = true;
          f.setAttribute('allow', 'accelerometer; encrypted-media; picture-in-picture');
          box.appendChild(f);
          card.appendChild(box);

          var meta = el('div', 'video-meta');
          meta.appendChild(el('div', 'title', x.v.title || 'Live'));
          if (x.v.date) meta.appendChild(el('div', 'date', x.v.date));
          card.appendChild(meta);
          grid.appendChild(card);
        });
        observeReveals(grid);
      })
      .catch(drop);
  }

  /* ─── scroll reveals ────────────────────────────────────────────────────── */

  var revealer = null;

  function observeReveals(root) {
    var targets = (root || document).querySelectorAll('.reveal:not(.in)');
    if (reduceMotion || !('IntersectionObserver' in window)) {
      Array.prototype.forEach.call(targets, function (n) { n.classList.add('in'); });
      return;
    }
    // Opt the page into the hidden-then-revealed state only now that we know an
    // observer exists to reveal it again. See the .reveal-ready note in style.css.
    document.documentElement.classList.add('reveal-ready');
    if (!revealer) {
      revealer = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          if (!e.isIntersecting) return;
          e.target.classList.add('in');
          revealer.unobserve(e.target);
        });
      }, { rootMargin: '0px 0px -12% 0px', threshold: 0.08 });
    }
    Array.prototype.forEach.call(targets, function (n) { revealer.observe(n); });
    armRevealFallback();
  }

  // Last resort. If the observer has revealed nothing at all a few seconds in,
  // it isn't working — show everything rather than leave the page blank. Only
  // triggers on total silence, so a working observer still animates normally.
  var fallbackArmed = false;

  function armRevealFallback() {
    if (fallbackArmed) return;
    fallbackArmed = true;
    setTimeout(function () {
      if (document.querySelector('.reveal.in')) return;      // it's working
      Array.prototype.forEach.call(
        document.querySelectorAll('.reveal'),
        function (n) { n.classList.add('in'); }
      );
    }, 3000);
  }

  /* ─── boot ──────────────────────────────────────────────────────────────── */

  function init() {
    var year = $('#year');
    if (year) year.textContent = new Date().getFullYear();
    initNav();
    initHero();
    initShows();
    initVideos();
    observeReveals(document);
    // Shows and videos arrive after their fetches, so re-scan once they land.
    setTimeout(function () { observeReveals(document); }, 600);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
