# Coming Up Aces - Content Update & Deploy
#
# Friendly wrapper around scripts/cua.py, which does all the actual JSON editing.
# The editing lives in Python because PowerShell 5.1's ConvertTo-Json cannot
# round-trip shows.json - it reindents to 4 spaces, escapes '&' as a unicode
# escape, and turns the em-dashes in the Local Fest entries into mojibake.
# Prompts here, writes there.
#
# Deploy is automatic: push to main -> GitHub Actions -> Cloud Run.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\cua-update.ps1            # list + commit/push what's edited
#   powershell -ExecutionPolicy Bypass -File scripts\cua-update.ps1 -AddShow
#   powershell -ExecutionPolicy Bypass -File scripts\cua-update.ps1 -RemoveShow
#   powershell -ExecutionPolicy Bypass -File scripts\cua-update.ps1 -AddVideo
#   powershell -ExecutionPolicy Bypass -File scripts\cua-update.ps1 -Status
#
# Scripting it (or driving it from an agent)? Skip this wrapper and call cua.py
# directly - every command there is non-interactive:
#   python scripts\cua.py add-show --date 2026-11-01 --event "..." --venue "..." --city "..., AR"
#   python scripts\cua.py list

param(
    [switch]$AddShow,
    [switch]$RemoveShow,
    [switch]$AddVideo,
    [switch]$Status,
    [string]$Message = ""
)

$PROJECT_DIR = $PSScriptRoot | Split-Path -Parent
$CUA = Join-Path $PSScriptRoot "cua.py"
Set-Location $PROJECT_DIR

function Invoke-Cua {
    param([string[]]$CuaArgs)
    & python $CUA @CuaArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  (cua.py exited $LASTEXITCODE)" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

function Read-Required {
    param([string]$Label)
    Write-Host "$Label" -NoNewline
    $v = Read-Host
    if (-not $v.Trim()) {
        Write-Host "ERROR: $Label is required." -ForegroundColor Red
        exit 1
    }
    return $v.Trim()
}

if ($Status) {
    Invoke-Cua @("status")
    exit 0
}

if ($AddShow) {
    Write-Host "==> Add a show" -ForegroundColor Cyan
    $date    = Read-Required "Date (YYYY-MM-DD): "
    $event   = Read-Required "Event name: "
    $venue   = Read-Required "Venue: "
    $city    = Read-Required "City, State: "
    Write-Host "Doors, 24h HH:MM (blank to skip): " -NoNewline; $doors   = Read-Host
    Write-Host "Set time, 24h HH:MM (blank to skip): " -NoNewline; $time  = Read-Host
    Write-Host "Tickets URL (blank to skip): "      -NoNewline; $tickets = Read-Host
    Write-Host "Notes (blank to skip): "            -NoNewline; $notes   = Read-Host

    $a = @("add-show", "--date", $date, "--event", $event, "--venue", $venue, "--city", $city)
    if ($doors.Trim())   { $a += @("--doors", $doors.Trim()) }
    if ($time.Trim())    { $a += @("--time", $time.Trim()) }
    if ($tickets.Trim()) { $a += @("--tickets", $tickets.Trim()) }
    if ($notes.Trim())   { $a += @("--notes", $notes.Trim()) }
    Invoke-Cua $a
}
elseif ($RemoveShow) {
    Write-Host "==> Remove a show" -ForegroundColor Cyan
    Invoke-Cua @("list")
    Write-Host ""
    Write-Host "Index to remove (blank to cancel): " -NoNewline
    $choice = Read-Host
    if (-not $choice.Trim()) { Write-Host "  Cancelled." -ForegroundColor Gray; exit 0 }
    Invoke-Cua @("remove-show", "--index", $choice.Trim())
}
elseif ($AddVideo) {
    Write-Host "==> Add a video" -ForegroundColor Cyan
    $title = Read-Required "Title: "
    $url   = Read-Required "URL (YouTube or Google Drive): "
    Write-Host "Date YYYY-MM-DD (blank for today): " -NoNewline; $vdate = Read-Host

    $a = @("add-video", "--title", $title, "--url", $url)
    if ($vdate.Trim()) { $a += @("--date", $vdate.Trim()) }
    Invoke-Cua $a
}
else {
    Write-Host "==> Coming Up Aces - Content Update" -ForegroundColor Cyan
    Write-Host ""
    Invoke-Cua @("list")
}

# -- Commit + push whatever is now edited --------------------------------------
Write-Host ""
# Content-aware, not 'git status': this repo has core.autocrlf=true while the JSON
# files are LF on disk, so status reports them modified even when nothing changed.
git diff --quiet -- shows.json videos.json 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "No shows.json/videos.json changes to publish." -ForegroundColor Gray
    exit 0
}

Write-Host "Pending changes:" -ForegroundColor Yellow
git status --short -- shows.json videos.json
Write-Host ""

if (-not $Message) {
    Write-Host "Commit message (blank to skip publishing): " -NoNewline
    $Message = Read-Host
}
if (-not $Message.Trim()) {
    Write-Host '  Left uncommitted. Publish later with: python scripts\cua.py push -m "..."' -ForegroundColor Gray
    exit 0
}

Invoke-Cua @("push", "-m", $Message.Trim())
Write-Host ""
Write-Host "  Waiting 30s, then checking the deploy..." -ForegroundColor Gray
Start-Sleep -Seconds 30
Invoke-Cua @("status")
