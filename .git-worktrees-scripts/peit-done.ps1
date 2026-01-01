# Quick worktree cleanup script
# Usage: .\peit-done.ps1 feature-name

param(
    [Parameter(Mandatory=$true)]
    [string]$FeatureName
)

$ProjectRoot = "C:\Users\lukas\OneDrive\OSIT\Python\APPEIT\appeit_map_creator"
$WorktreePath = "$ProjectRoot\.git-worktrees\$FeatureName"
$BranchName = "feature/$FeatureName"

Write-Host "`n=== Cleaning Up Worktree: $FeatureName ===" -ForegroundColor Cyan

# Check if worktree exists
if (-Not (Test-Path $WorktreePath)) {
    Write-Host "X Worktree not found: $WorktreePath" -ForegroundColor Red

    # List available worktrees
    Write-Host "`nAvailable worktrees:" -ForegroundColor Yellow
    Push-Location $ProjectRoot
    git worktree list
    Pop-Location

    exit 1
}

# Navigate to project root
Push-Location $ProjectRoot

# Step 1: Use robocopy to remove node_modules (handles long paths better than Remove-Item)
Write-Host "Removing node_modules (this speeds up deletion)..." -ForegroundColor Yellow
$NodeModulesPath = "$WorktreePath\peit-app-homepage\node_modules"
if (Test-Path $NodeModulesPath) {
    # Create empty temp directory for robocopy mirror
    $EmptyDir = "$env:TEMP\empty_$(Get-Random)"
    New-Item -ItemType Directory -Path $EmptyDir -Force | Out-Null

    # Use robocopy to mirror empty directory (effectively deleting node_modules)
    robocopy $EmptyDir $NodeModulesPath /MIR /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null

    # Clean up
    Remove-Item $EmptyDir -Force -ErrorAction SilentlyContinue
    Remove-Item $NodeModulesPath -Force -ErrorAction SilentlyContinue

    Write-Host "OK node_modules removed" -ForegroundColor Green
}

# Step 2: Remove .next build artifacts
Write-Host "Removing build artifacts..." -ForegroundColor Yellow
$NextPath = "$WorktreePath\peit-app-homepage\.next"
if (Test-Path $NextPath) {
    Remove-Item $NextPath -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "OK Build artifacts removed" -ForegroundColor Green
}

# Step 3: Remove worktree using robocopy for long path support
Write-Host "Removing worktree..." -ForegroundColor Yellow

# Create empty temp directory for robocopy mirror
$EmptyDir = "$env:TEMP\empty_$(Get-Random)"
New-Item -ItemType Directory -Path $EmptyDir -Force | Out-Null

# Use robocopy to mirror empty directory (effectively deleting worktree)
robocopy $EmptyDir $WorktreePath /MIR /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null

# Clean up
Remove-Item $EmptyDir -Force -ErrorAction SilentlyContinue
Remove-Item $WorktreePath -Force -ErrorAction SilentlyContinue

if (Test-Path $WorktreePath) {
    Write-Host "X Failed to remove worktree directory" -ForegroundColor Red
    Pop-Location
    exit 1
}

Write-Host "OK Worktree removed" -ForegroundColor Green

# Step 4: Delete branch (only if merged or force delete)
Write-Host "Deleting branch: $BranchName" -ForegroundColor Yellow
git branch -d $BranchName 2>$null

if ($LASTEXITCODE -ne 0) {
    # Branch not merged - ask user
    Write-Host "WARNING: Branch not merged to main. Force delete? [y/N]" -ForegroundColor Yellow
    $Response = Read-Host

    if ($Response -eq 'y' -or $Response -eq 'Y') {
        git branch -D $BranchName
        Write-Host "OK Branch force-deleted" -ForegroundColor Green
    } else {
        Write-Host "OK Branch kept (not deleted)" -ForegroundColor Yellow
    }
} else {
    Write-Host "OK Branch deleted" -ForegroundColor Green
}

# Step 5: Prune worktree references
git worktree prune

Pop-Location

Write-Host "`nOK Cleanup complete!" -ForegroundColor Green
Write-Host "  Worktree removed: $FeatureName`n" -ForegroundColor White
