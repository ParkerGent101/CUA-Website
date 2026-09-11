/**
 * COMING UP ACES — Google Drive restructure
 * ------------------------------------------------------------------
 * Rebuilds "Comin Up Aces Material" into the proposed layout.
 *
 *   NEVER DELETES ANYTHING. Only creates, moves and renames.
 *   Safe to run more than once — it adopts folders that already exist.
 *
 * HOW TO RUN
 *   1. script.google.com  →  New project
 *   2. Paste this whole file over the default Code.gs
 *   3. Run  ▶ restructure   — leave DRY_RUN = true the first time.
 *      Google will ask you to authorise the script; that is it asking
 *      for permission to touch your own Drive. Review and accept.
 *   4. Read the log (Ctrl+Enter). It prints every move it intends.
 *   5. Set DRY_RUN = false, run it again for real.
 *
 * If anything looks wrong afterwards, every move is listed in the log
 * and can be reversed by hand — nothing is destroyed.
 */

const DRY_RUN = true;   // ← flip to false to actually make the changes

const ROOT_ID = '1Tu1cT82_bpGOziIeVskEd_4gDRdA6tNj';  // Comin Up Aces Material

// Existing folders, by ID (more reliable than matching on name)
const ID = {
  practiceVideos : '1bxzX-2TI7rM_Sg5MGvJ3PM86HkQ3_4cw',  // Practice Song Videos
  showVideos     : '1Q0hZr9t5OHf_GiEK__DRZAE1M1UbwPz8',  // Show Videos
  promoMgmt      : '1N6TPDCKWAMOqdQMmNc-QyjRwzXEWfOuy',  // Promotional/Management
  setLists       : '1YN7jvhexjbb6cfjSlsPNCIPwL354T_7n',  // Set Lists
  originalMat    : '17pHAqdGnRbqUXKqpa4ezNxpo1npUBfyF',  // Original Material
  generalPhotos  : '12fwoUVTI4qW_L6jAfvPyJqaMCJ_w4KUM',  // General Photos
  clips          : '1kZvXsWgg0WKvZdc8U4peo_BrpKCEk6Pg',  // Clips

  sv_stoicBrews  : '1LufeFRcfF7gu0EPOvIe9FPnCuPmVm8U6',  // Show Videos/Stoic Brews
  sv_georges     : '11zZJSWjRojrcHr1D1uRYah5EvwZZmTWf',  // Show Videos/Georges
  sv_gopro       : '1RwO4MtbLmtiI8g1TG0khxqwxQlntSZ37',  // .../Rileys GoPro

  gp_stoicBrews  : '1_Bd-MndRiAKtb1vFSwngjdw8GAgfpSTm',  // General Photos/Stoic Brews
  gp_fromCamera  : '15vrr7soOeGLqGsFzh2h_13rwQ1CeWj2m',  // .../PHOTOS FROM CAMERA
  gp_shadowLake  : '1sYjS13_axAOGAqgTfuVAawYpn2fXlPjb',  // General Photos/Shadow Lake
  gp_georgesPics : '1rEj75m5F73_d0k91QnNtbzLgQck52FPJ'   // General Photos/Georges Pics
};

// ───────────────────────────────────────────────────────────── helpers ──

const log = [];
const problems = [];
function say(s) { log.push(s); }

function folder(id) {
  try { return DriveApp.getFolderById(id); }
  catch (e) { problems.push('Could not open folder ' + id + ' — ' + e.message); return null; }
}

/** Find a child folder by name, or make it. Idempotent. */
function ensure(parent, name) {
  if (!parent) return null;
  const hit = parent.getFoldersByName(name);
  if (hit.hasNext()) { const f = hit.next(); say('   exists  ' + name); return f; }
  say('   CREATE  ' + name + '   (in ' + parent.getName() + ')');
  if (DRY_RUN) return { __planned: name, getName: () => name };
  return parent.createFolder(name);
}

function rename(f, newName) {
  if (!f) return;
  if (f.getName() === newName) { say('   named ok  ' + newName); return; }
  say('   RENAME  "' + f.getName() + '"  →  "' + newName + '"');
  if (!DRY_RUN) { try { f.setName(newName); } catch (e) { problems.push('Rename "' + f.getName() + '" failed — ' + e.message); } }
}

function moveFolder(f, dest) {
  if (!f || !dest) return;
  say('   MOVE    [folder] ' + f.getName() + '  →  ' + dest.getName() + '/');
  if (DRY_RUN) return;
  try { f.moveTo(dest); }
  catch (e) { problems.push('Move folder "' + f.getName() + '" failed — ' + e.message + '  (likely owned by another account)'); }
}

/**
 * Move every file out of `src` into `dest`.
 * filterFn(file) → true to move it. Omit to move all.
 */
function moveFiles(src, dest, filterFn) {
  if (!src || !dest) return 0;
  const it = src.getFiles();
  let n = 0, skipped = 0;
  while (it.hasNext()) {
    const f = it.next();
    if (filterFn && !filterFn(f)) { skipped++; continue; }
    n++;
    if (!DRY_RUN) {
      try { f.moveTo(dest); }
      catch (e) { problems.push('Move file "' + f.getName() + '" failed — ' + e.message + '  (owner: ' + safeOwner(f) + ')'); }
    }
  }
  say('   MOVE    ' + n + ' file(s) from ' + src.getName() + '/  →  ' + dest.getName() + '/'
      + (skipped ? '   (' + skipped + ' left behind by filter)' : ''));
  return n;
}

function safeOwner(f) {
  try { return f.getOwner() ? f.getOwner().getEmail() : 'unknown'; }
  catch (e) { return 'unknown'; }
}

const isImage = f => /\.(jpe?g|png|heic|heif|tiff?|webp)$/i.test(f.getName());
const isVideo = f => /\.(mov|mp4|m4v|avi|mkv)$/i.test(f.getName());

// ──────────────────────────────────────────────────────────────── main ──

function restructure() {
  log.length = 0; problems.length = 0;

  say(DRY_RUN
    ? '=== DRY RUN — nothing will actually change ===\n'
    : '=== LIVE RUN — making changes ===\n');

  const root = folder(ROOT_ID);
  if (!root) { finish(); return; }

  // 0. Fix the typo on the top folder. Sharing and links are by ID, so this breaks nothing.
  say('[0] Top folder');
  rename(root, 'Coming Up Aces');

  // 1. The new shelf
  say('\n[1] New top-level folders');
  const wWebsite  = ensure(root, '01 WEBSITE');
  const wHero     = ensure(wWebsite, 'Hero Photos');
                    ensure(wWebsite, 'Press Stills');
  const wPress    = ensure(root, '02 PRESS KIT');
                    ensure(wPress, 'Logos & Artwork');
                    ensure(wPress, 'Hi-Res Photos');
  const wShows    = ensure(root, '03 SHOWS');
  const wSongs    = ensure(root, '04 SONGS');
  const wArchive  = ensure(root, '99 RAW ARCHIVE');
  const wRawShow  = ensure(wArchive, 'Show Footage Raw');
                    ensure(wArchive, 'Practice Raw');

  // 2. Rename the two folders that just need a number
  say('\n[2] Renames in place');
  const promo    = folder(ID.promoMgmt);
  const setLists = folder(ID.setLists);
  rename(promo,    '05 BAND BUSINESS');
  rename(setLists, '06 SET LISTS');

  // 3. Songs
  say('\n[3] 04 SONGS');
  const covers    = folder(ID.practiceVideos);
  const originals = folder(ID.originalMat);
  moveFolder(covers, wSongs);    rename(covers,    'Covers');
  moveFolder(originals, wSongs); rename(originals, 'Originals');

  // 4. Shows — Georges, 25 Jun 2026 (date confirmed against shows.json on the site)
  say('\n[4] 03 SHOWS / 2026-06-25 Georges Majestic');
  const georges      = ensure(wShows, '2026-06-25 Georges Majestic');
  const georgesPhoto = ensure(georges, 'Photos');
  const georgesVideo = ensure(georges, 'Video');
  moveFiles(folder(ID.sv_georges), georgesVideo);          // the 17 MVI_*.MOV
  moveFolder(folder(ID.sv_gopro), wRawShow);               // 7.32 GB of card dump
  moveFiles(folder(ID.gp_georgesPics), georgesPhoto);      // the 907 MB zip — still needs unzipping by hand

  // 5. Shows — Stoic Brews.  NOTE: date taken from the camera files (Jan 2025).
  //    Photos span Jan 1–2 and Jan 25, so this may really be two nights — worth checking.
  say('\n[5] 03 SHOWS / 2025-01 Stoic Brews');
  const stoic      = ensure(wShows, '2025-01 Stoic Brews');
  const stoicPhoto = ensure(stoic, 'Photos');
  const stoicVideo = ensure(stoic, 'Video');
  moveFiles(folder(ID.sv_stoicBrews), stoicVideo, isVideo);
  moveFiles(folder(ID.sv_stoicBrews), stoicPhoto, isImage);
  moveFiles(folder(ID.gp_fromCamera), stoicPhoto);         // the 70 DSCF*.JPG
  moveFiles(folder(ID.gp_stoicBrews), stoicPhoto, isImage);

  // 6. Shows — Shadow Lake.  No date anywhere in Drive; name it once you know.
  say('\n[6] 03 SHOWS / Shadow Lake  (no date found — rename when you know it)');
  const shadow      = ensure(wShows, 'Shadow Lake');
  const shadowPhoto = ensure(shadow, 'Photos');
  moveFiles(folder(ID.gp_shadowLake), shadowPhoto);

  // 7. Website + press kit
  say('\n[7] 01 WEBSITE / 02 PRESS KIT');
  moveFolder(folder(ID.clips), wWebsite);                  // 5 finished clips
  if (promo && !DRY_RUN) {
    const sp = promo.getFilesByName('CUA Stage Plot');
    if (sp.hasNext()) { const f = sp.next(); say('   MOVE    CUA Stage Plot  →  02 PRESS KIT/');
                        try { f.moveTo(wPress); } catch (e) { problems.push('Stage Plot move failed — ' + e.message); } }
  } else if (promo) {
    say('   MOVE    CUA Stage Plot  →  02 PRESS KIT/');
  }

  // 8. Strays sitting loose in My Drive
  say('\n[8] Loose files in My Drive root');
  sweepStray('Georges Setlist W_ Transitions.pdf', setLists);
  sweepStray('TIPS.docx', promo);   // duplicate of the TIPS Doc — moved, not deleted

  // 9. What is left over
  say('\n[9] Leftovers — NOT deleted, check then remove by hand');
  reportEmpty(folder(ID.showVideos));
  reportEmpty(folder(ID.generalPhotos));

  say('\n[10] Still to do by hand');
  say('   • Unzip "P&R Georges Show.zip" inside 03 SHOWS/2026-06-25 Georges Majestic/Photos/');
  say('   • Pick 8–12 LANDSCAPE shots into 01 WEBSITE/Hero Photos, prefixed 01- 02- 03-…');
  say('   • Split 04 SONGS/Originals into one folder per song');
  say('   • Share 01 WEBSITE/Hero Photos as "Anyone with the link — Viewer"');

  finish();
}

function sweepStray(name, dest) {
  if (!dest) return;
  const it = DriveApp.getRootFolder().getFilesByName(name);
  if (!it.hasNext()) { say('   not found  ' + name); return; }
  const f = it.next();
  say('   MOVE    ' + name + '  →  ' + dest.getName() + '/');
  if (!DRY_RUN) { try { f.moveTo(dest); } catch (e) { problems.push('Stray "' + name + '" failed — ' + e.message); } }
}

function reportEmpty(f) {
  if (!f) return;
  const nf = f.getFolders().hasNext(), nfi = f.getFiles().hasNext();
  say('   ' + f.getName() + ' — ' + (nf || nfi ? 'STILL HAS CONTENT, look before removing' : 'now empty, safe to delete by hand'));
}

function finish() {
  if (problems.length) {
    say('\n=== ' + problems.length + ' PROBLEM(S) ===');
    problems.forEach(p => say('   ! ' + p));
    say('\n  Moves usually fail because the file belongs to another band member.');
    say('  Ask that person to run this, or to transfer ownership to comingupaces1.');
  } else {
    say('\n=== no problems ===');
  }
  say(DRY_RUN ? '\nDRY RUN. Set DRY_RUN = false and run again to apply.' : '\nDone.');
  console.log(log.join('\n'));
}
