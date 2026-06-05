param(
    [string]$RunName = "",
    [ValidateSet("rules", "llm", "auto")]
    [string]$Planner = "llm",
    [switch]$UseRealLlm,
    [switch]$Build,
    [int]$MaxIterations = 5,
    [int]$BenchEvalLimit = 1,
    [int]$BenchRepairLimit = 1
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot
$env:PYTHONPATH = (Resolve-Path ".\src")

if ([string]::IsNullOrWhiteSpace($RunName)) {
    $RunName = "rc1-showcase-$((Get-Date).ToString('yyyyMMdd-HHmmss'))"
}

$Provider = "mock"
if ($UseRealLlm) {
    $Provider = "openai-compatible"
}

$BuildFlag = "--no-build"
if ($Build) {
    $BuildFlag = "--build"
}

$DevelopWorkspace = "$RunName-develop"
$BenchRunName = "$RunName-bench"
$RepairGoal = "Fix audit failures using safe structured patches."

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

Write-Host "== NeoForge Mod Agent RC1 Showcase =="
Write-Host "Project root: $ProjectRoot"
Write-Host "Run name: $RunName"
Write-Host "Develop workspace: $DevelopWorkspace"
Write-Host "Planner: $Planner"
Write-Host "Provider: $Provider"
Write-Host "Build: $($Build.IsPresent)"
Write-Host ""

Invoke-AgentCli -Arguments @(
    "agent", "develop",
    "Create a ruby mod with a ruby item, ruby block, ruby ore, ruby sword, ruby tool set, and ruby armor set.",
    "--planner", $Planner,
    "--llm-provider", $Provider,
    "--workspace-name", $DevelopWorkspace,
    $BuildFlag,
    "--max-iterations", "$MaxIterations",
    "--json"
)

Invoke-AgentCli -Arguments @(
    "agent", "repair", $DevelopWorkspace,
    "--goal", $RepairGoal,
    "--planner", $Planner,
    "--llm-provider", $Provider,
    "--max-iterations", "$MaxIterations",
    $BuildFlag,
    "--audit",
    "--json"
)

Invoke-AgentCli -Arguments @(
    "agent", "bench",
    "--run-name", $BenchRunName,
    "--llm-provider", $Provider,
    "--eval-limit", "$BenchEvalLimit",
    "--repair-limit", "$BenchRepairLimit",
    $BuildFlag,
    "--audit",
    "--json"
)

$DevelopAgentDir = Join-Path $ProjectRoot "workspace\$DevelopWorkspace\.agent"
$BenchAgentDir = Join-Path $ProjectRoot "workspace\benchmark-runs\$BenchRunName\.agent"

Write-Host ""
Write-Host "== RC1 showcase artifacts =="
Write-Host "Develop run:       $(Join-Path $DevelopAgentDir "agent-run.md")"
Write-Host "Tool trace:        $(Join-Path $DevelopAgentDir "tool-call-trace.json")"
Write-Host "Reviewer report:   $(Join-Path $DevelopAgentDir "reviewer-report.json")"
Write-Host "Audit report:      $(Join-Path $DevelopAgentDir "audit-report.json")"
Write-Host "Structured patch:  $(Join-Path $DevelopAgentDir "structured-patch-report.json")"
Write-Host "Rollback evidence: $(Join-Path $DevelopAgentDir "structured-patch-rollback-report.json")"
Write-Host "Benchmark report:  $(Join-Path $BenchAgentDir "agent-benchmark-report.md")"
Write-Host "Benchmark HTML:    $(Join-Path $BenchAgentDir "agent-benchmark-report.html")"
Write-Host ""
Write-Host "Suggested walkthrough: agent-run -> tool trace -> reviewer -> repair evidence -> agent bench metrics."
