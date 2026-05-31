param(
    [string]$RunName = "v80-portfolio-showcase",
    [ValidateSet("rules", "llm", "auto")]
    [string]$Planner = "llm",
    [switch]$UseRealLlm,
    [switch]$RunQualityGate,
    [switch]$Build,
    [switch]$SkipGoldenCases,
    [switch]$SkipFailureSample
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot
$env:PYTHONPATH = (Resolve-Path ".\src")

$Provider = "mock"
if ($UseRealLlm) {
    $Provider = "openai-compatible"
}

$BuildFlag = "--no-build"
if ($Build) {
    $BuildFlag = "--build"
}

function Invoke-AgentCli {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    Write-Host ""
    Write-Host ">> py -3.11 -m agent.cli $($Arguments -join ' ')"
    py -3.11 -m agent.cli @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "agent.cli failed with exit code $LASTEXITCODE"
    }
}

Write-Host "== NeoForge Mod Agent Portfolio Showcase =="
Write-Host "Project root: $ProjectRoot"
Write-Host "Run name: $RunName"
Write-Host "Planner: $Planner"
Write-Host "Provider: $Provider"
Write-Host "Build: $($Build.IsPresent)"
Write-Host ""

$PortfolioArgs = @(
    "portfolio-demo",
    "--run-name", $RunName,
    "--planner", $Planner,
    "--llm-provider", $Provider,
    "--candidate-provider", $Provider,
    "--eval-limit", "2",
    $BuildFlag,
    "--json"
)

if ($RunQualityGate) {
    $PortfolioArgs += "--quality-gate"
}

Invoke-AgentCli -Arguments $PortfolioArgs

if (-not $SkipGoldenCases) {
    Invoke-AgentCli -Arguments @(
        "agent", "generate",
        "Create a ruby mod with ruby item, ruby block, ruby ore, ruby sword, ruby tool set, and ruby armor set.",
        "--planner", $Planner,
        "--llm-provider", $Provider,
        "--workspace-name", "$RunName-ruby-basic",
        "--overwrite",
        $BuildFlag,
        "--json"
    )

    Invoke-AgentCli -Arguments @(
        "generate-from-spec", ".\examples\machine_ruby_compressor.json",
        "--workspace-name", "$RunName-machine",
        "--overwrite",
        "--audit",
        $BuildFlag,
        "--json"
    )

    Invoke-AgentCli -Arguments @(
        "generate-from-spec", ".\examples\progression_gameplay_loop.json",
        "--workspace-name", "$RunName-gameplay-loop",
        "--overwrite",
        "--audit",
        $BuildFlag,
        "--json"
    )

    Invoke-AgentCli -Arguments @(
        "generate-from-spec", ".\examples\quest_guide_gameplay_loop.json",
        "--workspace-name", "$RunName-quest-guide",
        "--overwrite",
        "--audit",
        $BuildFlag,
        "--json"
    )

    Invoke-AgentCli -Arguments @(
        "generate-from-spec", ".\examples\resource_quality_showcase.json",
        "--workspace-name", "$RunName-resource-quality",
        "--overwrite",
        "--audit",
        $BuildFlag,
        "--json"
    )
}

if (-not $SkipFailureSample) {
    $FailureArgs = @(
        "failure-lab",
        "--run-name", "$RunName-failure-lab",
        "--case", "delete_model",
        "--json"
    )

    $RepairEvalArgs = @(
        "repair-eval",
        "--run-name", "$RunName-repair-eval",
        "--case", "delete_model",
        "--json"
    )

    if ($Build) {
        $FailureArgs += "--build"
        $RepairEvalArgs += "--build"
    }

    Invoke-AgentCli -Arguments $FailureArgs
    Invoke-AgentCli -Arguments $RepairEvalArgs
}

$PortfolioDir = Join-Path $ProjectRoot "workspace\portfolio-runs\$RunName"
$Report = Join-Path $PortfolioDir ".agent\portfolio-demo-report.md"
$Dashboard = Join-Path $PortfolioDir "runs\dashboard-runs\$RunName-dashboard\index.html"

Write-Host ""
Write-Host "== Showcase artifacts =="
Write-Host "Portfolio report: $Report"
Write-Host "Dashboard HTML:    $Dashboard"
Write-Host "Ruby basic:        $(Join-Path $ProjectRoot "workspace\$RunName-ruby-basic\.agent\audit-report.json")"
Write-Host "Machine demo:      $(Join-Path $ProjectRoot "workspace\$RunName-machine\.agent\audit-report.json")"
Write-Host "Gameplay loop:     $(Join-Path $ProjectRoot "workspace\$RunName-gameplay-loop\.agent\progression-report.md")"
Write-Host "Quest guide:       $(Join-Path $ProjectRoot "workspace\$RunName-quest-guide\.agent\quest-report.md")"
Write-Host "Resource preview:  $(Join-Path $ProjectRoot "workspace\$RunName-resource-quality\.agent\resource-quality-report.md")"
Write-Host "Failure lab:       $(Join-Path $ProjectRoot "workspace\failure-lab-runs\$RunName-failure-lab\.agent\failure-lab-report.md")"
Write-Host "Repair eval:       $(Join-Path $ProjectRoot "workspace\repair-eval-runs\$RunName-repair-eval\.agent\repair-eval-report.md")"
Write-Host ""
Write-Host "Suggested walkthrough: report -> dashboard -> ModSpec -> audit -> failure/repair reports."
