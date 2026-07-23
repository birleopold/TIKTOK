param(
    [string]$Repo = "C:\Users\LEOSOFT\Desktop\TIKTOK"
)

$ErrorActionPreference = "Stop"
Set-Location $Repo

if (-not (Test-Path ".git")) {
    throw "Not a Git repository: $Repo"
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dbBackup = $null

if (Test-Path ".\creator_library.db") {
    $dbBackup = Join-Path $env:USERPROFILE "Desktop\creator_library-before-pull-$stamp.db"
    Copy-Item ".\creator_library.db" $dbBackup -Force
    Write-Host "Creator database backed up to $dbBackup"
}

git fetch origin
if ($LASTEXITCODE -ne 0) {
    throw "git fetch failed."
}

$ahead = [int](git rev-list --count origin/main..HEAD)
$behind = [int](git rev-list --count HEAD..origin/main)

if ($ahead -gt 0) {
    Write-Host ""
    Write-Host "Pull stopped safely: this branch has $ahead local commit(s) not on GitHub." -ForegroundColor Yellow
    Write-Host "Push or recover those commits first. This script will not reset them."
    git log --oneline origin/main..HEAD
    exit 2
}

# Generated tracked files should not block a pull.
if (Test-Path ".\creator_library.db") {
    git restore -- ".\creator_library.db"
}
$trackedCaches = git ls-files | Where-Object { $_ -match '(^|/)__pycache__/|\.pyc$' }
foreach ($cache in $trackedCaches) {
    git restore -- "$cache" 2>$null
}

$dirty = git status --porcelain |
    Where-Object {
        $_ -notmatch 'creator_library\.db$' -and
        $_ -notmatch '__pycache__' -and
        $_ -notmatch '\.pyc$'
    }

if ($dirty) {
    Write-Host ""
    Write-Host "Pull stopped safely because source or untracked files are present:" -ForegroundColor Yellow
    $dirty | ForEach-Object { Write-Host $_ }
    Write-Host "Commit, move, or stash those files before pulling."
    if ($dbBackup) {
        Copy-Item $dbBackup ".\creator_library.db" -Force
        Write-Host "Creator database restored."
    }
    exit 3
}

if ($behind -gt 0) {
    git pull --ff-only origin main
    if ($LASTEXITCODE -ne 0) {
        if ($dbBackup) {
            Copy-Item $dbBackup ".\creator_library.db" -Force
        }
        throw "Fast-forward pull failed."
    }
} else {
    Write-Host "Already up to date."
}

if ($dbBackup) {
    Copy-Item $dbBackup ".\creator_library.db" -Force
    Write-Host "Creator database restored."
}

Write-Host ""
Write-Host "TIKTOK safely synchronized with origin/main." -ForegroundColor Green
git status -sb
