param(
    [string]$RunName = "v50-portfolio",
    [ValidateSet("rules", "llm", "auto")]
    [string]$Planner = "llm",
    [switch]$UseRealLlm,
    [switch]$RunQualityGate,
    [switch]$Build
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot
$env:PYTHONPATH = (Resolve-Path ".\src")

$Provider = "mock"
$CandidateProvider = "mock"
if ($UseRealLlm) {
    $Provider = "openai-compatible"
    $CandidateProvider = "openai-compatible"
}

$CliArgs = @(
    "-m", "agent.cli",
    "portfolio-demo",
    "--run-name", $RunName,
    "--planner", $Planner,
    "--llm-provider", $Provider,
    "--candidate-provider", $CandidateProvider,
    "--eval-limit", "2",
    "--json"
)

if ($RunQualityGate) {
    $CliArgs += "--quality-gate"
}

if ($Build) {
    $CliArgs += "--build"
} else {
    $CliArgs += "--no-build"
}

Write-Host "== NeoForge Mod Agent V5.0 Portfolio Demo =="
Write-Host "Project root: $ProjectRoot"
Write-Host "Planner: $Planner"
Write-Host "Provider: $Provider"
Write-Host "Run name: $RunName"
Write-Host ""

py -3.11 @CliArgs

$PortfolioDir = Join-Path $ProjectRoot "workspace\portfolio-runs\$RunName"
$Report = Join-Path $PortfolioDir ".agent\portfolio-demo-report.md"
$Dashboard = Join-Path $PortfolioDir "runs\dashboard-runs\$RunName-dashboard\index.html"

Write-Host ""
Write-Host "== Demo artifacts =="
Write-Host "Portfolio report: $Report"
Write-Host "Dashboard HTML:    $Dashboard"
Write-Host ""
Write-Host "Suggested next step:"
Write-Host "Start by opening the portfolio report, then open the dashboard HTML for the visual walkthrough."
