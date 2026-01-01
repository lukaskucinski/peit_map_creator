# Cleanup orphaned worktree branches
# Usage: .\peit-cleanup.ps1
# Finds and deletes feature/* branches that have no corresponding worktree

$ProjectRoot = "C:\Users\lukas\OneDrive\OSIT\Python\APPEIT\appeit_map_creator"

Write-Host "`n=== Cleaning Up Orphaned Branches ===" -ForegroundColor Cyan

# Navigate to project root
Push-Location $ProjectRoot

# Get all feature branches
$FeatureBranches = git branch --list "feature/*" | ForEach-Object { $_.Trim() -replace '^\* ', '' }

if ($FeatureBranches.Count -eq 0) {
    Write-Host "No feature branches found" -ForegroundColor Gray
    Pop-Location
    exit 0
}

# Get all active worktree paths
$ActiveWorktrees = git worktree list --porcelain | Select-String "^worktree " | ForEach-Object {
    $_.ToString() -replace '^worktree ', ''
}

# Find orphaned branches (branches without corresponding worktree)
$OrphanedBranches = @()

foreach ($Branch in $FeatureBranches) {
    # Extract feature name from branch (e.g., "feature/my-feature" -> "my-feature")
    $FeatureName = $Branch -replace '^feature/', ''
    $ExpectedPath = "$ProjectRoot\.git-worktrees\$FeatureName"

    # Check if worktree exists for this branch
    $HasWorktree = $false
    foreach ($WorktreePath in $ActiveWorktrees) {
        if ($WorktreePath -eq $ExpectedPath) {
            $HasWorktree = $true
            break
        }
    }

    if (-not $HasWorktree) {
        $OrphanedBranches += $Branch
    }
}

if ($OrphanedBranches.Count -eq 0) {
    Write-Host "`nNo orphaned branches found" -ForegroundColor Green
    Pop-Location
    exit 0
}

# Display orphaned branches
Write-Host "`nFound $($OrphanedBranches.Count) orphaned branch(es):" -ForegroundColor Yellow
foreach ($Branch in $OrphanedBranches) {
    Write-Host "  - $Branch" -ForegroundColor White
}

# Ask for confirmation
Write-Host "`nDelete these branches? [y/N]" -ForegroundColor Yellow
$Response = Read-Host

if ($Response -eq 'y' -or $Response -eq 'Y') {
    Write-Host ""
    foreach ($Branch in $OrphanedBranches) {
        # Redirect stderr to suppress directory deletion prompts (Windows file locking issue)
        git branch -D $Branch 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "OK Deleted: $Branch" -ForegroundColor Green
        } else {
            Write-Host "X Failed to delete: $Branch" -ForegroundColor Red
        }
    }

    # Prune worktree references
    Write-Host "`nPruning worktree references..." -ForegroundColor Yellow
    git worktree prune

    Write-Host "`nOK Cleanup complete!" -ForegroundColor Green
} else {
    Write-Host "`nCancelled - no branches deleted" -ForegroundColor Gray
}

Pop-Location
