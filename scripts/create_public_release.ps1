param(
    [string]$ReleaseName = "neoforge-mod-agent-public-$(Get-Date -Format 'yyyyMMdd-HHmmss')",
    [string]$OutputRoot = "dist",
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
    "tests",
    "examplemod-template-26.1.2"
)

$includeFiles = @(
    ".gitignore",
    "README.md",
    "pyproject.toml",
    "TASK.md"
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

$evidence = @()
$evidence += Copy-EvidenceFile `
    -SourceRelativePath "workspace\v81-provider-layer-smoke-20260514\.agent\agent-run-replay.html" `
    -TargetRelativePath "release-artifacts\evidence\session-replay\agent-run-replay.html" `
    -Label "Session replay trace viewer"
$evidence += Copy-EvidenceFile `
    -SourceRelativePath "workspace\benchmark-runs\v82-benchmark-page-offline-20260514\.agent\benchmark-report.html" `
    -TargetRelativePath "release-artifacts\evidence\benchmark-report\benchmark-report.html" `
    -Label "Benchmark report HTML"
$evidence += Copy-EvidenceFile `
    -SourceRelativePath "workspace\benchmark-runs\v82-benchmark-page-offline-20260514\.agent\benchmark-report.json" `
    -TargetRelativePath "release-artifacts\evidence\benchmark-report\benchmark-report.json" `
    -Label "Benchmark report JSON"
$evidence += Copy-EvidenceFile `
    -SourceRelativePath "workspace\benchmark-runs\v82-benchmark-page-offline-20260514\.agent\benchmark-report.md" `
    -TargetRelativePath "release-artifacts\evidence\benchmark-report\benchmark-report.md" `
    -Label "Benchmark report Markdown"
$evidence += Copy-EvidenceFile `
    -SourceRelativePath "workspace\evidence-chain-runs\local-evidence-chain\.agent\evidence-chain-report.json" `
    -TargetRelativePath "release-artifacts\evidence\evidence-chain\evidence-chain-report.json" `
    -Label "Layered evidence chain JSON"
$evidence += Copy-EvidenceFile `
    -SourceRelativePath "workspace\evidence-chain-runs\local-evidence-chain\.agent\evidence-chain-report.md" `
    -TargetRelativePath "release-artifacts\evidence\evidence-chain\evidence-chain-report.md" `
    -Label "Layered evidence chain Markdown"
$evidence += Copy-EvidenceFile `
    -SourceRelativePath "workspace\v80-resource-smoke\.agent\resource-quality-report.md" `
    -TargetRelativePath "release-artifacts\evidence\resource-quality\resource-quality-report.md" `
    -Label "Resource quality report"
$evidence += Copy-EvidenceFile `
    -SourceRelativePath "workspace\v80-resource-smoke\.agent\texture-atlas.png" `
    -TargetRelativePath "release-artifacts\evidence\resource-quality\texture-atlas.png" `
    -Label "Texture atlas preview"
$evidence += Copy-EvidenceFile `
    -SourceRelativePath "workspace\v80-resource-smoke\.agent\previews\ruby_gallery.png" `
    -TargetRelativePath "release-artifacts\evidence\resource-quality\previews\ruby_gallery.png" `
    -Label "Structure preview PNG"
$evidence += Copy-EvidenceFile `
    -SourceRelativePath "workspace\failure-lab-runs\v80-portfolio-showcase-failure-lab\.agent\failure-lab-report.md" `
    -TargetRelativePath "release-artifacts\evidence\failure-repair\failure-lab-report.md" `
    -Label "Failure injection report"
$evidence += Copy-EvidenceFile `
    -SourceRelativePath "workspace\repair-eval-runs\v80-portfolio-showcase-repair-eval\.agent\repair-eval-report.md" `
    -TargetRelativePath "release-artifacts\evidence\failure-repair\repair-eval-report.md" `
    -Label "Repair eval report"

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
