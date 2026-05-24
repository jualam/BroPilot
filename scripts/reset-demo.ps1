param(
    [string]$RepoPath = "D:\bropilot-demo",
    [string]$Baseline = "d672866",
    [string]$Branch = "demo-working"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $RepoPath)) {
    throw "Demo repo path not found: $RepoPath"
}

Set-Location -LiteralPath $RepoPath

if (-not (Test-Path -LiteralPath ".git")) {
    throw "Path is not a git repository: $RepoPath"
}

Write-Host "Resetting demo repo at $RepoPath"

git reset --hard
git clean -fd -- .gitagent workspace agent.yaml SOUL.md memory

git switch main
git reset --hard $Baseline

$branchExists = git branch --list $Branch
if ($branchExists) {
    git branch -D $Branch
}

git switch -c $Branch
python -m pytest

Write-Host "Demo repo is ready on branch $Branch at baseline $Baseline"
