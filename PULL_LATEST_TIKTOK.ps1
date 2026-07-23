param(
    [string]$Repo = "C:\Users\LEOSOFT\Desktop\TIKTOK"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path (Join-Path $Repo ".git"))) {
    throw "Git repository not found: $Repo"
}

Set-Location $Repo
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dbPath = Join-Path $Repo "creator_library.db"
$dbBackup = Join-Path $env:USERPROFILE "Desktop\creator_library-before-pull-$stamp.db"

if (Test-Path $dbPath) {
    Copy-Item $dbPath $dbBackup -Force
    Write-Host "Creator database backed up to $dbBackup" -ForegroundColor Cyan
}

try {
    $dirty = @(git status --porcelain)
    $important = @($dirty | Where-Object {
        $_ -notmatch "creator_library\.db" -and
        $_ -notmatch "__pycache__" -and
        $_ -notmatch "\.pyc$" -and
        $_ -notmatch "app-startup\.log"
    })

    if ($important.Count -gt 0) {
        $backupBranch = "backup-working-tree-$stamp"
        git switch -c $backupBranch
        git add -A
        git commit -m "Backup working tree before pull"
        git switch main
        Write-Host "Uncommitted work saved on $backupBranch" -ForegroundColor Yellow
    }

    if (Test-Path $dbPath) {
        git restore -- creator_library.db 2>$null
    }

    Get-ChildItem -Path ".\unified_app" -Directory -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

    git fetch origin
    git checkout main

    $ahead = [int](git rev-list --count origin/main..main)
    $behind = [int](git rev-list --count main..origin/main)

    if ($ahead -gt 0) {
        $backupBranch = "backup-local-commits-$stamp"
        git branch $backupBranch HEAD
        git reset --hard origin/main
        Write-Host "Local commits preserved on $backupBranch" -ForegroundColor Yellow
    }
    elseif ($behind -gt 0) {
        git pull --ff-only origin main
    }
    else {
        Write-Host "Repository is already current." -ForegroundColor Green
    }

    py -3 -m compileall -q unified_app
    if ($LASTEXITCODE -ne 0) {
        throw "Python compilation failed after pulling."
    }
}
finally {
    if (Test-Path $dbBackup) {
        Copy-Item $dbBackup $dbPath -Force
        Write-Host "Creator database restored." -ForegroundColor Green
    }
}

Write-Host "TIKTOK is synchronized with origin/main." -ForegroundColor Green
git status
