param(
    [string]$RunName = "v80-failure-repair-demo",
    [ValidateSet("delete_model", "delete_texture", "delete_worldgen_json", "delete_behavior_java", "break_recipe_reference")]
    [string]$Case = "delete_model",
    [switch]$Build
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot
$env:PYTHONPATH = (Resolve-Path ".\src")

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

function Join-Values {
    param($Values)
    if ($null -eq $Values) {
        return ""
    }
    $items = @($Values | Where-Object { $_ })
    if ($items.Count -eq 0) {
        return ""
    }
    return ($items -join ", ")
}

Write-Host "== Failure -> Audit -> Repair -> Pass Demo =="
Write-Host "Project root: $ProjectRoot"
Write-Host "Run name: $RunName"
Write-Host "Case: $Case"
Write-Host "Build: $($Build.IsPresent)"

$FailureArgs = @(
    "failure-lab",
    "--run-name", $RunName,
    "--case", $Case,
    "--json"
)

if ($Build) {
    $FailureArgs += "--build"
}

Invoke-AgentCli -Arguments $FailureArgs

$FailureReportJson = Join-Path $ProjectRoot "workspace\failure-lab-runs\$RunName\.agent\failure-lab-report.json"
if (-not (Test-Path $FailureReportJson)) {
    throw "Expected failure lab report was not written: $FailureReportJson"
}

$FailureReport = Get-Content $FailureReportJson -Encoding utf8 | ConvertFrom-Json
$CaseResult = @($FailureReport.cases)[0]
if ($null -eq $CaseResult) {
    throw "Failure lab report does not contain a case result: $FailureReportJson"
}

$RepairLoopJson = $CaseResult.repair_loop_report_json_path
$RepairLoop = $null
$InitialAttempt = $null
$FinalAttempt = $null
if ($RepairLoopJson -and (Test-Path $RepairLoopJson)) {
    $RepairLoop = Get-Content $RepairLoopJson -Encoding utf8 | ConvertFrom-Json
    $Attempts = @($RepairLoop.attempts)
    if ($Attempts.Count -gt 0) {
        $InitialAttempt = $Attempts[0]
        $FinalAttempt = $Attempts[$Attempts.Count - 1]
    }
}

$DemoDir = Join-Path $ProjectRoot "workspace\failure-repair-demos\$RunName\.agent"
New-Item -ItemType Directory -Force -Path $DemoDir | Out-Null
$DemoReportMd = Join-Path $DemoDir "failure-repair-demo-report.md"
$DemoReportJson = Join-Path $DemoDir "failure-repair-demo-report.json"

$InjectedPaths = @($CaseResult.injected_paths)
$DetectedIssues = @($CaseResult.detected_issue_ids)
$RepairCapabilities = @($CaseResult.repair_rag_capabilities)
$GeneratedFiles = @()
if ($FinalAttempt -and $FinalAttempt.generated_files) {
    $GeneratedFiles = @($FinalAttempt.generated_files)
}

$DemoPayload = [ordered]@{
    success = [bool]$CaseResult.success
    run_id = $RunName
    case_id = $CaseResult.id
    case_title = $CaseResult.title
    workspace = $CaseResult.workspace
    fault = $CaseResult.fault
    injected_paths = $InjectedPaths
    initial_audit_success = $CaseResult.initial_audit_success
    initial_audit_errors_count = $CaseResult.initial_audit_errors_count
    detected_expected_failure = $CaseResult.detected_expected_failure
    detected_issue_ids = $DetectedIssues
    repair_rag_hits_count = $CaseResult.repair_rag_hits_count
    repair_rag_relevant = $CaseResult.repair_rag_relevant
    repair_rag_capabilities = $RepairCapabilities
    repair_success = $CaseResult.repair_success
    repair_attempts_count = $CaseResult.repair_attempts_count
    final_audit_success = $CaseResult.final_audit_success
    repaired_generated_files_count = $GeneratedFiles.Count
    artifacts = [ordered]@{
        demo_report_md = $DemoReportMd
        demo_report_json = $DemoReportJson
        failure_lab_report_json = $FailureReportJson
        failure_lab_report_md = $FailureReport.failure_lab_report_md_path
        initial_audit_report = $CaseResult.initial_audit_report_path
        repair_rag_report = $CaseResult.repair_rag_report_md_path
        repair_loop_report = $CaseResult.repair_loop_report_md_path
        repair_loop_report_json = $CaseResult.repair_loop_report_json_path
    }
}

$DemoPayload | ConvertTo-Json -Depth 12 | Set-Content -Path $DemoReportJson -Encoding utf8

$IssueLines = @()
if ($DetectedIssues.Count -gt 0) {
    $IssueLines = $DetectedIssues | ForEach-Object { '- `' + $_ + '`' }
} else {
    $IssueLines = @('- none')
}

$GeneratedFileLines = @()
if ($GeneratedFiles.Count -gt 0) {
    $GeneratedFileLines = $GeneratedFiles | Select-Object -First 12 | ForEach-Object { '- `' + $_ + '`' }
    if ($GeneratedFiles.Count -gt 12) {
        $GeneratedFileLines += '- ... ' + ($GeneratedFiles.Count - 12) + ' more'
    }
} else {
    $GeneratedFileLines = @('- none')
}

$Markdown = @(
    "# Failure -> Audit -> Repair -> Pass Demo",
    "",
    "Success: ``$([string]$CaseResult.success)``",
    "Run ID: ``$RunName``",
    "Case: ``$($CaseResult.id)``",
    "Workspace: ``$($CaseResult.workspace)``",
    "",
    "## Story",
    "",
    "This demo intentionally breaks one generated artifact, verifies that ``audit`` detects the broken reference, asks repair RAG for relevant evidence, then runs ``repair-loop`` to regenerate managed files from ``.agent/modspec.json``. The final audit must pass.",
    "",
    "## Stage Checklist",
    "",
    "| Stage | Evidence | Result |",
    "| --- | --- | --- |",
    "| 1. Generate clean workspace | ``$($CaseResult.workspace)`` | generation success: ``$([string]$CaseResult.generation_success)`` |",
    "| 2. Inject failure | ``$(Join-Values $InjectedPaths)`` | injected: ``$([string]$CaseResult.fault_injected)`` |",
    "| 3. Audit detects failure | ``$($CaseResult.initial_audit_report_path)`` | initial audit success: ``$($CaseResult.initial_audit_success)``, errors: ``$($CaseResult.initial_audit_errors_count)`` |",
    "| 4. Repair RAG explains context | ``$($CaseResult.repair_rag_report_md_path)`` | hits: ``$($CaseResult.repair_rag_hits_count)``, relevant: ``$([string]$CaseResult.repair_rag_relevant)`` |",
    "| 5. Repair loop regenerates files | ``$($CaseResult.repair_loop_report_md_path)`` | repair success: ``$($CaseResult.repair_success)`` |",
    "| 6. Final audit passes | ``$($CaseResult.repair_loop_report_json_path)`` | final audit success: ``$($CaseResult.final_audit_success)`` |",
    "",
    "## Injected Fault",
    "",
    '```text',
    "$($CaseResult.fault)",
    '```',
    "",
    "Injected path(s):",
    ""
) + ($InjectedPaths | ForEach-Object { '- `' + $_ + '`' }) + @(
    "",
    "## Detected Audit Issues",
    ""
) + $IssueLines + @(
    "",
    "## Repair RAG",
    "",
    "- hits: ``$($CaseResult.repair_rag_hits_count)``",
    "- relevant: ``$([string]$CaseResult.repair_rag_relevant)``",
    "- capabilities: ``$(Join-Values $RepairCapabilities)``",
    "",
    "## Regenerated Files",
    "",
    "Repair loop regenerated ``$($GeneratedFiles.Count)`` managed file entries. First entries:",
    ""
) + $GeneratedFileLines + @(
    "",
    "## Artifacts",
    "",
    "- failure lab report: ``$($FailureReport.failure_lab_report_md_path)``",
    "- initial audit report: ``$($CaseResult.initial_audit_report_path)``",
    "- repair RAG report: ``$($CaseResult.repair_rag_report_md_path)``",
    "- repair loop report: ``$($CaseResult.repair_loop_report_md_path)``",
    "- compact demo JSON: ``$DemoReportJson``",
    ""
)

$Markdown | Set-Content -Path $DemoReportMd -Encoding utf8

Write-Host ""
Write-Host "== Demo artifacts =="
Write-Host "Compact report:     $DemoReportMd"
Write-Host "Compact JSON:       $DemoReportJson"
Write-Host "Failure lab report: $($FailureReport.failure_lab_report_md_path)"
Write-Host "Initial audit:      $($CaseResult.initial_audit_report_path)"
Write-Host "Repair RAG:         $($CaseResult.repair_rag_report_md_path)"
Write-Host "Repair loop:        $($CaseResult.repair_loop_report_md_path)"
Write-Host ""
Write-Host "Suggested walkthrough: compact report -> initial audit -> repair RAG -> repair loop."
