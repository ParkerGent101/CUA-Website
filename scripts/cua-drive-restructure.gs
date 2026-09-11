/**
 * COMING UP ACES — Google Drive restructure
 * ------------------------------------------------------------------
 * Rebuilds "Comin Up Aces Material" into the layout we agreed, and can
 * hand the archive over to the band account.
 *
 *   Two entry points, run them in this order:
 *     restructure()        build the new shelf, move everything into it
 *     transferOwnership()  hand your files to the band account
 *
 *   Safe to run more than once — it adopts folders that already exist.
 *   The ONLY thing it ever removes is the raw practice takes, and those
 *   go to Drive's Trash (recoverable for 30 days), never a hard delete.
 *
 * HOW TO RUN
 *   1. script.google.com  →  New project
 *   2. Paste this whole file over the default Code.gs
 *   3. Check the two settings directly below this comment
 *   4. Run  ▶ restructure   with DRY_RUN = true. Google will ask you to
 *      authorise it touching your own Drive; review and accept.
 *   5. Read the log (Ctrl+Enter). It prints every move before making it.
 *   6. Set DRY_RUN = false, run restructure() again for real.
 *   7. Then run transferOwnership() the same way.
 */

const DRY_RUN = true;   // ← flip to false to actually make the changes

// Decisions from 11 Sep 2026:
const DRIVE_OWNER           = 'parkergent7@gmail.com';    // owns the band folder — run restructure() as this
const BAND_ACCOUNT          = 'comingupaces1@gmail.com';  // receives ownership — does NOT run restructure()
const TRASH_PRACTICE_VIDEOS = true;   // the 10 raw practice takes, 4.75 GB → Trash

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

/**
 * Stand-in for a folder a dry run would have created.
 * It has to answer the same calls a real Folder does, because the very next
 * thing we do is ensure() children inside it — and a folder that does not
 * exist yet is, correctly, empty of everything.
 */
const EMPTY = { hasNext: () => false, next: () => null };
function plannedFolder(name) {
  return {
    __planned: true,
    getName: () => name,
    getFoldersByName: () => EMPTY,
    getFilesByName: () => EMPTY,
    getFolders: () => EMPTY,
    getFiles: () => EMPTY,
    createFolder: n => plannedFolder(n),
    setName: () => {},
    moveTo: () => {}
  };
}

/** Find a child folder by name, or make it. Idempotent. */
function ensure(parent, name) {
  if (!parent) return null;
  const hit = parent.getFoldersByName(name);
  if (hit.hasNext()) { const f = hit.next(); say('   exists  ' + name); return f; }
  say('   CREATE  ' + name + '   (in ' + parent.getName() + ')');
  if (DRY_RUN) return plannedFolder(name);
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
 * Collect an iterator into an array before touching anything.
 * Drive's iterators are paginated over a live query, so moving or trashing
 * a file while walking the folder it sits in can skip later entries. Read
 * the whole list first, then act on it.
 */
function drain(it) {
  const out = [];
  while (it.hasNext()) out.push(it.next());
  return out;
}

/** Move every file out of `src` into `dest`. filterFn(file) → true to move it. */
function moveFiles(src, dest, filterFn) {
  if (!src || !dest) return 0;
  const all = drain(src.getFiles());
  let n = 0, skipped = 0;
  for (const f of all) {
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

/**
 * Send every file in `src` to Drive's Trash.
 * This is the one destructive step in the script, and it is still reversible:
 * Trash holds files 30 days, restorable from drive.google.com/drive/trash.
 * Storage is NOT freed until the Trash is emptied.
 */
function trashContents(src, what) {
  if (!src) return;
  const all = drain(src.getFiles());
  let n = 0, gb = 0;
  for (const f of all) {
    let size = 0;
    try { size = f.getSize() / 1073741824; } catch (e) { size = 0; }
    n++; gb += size;
    say('   TRASH   ' + f.getName() + '   (' + size.toFixed(2) + ' GB)');
    if (!DRY_RUN) {
      try { f.setTrashed(true); }
      catch (e) { problems.push('Could not trash "' + f.getName() + '" — ' + e.message + '  (owner: ' + safeOwner(f) + ')'); }
    }
  }
  say('   → ' + n + ' ' + what + ', ' + gb.toFixed(2) + ' GB sent to Trash.');
  say('     Recoverable for 30 days. Storage is not freed until you empty the Trash.');
  return gb;
}

function safeOwner(f) {
  try { return f.getOwner() ? f.getOwner().getEmail() : 'unknown'; }
  catch (e) { return 'unknown'; }
}

/** Depth-first walk over every file under `f`. */
function walk(f, fn) {
  const files = f.getFiles();
  while (files.hasNext()) fn(files.next());
  const subs = f.getFolders();
  while (subs.hasNext()) walk(subs.next(), fn);
}

const isImage = f => /\.(jpe?g|png|heic|heif|tiff?|webp)$/i.test(f.getName());
const isVideo = f => /\.(mov|mp4|m4v|avi|mkv)$/i.test(f.getName());

// ──────────────────────────────────────────────────────────────── main ──

function restructure() {
  log.length = 0; problems.length = 0;

  say(DRY_RUN
    ? '=== DRY RUN — nothing will actually change ===\n'
    : '=== LIVE RUN — making changes ===\n');

  // Wrong-account guard. Moving and renaming files you do not own fails per-file and
  // half-finishes the job, so a live run from the wrong account stops here.
  const me = Session.getEffectiveUser().getEmail();
  if (me !== DRIVE_OWNER) {
    say('!! Signed in as ' + me);
    say('!! This needs to run as ' + DRIVE_OWNER + ', which owns the band folder.');
    if (me === BAND_ACCOUNT) say('!! The band account receives ownership later; it does not run this.');
    if (!DRY_RUN) { say('\nSTOPPED. Switch account, or change DRIVE_OWNER if this really is the owner.'); finish(); return; }
    say('!! Dry run continues anyway so you can see the plan.\n');
  }

  const root = folder(ROOT_ID);
  if (!root) { finish(); return; }

  // 0. Fix the typo on the top folder. Sharing and links are by ID, so this breaks nothing.
  say('[0] Top folder');
  rename(root, 'Coming Up Aces');

  // 1. The new shelf
  say('\n[1] New top-level folders');
  const wWebsite  = ensure(root, '01 WEBSITE');
                    ensure(wWebsite, 'Hero Photos');
                    ensure(wWebsite, 'Press Stills');
  const wPress    = ensure(root, '02 PRESS KIT');
                    ensure(wPress, 'Logos & Artwork');
                    ensure(wPress, 'Hi-Res Photos');
  const wShows    = ensure(root, '03 SHOWS');
  const wSongs    = ensure(root, '04 SONGS');
  const wArchive  = ensure(root, '99 RAW ARCHIVE');
  const wRawShow  = ensure(wArchive, 'Show Footage Raw');

  // 2. Rename the two folders that just need a number
  say('\n[2] Renames in place');
  const promo    = folder(ID.promoMgmt);
  const setLists = folder(ID.setLists);
  rename(promo,    '05 BAND BUSINESS');
  rename(setLists, '06 SET LISTS');

  // 3. Songs.  The raw practice takes go to Trash — the finished Clips stay.
  say('\n[3] 04 SONGS');
  const covers    = folder(ID.practiceVideos);
  const originals = folder(ID.originalMat);
  let trashedGb = 0;
  if (TRASH_PRACTICE_VIDEOS) trashedGb = trashContents(covers, 'raw practice take(s)') || 0;
  moveFolder(covers, wSongs);    rename(covers,    'Covers');
  moveFolder(originals, wSongs); rename(originals, 'Originals');

  // 4. Shows — Georges, 25 Jun 2026 (date confirmed against shows.json on the site)
  say('\n[4] 03 SHOWS / 2026-06-25 Georges Majestic');
  const georges      = ensure(wShows, '2026-06-25 Georges Majestic');
  const georgesPhoto = ensure(georges, 'Photos');
  const georgesVideo = ensure(georges, 'Video');
  moveFiles(folder(ID.sv_georges), georgesVideo);          // the 17 MVI_*.MOV
  moveFolder(folder(ID.sv_gopro), wRawShow);               // 7.32 GB of card dump
  moveFiles(folder(ID.gp_georgesPics), georgesPhoto);      // the 907 MB zip — unzip by hand after

  // 5. Shows — Stoic Brews.  Date taken from the camera files (Jan 2025).
  //    Photos span Jan 1–2 and Jan 25, so this may really be two nights — worth checking.
  //    Brandon's 70 camera shots land here, per Parker on 11 Sep 2026.
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
  moveFolder(folder(ID.clips), wWebsite);                  // the 5 finished clips — kept
  if (promo) {
    say('   MOVE    CUA Stage Plot  →  02 PRESS KIT/');
    if (!DRY_RUN) {
      const sp = promo.getFilesByName('CUA Stage Plot');
      if (sp.hasNext()) { try { sp.next().moveTo(wPress); } catch (e) { problems.push('Stage Plot move failed — ' + e.message); } }
    }
  }

  // 8. Strays sitting loose in My Drive
  say('\n[8] Loose files in My Drive root');
  sweepStray('Georges Setlist', setLists);
  sweepStray('TIPS.docx', promo);   // duplicate of the TIPS Doc — moved, not deleted

  // 9. What is left over
  say('\n[9] Leftovers — NOT deleted, check then remove by hand');
  reportEmpty(folder(ID.showVideos));
  reportEmpty(folder(ID.generalPhotos));

  say('\n[10] Still to do by hand');
  say('   • Run transferOwnership() to hand your files to ' + BAND_ACCOUNT);
  say('   • Empty the Trash to actually free the ' + trashedGb.toFixed(2) + ' GB of practice takes');
  say('   • Unzip "P&R Georges Show.zip" in 03 SHOWS/2026-06-25 Georges Majestic/Photos/');
  say('   • Pick 8–12 LANDSCAPE shots into 01 WEBSITE/Hero Photos, prefixed 01- 02- 03-…');
  say('   • Split 04 SONGS/Originals into one folder per song');
  say('   • Share 01 WEBSITE/Hero Photos as "Anyone with the link — Viewer"');

  finish();
}

// ────────────────────────────────────────────────── ownership handover ──

/**
 * Hands every file YOU own under the band folder to BAND_ACCOUNT.
 *
 * You can only give away files you own. Anything uploaded by Riley or Brandon
 * has to be transferred by them — this lists those per account so you can ask.
 * Google may also refuse to transfer certain file types between consumer
 * accounts; any refusal is reported rather than silently skipped.
 *
 * Run restructure() first, so the tree is settled before ownership moves.
 */
function transferOwnership() {
  log.length = 0; problems.length = 0;

  const me = Session.getEffectiveUser().getEmail();
  say(DRY_RUN ? '=== DRY RUN — ownership handover ===\n' : '=== LIVE — handing ownership over ===\n');
  say('Signed in as : ' + me);
  say('Handing to   : ' + BAND_ACCOUNT + '\n');

  if (me === BAND_ACCOUNT) { say('Already signed in as the band account — nothing to do.'); finish(); return; }

  const root = folder(ROOT_ID);
  if (!root) { finish(); return; }

  const others = {};
  let mine = 0, gb = 0;

  walk(root, f => {
    const owner = safeOwner(f);
    if (owner !== me) { others[owner] = (others[owner] || 0) + 1; return; }
    mine++;
    try { gb += f.getSize() / 1073741824; } catch (e) {}
    if (!DRY_RUN) {
      try { f.setOwner(BAND_ACCOUNT); }
      catch (e) { problems.push('Transfer "' + f.getName() + '" failed — ' + e.message); }
    }
  });

  say(mine + ' file(s) you own (' + gb.toFixed(2) + ' GB)  →  ' + BAND_ACCOUNT);
  const keys = Object.keys(others);
  if (keys.length) {
    say('\nNot yours to give — ask each of these to run this script from their own account:');
    keys.forEach(o => say('   ' + others[o] + ' file(s) owned by ' + o));
  }
  say('\nAfter this, ' + BAND_ACCOUNT + ' carries roughly ' + (gb + 2.5).toFixed(1) + ' GB.');
  say('A free account holds 15 GB — check it fits before the others transfer theirs too.');

  finish();
}

// ────────────────────────────────────────────────────────────── detail ──

/**
 * Move a loose file out of My Drive root.
 * `hint` is matched loosely — exact names are brittle, since what Drive shows
 * you is not always the stored name (slashes render as underscores, trailing
 * spaces are invisible). Anything matching more than once is listed, not moved.
 */
function sweepStray(hint, dest) {
  if (!dest) return;
  const root = DriveApp.getRootFolder();
  let hits = drain(root.getFilesByName(hint));
  if (!hits.length) {
    const safe = hint.replace(/["\\]/g, ' ').split('.')[0];
    try { hits = drain(root.searchFiles('title contains "' + safe + '" and trashed = false')); }
    catch (e) { problems.push('Search for "' + hint + '" failed — ' + e.message); }
  }
  if (!hits.length) { say('   not found  ' + hint); return; }
  if (hits.length > 1) {
    say('   AMBIGUOUS  "' + hint + '" matched ' + hits.length + ' files — moving none:');
    hits.forEach(f => say('                 ' + f.getName()));
    return;
  }
  say('   MOVE    ' + hits[0].getName() + '  →  ' + dest.getName() + '/');
  if (!DRY_RUN) { try { hits[0].moveTo(dest); } catch (e) { problems.push('Stray "' + hint + '" failed — ' + e.message); } }
}

function reportEmpty(f) {
  if (!f) return;
  const hasAny = f.getFolders().hasNext() || f.getFiles().hasNext();
  say('   ' + f.getName() + ' — ' + (hasAny ? 'STILL HAS CONTENT, look before removing' : 'now empty, safe to delete by hand'));
}

function finish() {
  if (problems.length) {
    say('\n=== ' + problems.length + ' PROBLEM(S) ===');
    problems.forEach(p => say('   ! ' + p));
    say('\n  Moves and transfers usually fail because the file belongs to another band member.');
    say('  Ask that person to run this script from their own account.');
  } else {
    say('\n=== no problems ===');
  }
  say(DRY_RUN ? '\nDRY RUN. Set DRY_RUN = false and run again to apply.' : '\nDone.');
  console.log(log.join('\n'));
}
