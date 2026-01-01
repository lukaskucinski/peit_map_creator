# List all active worktrees with disk usage
# Usage: .\peit-list.ps1

$ProjectRoot = "C:\Users\lukas\OneDrive\OSIT\Python\APPEIT\appeit_map_creator"

Write-Host "`n=== Active Worktrees ===" -ForegroundColor Cyan

Push-Location $ProjectRoot

# Get worktree list from git
git worktree list

Write-Host "`n=== Disk Space Usage ===" -ForegroundColor Cyan

# Calculate disk usage for each worktree
$WorktreesPath = "$ProjectRoot\.git-worktrees"
if (Test-Path $WorktreesPath) {
    Get-ChildItem $WorktreesPath -Directory | ForEach-Object {
        $Size = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue |
                 Measure-Object -Property Length -Sum).Sum / 1MB

        $Color = if ($Size -gt 500) { "Red" } elseif ($Size -gt 200) { "Yellow" } else { "Green" }
        Write-Host ("  {0,-30} {1,8:N2} MB" -f $_.Name, $Size) -ForegroundColor $Color
    }

    # Total
    $TotalSize = (Get-ChildItem $WorktreesPath -Recurse -File -ErrorAction SilentlyContinue |
                  Measure-Object -Property Length -Sum).Sum / 1MB
    Write-Host "`n  Total: $([math]::Round($TotalSize, 2)) MB" -ForegroundColor Cyan
} else {
    Write-Host "  No worktrees directory found" -ForegroundColor Gray
}

Pop-Location

Write-Host ""