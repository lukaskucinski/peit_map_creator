# Quick worktree creation script
# Usage: .\peit-new.ps1 feature-name

param(
    [Parameter(Mandatory=$true)]
    [string]$FeatureName
)

$ProjectRoot = "C:\Users\lukas\OneDrive\OSIT\Python\APPEIT\appeit_map_creator"
$WorktreePath = "$ProjectRoot\.git-worktrees\$FeatureName"
$BranchName = "feature/$FeatureName"

Write-Host "`n=== Creating Worktree: $FeatureName ===" -ForegroundColor Cyan

# Check if worktree already exists
if (Test-Path $WorktreePath) {
    Write-Host "X Worktree already exists: $WorktreePath" -ForegroundColor Red
    exit 1
}

# Navigate to project root
Push-Location $ProjectRoot

# Create worktree
Write-Host "Creating worktree from main branch..." -ForegroundColor Yellow
git worktree add -b $BranchName $WorktreePath main

if ($LASTEXITCODE -ne 0) {
    Write-Host "X Failed to create worktree" -ForegroundColor Red
    Pop-Location
    exit 1
}

Write-Host "OK Worktree created: $WorktreePath" -ForegroundColor Green

# Open in new VS Code window
Write-Host "Opening VS Code..." -ForegroundColor Yellow
code -n $WorktreePath

# Install dependencies in background
Write-Host "Installing dependencies (background process)..." -ForegroundColor Yellow

# Create temp script file for background installation
$TempScript = "$env:TEMP\peit-install-$FeatureName.ps1"
$InstallPath = "$WorktreePath\peit-app-homepage"

# Write installation script to temp file
$InstallScript = @"
Set-Location '$InstallPath'
Write-Host 'Installing pnpm dependencies...' -ForegroundColor Yellow
pnpm install
if (`$LASTEXITCODE -eq 0) {
    Write-Host '`nOK Dependencies installed successfully' -ForegroundColor Green
} else {
    Write-Host '`nX Dependency installation failed' -ForegroundColor Red
}
Write-Host '`nPress any key to close...' -ForegroundColor Gray
`$null = Read-Host
"@

$InstallScript | Out-File -FilePath $TempScript -Encoding UTF8

# Start background PowerShell process
Start-Process -FilePath "powershell" -ArgumentList "-NoExit","-ExecutionPolicy","Bypass","-File",$TempScript

Pop-Location

Write-Host "`nOK Setup complete!" -ForegroundColor Green
Write-Host "  Branch: $BranchName" -ForegroundColor White
Write-Host "  Path: $WorktreePath" -ForegroundColor White
Write-Host "  VS Code: Opening in new window" -ForegroundColor White
Write-Host "  Dependencies: Installing in background terminal`n" -ForegroundColor White
