# Git Worktree Management Scripts

Quick PowerShell scripts for managing ephemeral worktrees in the PEIT Map Creator project.

## Quick Start

### Create New Worktree
```powershell
cd .git-worktrees-scripts
.\peit-new.ps1 my-feature-name
```

**What it does:**
- Creates worktree at `.git-worktrees/my-feature-name`
- Creates branch `feature/my-feature-name` from `main`
- Opens new VS Code window
- Installs dependencies in background terminal

### Finish & Cleanup Worktree
```powershell
.\peit-done.ps1 my-feature-name
```

**What it does:**
- Removes `node_modules` for faster deletion
- Removes worktree directory
- Deletes branch (asks for confirmation if not merged)
- Prunes stale references

### List Active Worktrees
```powershell
.\peit-list.ps1
```

**What it shows:**
- All active worktrees
- Disk space usage per worktree
- Total disk usage

### Cleanup Orphaned Branches
```powershell
.\peit-cleanup.ps1
```

**What it does:**
- Finds feature/* branches without corresponding worktrees
- Shows list of orphaned branches
- Asks for confirmation before deletion
- Deletes orphaned branches and prunes references

**When to use:**
- After manually deleting worktree directories
- When cleanup script failed mid-execution
- Periodic maintenance to remove stale branches

## Usage Examples

### Example: Create feature worktree
```powershell
cd C:\Users\lukas\OneDrive\OSIT\Python\APPEIT\appeit_map_creator\.git-worktrees-scripts
.\peit-new.ps1 new-processing-icon
```

Result:
- Branch: `feature/new-processing-icon`
- Path: `.git-worktrees\new-processing-icon`
- VS Code opens automatically
- Dependencies install in background

### Example: Clean up finished feature
```powershell
.\peit-done.ps1 new-processing-icon
```

Result:
- Worktree removed
- Branch deleted (or kept if unmerged)
- Disk space freed

## Optional: Global PowerShell Aliases

Add to your PowerShell profile (`$PROFILE`) for even faster access:

```powershell
# Worktree shortcuts
function peit-new {
    & "C:\Users\lukas\OneDrive\OSIT\Python\APPEIT\appeit_map_creator\.git-worktrees-scripts\peit-new.ps1" @args
}
function peit-done {
    & "C:\Users\lukas\OneDrive\OSIT\Python\APPEIT\appeit_map_creator\.git-worktrees-scripts\peit-done.ps1" @args
}
function peit-list {
    & "C:\Users\lukas\OneDrive\OSIT\Python\APPEIT\appeit_map_creator\.git-worktrees-scripts\peit-list.ps1"
}
```

Then from anywhere:
```powershell
peit-new my-feature    # Create worktree
peit-done my-feature   # Clean up worktree
peit-list              # Show active worktrees
```

## Workflow

**Standard Development Flow:**
1. **Start feature**: `peit-new feature-name`
2. **Work in VS Code**: Code opens automatically
3. **Commit & push**: Normal git workflow
4. **Create PR**: Merge to main when ready
5. **Clean up**: `peit-done feature-name`

**Parallel Development:**
```powershell
# Start feature A
peit-new feature-a
# VS Code window 1 opens

# Start feature B (while A is in progress)
peit-new feature-b
# VS Code window 2 opens

# Work on both simultaneously!
# Each has its own dependencies, dev server, etc.

# Finish feature A
peit-done feature-a

# Continue working on feature B in its own window
```

## Tips

- **Naming**: Use descriptive feature names (e.g., `fix-mobile-basemap`, `add-pdf-export`)
- **Cleanup**: Always run `peit-done` after merging PR to free disk space
- **Disk Space**: Run `peit-list` periodically to check total usage
- **Multiple Features**: Keep max 2-3 worktrees active at once (RAM constraint)

## Troubleshooting

### "Worktree already exists"
The worktree directory wasn't cleaned up properly. Manually delete:
```powershell
Remove-Item .git-worktrees\feature-name -Recurse -Force
git worktree prune
```

### "Branch already exists"
Delete the old branch first:
```powershell
git branch -D feature/feature-name
```

### Path too long errors (Windows)
This is a known Windows limitation. The scripts remove `node_modules` first to minimize this, but if it still happens:
1. Rename the worktree folder to something short (e.g., `x`)
2. Delete the renamed folder
3. Run `git worktree prune`