param(
    [string]$ReleaseName = "neoforge-mod-agent-public-$(Get-Date -Format 'yyyyMMdd-HHmmss')",
    [string]$OutputRoot = "dist",
    [string]$Rc1WorkspaceName = "rc1-release-smoke",
    [string]$Rc1BenchmarkRunName = "rc1-release-bench",
    [switch]$NoZip,
    [switch]$Overwrite
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$outputRootPath = Join-Path $repoRoot $OutputRoot
$stagePath = Join-Path $outputRootPath $ReleaseName
$zipPath = Join-Path $outputRootPath "$ReleaseName.zip"

$excludedPaths = @(
    "workspace",
    ".tmp",
    "dist",
    ".gradle-user-home",
    ".gradle-default-user-home",
    ".playwright-mcp",
    ".codex",
    "__pycache__",
    ".pytest_cache",
    "*.pyc",
    "*.pyo",
    "*.egg-info"
)

$includeDirs = @(
    ".github",
    "docs",
    "examples",
    "scripts",
    "src",
    "templates",
    "tests"
)

$includeFiles = @(
    ".gitignore",
    "README.md",
    "pyproject.toml"
)

function Copy-ReleasePath {
    param(
        [Parameter(Mandatory = $true)][string]$RelativePath
    )

    $source = Join-Path $repoRoot $RelativePath
    if (-not (Test-Path -LiteralPath $source)) {
        return $false
    }

    $target = Join-Path $stagePath $RelativePath
    $targetParent = Split-Path -Parent $target
    if (-not (Test-Path -LiteralPath $targetParent)) {
        New-Item -ItemType Directory -Path $targetParent | Out-Null
    }

    Copy-Item -LiteralPath $source -Destination $target -Recurse -Force
    return $true
}

function Copy-EvidenceFile {
    param(
        [Parameter(Mandatory = $true)][string]$SourceRelativePath,
        [Parameter(Mandatory = $true)][string]$TargetRelativePath,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $source = Join-Path $repoRoot $SourceRelativePath
    if (-not (Test-Path -LiteralPath $source)) {
        return [ordered]@{
            label = $Label
            source = $SourceRelativePath
            copied = $false
            path = $null
            bytes = 0
        }
    }

    $target = Join-Path $stagePath $TargetRelativePath
    $targetParent = Split-Path -Parent $target
    if (-not (Test-Path -LiteralPath $targetParent)) {
        New-Item -ItemType Directory -Path $targetParent | Out-Null
    }

    Copy-Item -LiteralPath $source -Destination $target -Force
    $targetItem = Get-Item -LiteralPath $target
    return [ordered]@{
        label = $Label
        source = $SourceRelativePath
        copied = $true
        path = $TargetRelativePath
        bytes = $targetItem.Length
    }
}

if ((Test-Path -LiteralPath $stagePath) -and -not $Overwrite) {
    throw "Release directory already exists: $stagePath. Use -Overwrite or choose another -ReleaseName."
}

if ((Test-Path -LiteralPath $zipPath) -and -not $Overwrite -and -not $NoZip) {
    throw "Release zip already exists: $zipPath. Use -Overwrite or choose another -ReleaseName."
}

if ((Test-Path -LiteralPath $stagePath) -and $Overwrite) {
    Remove-Item -LiteralPath $stagePath -Recurse -Force
}

if ((Test-Path -LiteralPath $zipPath) -and $Overwrite -and -not $NoZip) {
    Remove-Item -LiteralPath $zipPath -Force
}

if (-not (Test-Path -LiteralPath $outputRootPath)) {
    New-Item -ItemType Directory -Path $outputRootPath | Out-Null
}

New-Item -ItemType Directory -Path $stagePath | Out-Null

$copiedDirs = @()
foreach ($dir in $includeDirs) {
    if (Copy-ReleasePath -RelativePath $dir) {
        $copiedDirs += $dir
    }
}

$copiedFiles = @()
foreach ($file in $includeFiles) {
    if (Copy-ReleasePath -RelativePath $file) {
        $copiedFiles += $file
    }
}

$transientDirectoryNames = @("__pycache__", ".pytest_cache")
Get-ChildItem -LiteralPath $stagePath -Directory -Recurse -Force |
    Where-Object { $transientDirectoryNames -contains $_.Name -or $_.Name.EndsWith(".egg-info") } |
    Remove-Item -Recurse -Force

Get-ChildItem -LiteralPath $stagePath -File -Recurse -Force |
    Where-Object { $_.Name.EndsWith(".pyc") -or $_.Name.EndsWith(".pyo") } |
    Remove-Item -Force

$rc1AgentDir = "workspace\$Rc1WorkspaceName\.agent"
$rc1BenchmarkAgentDir = "workspace\benchmark-runs\$Rc1BenchmarkRunName\.agent"
$rc1BenchmarkRunsDir = "workspace\benchmark-runs\$Rc1BenchmarkRunName\runs"

$evidenceFiles = @(
    @{ Source = "$rc1AgentDir\modspec.json"; Target = "release-artifacts\evidence\rc1-develop-repair\modspec.json"; Label = "RC1 ModSpec from agent develop" },
    @{ Source = "$rc1AgentDir\generation-summary.json"; Target = "release-artifacts\evidence\rc1-develop-repair\generation-summary.json"; Label = "RC1 deterministic generator summary" },
    @{ Source = "$rc1AgentDir\agent-run.json"; Target = "release-artifacts\evidence\rc1-develop-repair\agent-run.json"; Label = "RC1 agent run JSON" },
    @{ Source = "$rc1AgentDir\agent-run.md"; Target = "release-artifacts\evidence\rc1-develop-repair\agent-run.md"; Label = "RC1 agent run Markdown" },
    @{ Source = "$rc1AgentDir\agent-decisions.md"; Target = "release-artifacts\evidence\rc1-develop-repair\agent-decisions.md"; Label = "RC1 agent decisions" },
    @{ Source = "$rc1AgentDir\agent-repair-plan.json"; Target = "release-artifacts\evidence\rc1-develop-repair\agent-repair-plan.json"; Label = "RC1 repair plan JSON" },
    @{ Source = "$rc1AgentDir\agent-repair-plan.md"; Target = "release-artifacts\evidence\rc1-develop-repair\agent-repair-plan.md"; Label = "RC1 repair plan Markdown" },
    @{ Source = "$rc1AgentDir\agent-trace-summary.json"; Target = "release-artifacts\evidence\rc1-develop-repair\agent-trace-summary.json"; Label = "RC1 trace summary JSON" },
    @{ Source = "$rc1AgentDir\agent-trace-summary.md"; Target = "release-artifacts\evidence\rc1-develop-repair\agent-trace-summary.md"; Label = "RC1 trace summary Markdown" },
    @{ Source = "$rc1AgentDir\tool-call-trace.json"; Target = "release-artifacts\evidence\rc1-develop-repair\tool-call-trace.json"; Label = "RC1 real tool-call trace" },
    @{ Source = "$rc1AgentDir\prompt-trace.json"; Target = "release-artifacts\evidence\rc1-develop-repair\prompt-trace.json"; Label = "RC1 prompt trace" },
    @{ Source = "$rc1AgentDir\rag-context.json"; Target = "release-artifacts\evidence\rc1-develop-repair\rag-context.json"; Label = "RC1 planner RAG context" },
    @{ Source = "$rc1AgentDir\rag-context.md"; Target = "release-artifacts\evidence\rc1-develop-repair\rag-context.md"; Label = "RC1 planner RAG context Markdown" },
    @{ Source = "$rc1AgentDir\repair-rag-context.json"; Target = "release-artifacts\evidence\rc1-develop-repair\repair-rag-context.json"; Label = "RC1 repair RAG context" },
    @{ Source = "$rc1AgentDir\repair-rag-context.md"; Target = "release-artifacts\evidence\rc1-develop-repair\repair-rag-context.md"; Label = "RC1 repair RAG context Markdown" },
    @{ Source = "$rc1AgentDir\reviewer-report.json"; Target = "release-artifacts\evidence\rc1-develop-repair\reviewer-report.json"; Label = "RC1 LLM reviewer report JSON" },
    @{ Source = "$rc1AgentDir\reviewer-report.md"; Target = "release-artifacts\evidence\rc1-develop-repair\reviewer-report.md"; Label = "RC1 LLM reviewer report Markdown" },
    @{ Source = "$rc1AgentDir\audit-report.json"; Target = "release-artifacts\evidence\rc1-develop-repair\audit-report.json"; Label = "RC1 audit report JSON" },
    @{ Source = "$rc1AgentDir\audit-report.md"; Target = "release-artifacts\evidence\rc1-develop-repair\audit-report.md"; Label = "RC1 audit report Markdown" },
    @{ Source = "$rc1AgentDir\structured-patch-plan.json"; Target = "release-artifacts\evidence\rc1-develop-repair\structured-patch-plan.json"; Label = "RC1 structured patch plan" },
    @{ Source = "$rc1AgentDir\structured-patch-diff.md"; Target = "release-artifacts\evidence\rc1-develop-repair\structured-patch-diff.md"; Label = "RC1 structured patch diff" },
    @{ Source = "$rc1AgentDir\structured-patch-report.json"; Target = "release-artifacts\evidence\rc1-develop-repair\structured-patch-report.json"; Label = "RC1 structured patch report" },
    @{ Source = "$rc1AgentDir\structured-patch-rollback-report.json"; Target = "release-artifacts\evidence\rc1-develop-repair\structured-patch-rollback-report.json"; Label = "RC1 rollback evidence" },
    @{ Source = "$rc1AgentDir\resource-quality-report.json"; Target = "release-artifacts\evidence\rc1-develop-repair\resource-quality-report.json"; Label = "RC1 resource quality report JSON" },
    @{ Source = "$rc1AgentDir\resource-quality-report.md"; Target = "release-artifacts\evidence\rc1-develop-repair\resource-quality-report.md"; Label = "RC1 resource quality report Markdown" },
    @{ Source = "$rc1AgentDir\texture-atlas.png"; Target = "release-artifacts\evidence\rc1-develop-repair\texture-atlas.png"; Label = "RC1 generated texture atlas" },
    @{ Source = "$rc1BenchmarkAgentDir\agent-benchmark-report.html"; Target = "release-artifacts\evidence\rc1-benchmark\agent-benchmark-report.html"; Label = "RC1 agent bench report HTML" },
    @{ Source = "$rc1BenchmarkAgentDir\agent-benchmark-report.json"; Target = "release-artifacts\evidence\rc1-benchmark\agent-benchmark-report.json"; Label = "RC1 agent bench report JSON" },
    @{ Source = "$rc1BenchmarkAgentDir\agent-benchmark-report.md"; Target = "release-artifacts\evidence\rc1-benchmark\agent-benchmark-report.md"; Label = "RC1 agent bench report Markdown" },
    @{ Source = "$rc1BenchmarkRunsDir\01-develop_ruby_tech_refine\.agent\agent-run.json"; Target = "release-artifacts\evidence\rc1-benchmark\cases\01-develop\agent-run.json"; Label = "RC1 bench develop case agent run" },
    @{ Source = "$rc1BenchmarkRunsDir\01-develop_ruby_tech_refine\.agent\tool-call-trace.json"; Target = "release-artifacts\evidence\rc1-benchmark\cases\01-develop\tool-call-trace.json"; Label = "RC1 bench develop case tool trace" },
    @{ Source = "$rc1BenchmarkRunsDir\01-develop_ruby_tech_refine\.agent\reviewer-report.json"; Target = "release-artifacts\evidence\rc1-benchmark\cases\01-develop\reviewer-report.json"; Label = "RC1 bench develop case reviewer report" },
    @{ Source = "$rc1BenchmarkRunsDir\02-repair_mods_toml_structured_patch-setup\.agent\agent-run.json"; Target = "release-artifacts\evidence\rc1-benchmark\cases\02-repair\agent-run.json"; Label = "RC1 bench repair case agent run" },
    @{ Source = "$rc1BenchmarkRunsDir\02-repair_mods_toml_structured_patch-setup\.agent\tool-call-trace.json"; Target = "release-artifacts\evidence\rc1-benchmark\cases\02-repair\tool-call-trace.json"; Label = "RC1 bench repair case tool trace" },
    @{ Source = "$rc1BenchmarkRunsDir\02-repair_mods_toml_structured_patch-setup\.agent\reviewer-report.json"; Target = "release-artifacts\evidence\rc1-benchmark\cases\02-repair\reviewer-report.json"; Label = "RC1 bench repair case reviewer report" },
    @{ Source = "$rc1BenchmarkRunsDir\02-repair_mods_toml_structured_patch-setup\.agent\structured-patch-rollback-report.json"; Target = "release-artifacts\evidence\rc1-benchmark\cases\02-repair\structured-patch-rollback-report.json"; Label = "RC1 bench repair case rollback evidence" }
)

$evidence = @()
foreach ($item in $evidenceFiles) {
    $evidence += Copy-EvidenceFile `
        -SourceRelativePath $item.Source `
        -TargetRelativePath $item.Target `
        -Label $item.Label
}

$forbiddenRoots = @("workspace", ".tmp", "dist", ".gradle-user-home", ".gradle-default-user-home", ".playwright-mcp", ".codex")
$violations = @()
foreach ($name in $forbiddenRoots) {
    $candidate = Join-Path $stagePath $name
    if (Test-Path -LiteralPath $candidate) {
        $violations += $name
    }
}

if ($violations.Count -gt 0) {
    throw "Release staging contains excluded root paths: $($violations -join ', ')"
}

$fileStats = Get-ChildItem -LiteralPath $stagePath -File -Recurse -Force | Measure-Object -Property Length -Sum
$manifest = [ordered]@{
    release_name = $ReleaseName
    generated_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    source_root = $repoRoot
    stage_path = $stagePath
    zip_path = if ($NoZip) { $null } else { $zipPath }
    included_dirs = $copiedDirs
    included_files = $copiedFiles
    excluded_paths = $excludedPaths
    rc1_workspace_name = $Rc1WorkspaceName
    rc1_benchmark_run_name = $Rc1BenchmarkRunName
    curated_evidence = $evidence
    file_count = $fileStats.Count
    size_bytes = [int64]($fileStats.Sum)
}

$manifestJsonPath = Join-Path $stagePath "release-manifest.json"
$manifest | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 -Path $manifestJsonPath

$copiedEvidence = @($evidence | Where-Object { $_.copied })
$missingEvidence = @($evidence | Where-Object { -not $_.copied })
$manifestMarkdown = @(
    "# Public Release Manifest",
    "",
    "- Release: ``$ReleaseName``",
    "- Generated UTC: ``$($manifest.generated_at_utc)``",
    "- File count before manifest write: ``$($manifest.file_count)``",
    "- Size before manifest write: ``$($manifest.size_bytes)`` bytes",
    "",
    "## Included",
    "",
    ($copiedDirs | ForEach-Object { "- ``$_/``" }),
    ($copiedFiles | ForEach-Object { "- ``$_``" }),
    "",
    "## Excluded",
    "",
    ($excludedPaths | ForEach-Object { "- ``$_``" }),
    "",
    "## Curated Evidence",
    "",
    ($copiedEvidence | ForEach-Object { "- $($_.label): ``$($_.path)``" })
)

if ($missingEvidence.Count -gt 0) {
    $manifestMarkdown += @(
        "",
        "## Missing Optional Evidence",
        "",
        ($missingEvidence | ForEach-Object { "- $($_.label): ``$($_.source)``" })
    )
}

$manifestMarkdown | Set-Content -Encoding utf8 -Path (Join-Path $stagePath "release-manifest.md")

if (-not $NoZip) {
    Push-Location $outputRootPath
    try {
        Compress-Archive -Path ".\$ReleaseName" -DestinationPath $zipPath -Force
    }
    finally {
        Pop-Location
    }
}

Write-Output "Release directory: $stagePath"
if (-not $NoZip) {
    Write-Output "Release zip: $zipPath"
}
Write-Output "Manifest: $manifestJsonPath"
