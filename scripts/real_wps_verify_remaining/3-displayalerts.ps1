# 3-displayalerts.ps1
# Verify Set-WpsAppQuiet / Restore-WpsAppSettings: DisplayAlerts (and inspect's AskToUpdateLinks /
# EnableEvents) are restored on the *attached* instance after a real CLI command.
#
# Also records whether a brief CLI Open on a closed scratch flips Visible (it must not on attached).
#
# Cases:
#   A0 snapshot baseline DisplayAlerts / AskToUpdateLinks / EnableEvents on attached ET
#   A1 spreadsheet-write on a *closed* scratch (CLI opens then closes its own workbook)
#      -> after return, DisplayAlerts equals baseline
#   A2 spreadsheet-inspect on another closed scratch
#      -> DisplayAlerts / AskToUpdateLinks / EnableEvents restored
#   A3 (optional evidence) force Open() on an already-open dirty scratch with alerts off
#      via inject + -RawOpenEvidence: documents silent reload; DESTRUCTIVE to that scratch's edit only
#
# Safety: only scratch files; never Quit/Kill ET; restores DisplayAlerts in finally even if CLI fails.
# usage: pwsh -File .\3-displayalerts.ps1 -RepoRoot C:\path\to\WPS-cli [-RawOpenEvidence]
# exit: 0 pass, 1 fail, 3 precondition
param([Parameter(Mandatory)][string]$RepoRoot, [string]$Python = 'python', [switch]$RawOpenEvidence)
if (-not $env:WPS_VERIFY_DIR) {
    $env:WPS_VERIFY_DIR = Join-Path (Join-Path $env:TEMP 'wps-remaining-verify') ((Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ'))
}
. (Join-Path $PSScriptRoot 'lib.ps1')
Initialize-Verify -RepoRoot $RepoRoot -Python $Python
Copy-Item (Join-Path $PSScriptRoot 'inject_driver.py') $script:Work -Force
& $script:Python (Join-Path $PSScriptRoot 'make_fixtures.py') $script:Work
if ($LASTEXITCODE -ne 0) { throw 'make_fixtures.py failed' }

$pathWrite = Join-Path $script:Work 'r3_alerts.xlsx'
# second copy for inspect so write's save does not affect inspect target
$pathInspect = Join-Path $script:Work 'r1_inspect_free.xlsx'
$idWrite = Register-VerifyDoc -Path $pathWrite -Component 'spreadsheets'
$idInspect = Register-VerifyDoc -Path $pathInspect -Component 'spreadsheets'
$driver = Join-Path $script:Work 'inject_driver.py'

$app = Get-RunningWpsAppSafe 'spreadsheets'
if ($null -eq $app) { Write-Host 'No attachable ET.'; exit 3 }
$et = Get-ProcSnap 'et'
if ($et.windowed -gt 1) { Write-Host "More than one windowed et."; exit 3 }

function Read-AppSettings($app) {
    [pscustomobject]@{
        DisplayAlerts = $(try { $app.DisplayAlerts } catch { $null })
        AskToUpdateLinks = $(try { $app.AskToUpdateLinks } catch { $null })
        EnableEvents = $(try { $app.EnableEvents } catch { $null })
        Visible = $(try { $app.Visible } catch { $null })
    }
}

$checks = @()
$opened = @()
$report = [ordered]@{ commit = (git -C $script:RepoRoot rev-parse HEAD); et = $et; work_dir = $script:Work }
$exitCode = 0
$baseline = $null
$forcedBaseline = $false
try {
    # Ensure baseline DisplayAlerts is true so restore is observable (many installs default true).
    $prev = Read-AppSettings $app
    if ($prev.DisplayAlerts -eq $false) {
        try { $app.DisplayAlerts = $true; $forcedBaseline = $true } catch { }
    }
    $baseline = Read-AppSettings $app
    $report.baseline = $baseline
    $report.forced_displayalerts_true = $forcedBaseline
    $checks += Show-Check 'A0 baseline DisplayAlerts readable' ($null -ne $baseline.DisplayAlerts) ('DisplayAlerts=' + $baseline.DisplayAlerts)

    $docs0 = Get-DocStates $app 'spreadsheets'
    $a1 = Invoke-WpsCli -CliArgs @('spreadsheet-write', '--document-id', $idWrite, '--range', 'A1:A1', '--values-json', '[[77]]')
    $afterWrite = Read-AppSettings $app
    $docs1 = Get-DocStates $app 'spreadsheets'
    $leftWrite = @($docs1 | Where-Object { $_.full_name -like '*r3_alerts.xlsx' })
    $checks += Show-Check 'A1 write ok' ([bool]$a1.json.ok) ('ok=' + $a1.json.ok)
    $checks += Show-Check 'A1 DisplayAlerts restored after write' ($afterWrite.DisplayAlerts -eq $baseline.DisplayAlerts) ('before=' + $baseline.DisplayAlerts + ' after=' + $afterWrite.DisplayAlerts)
    $checks += Show-Check 'A1 Visible unchanged' ($afterWrite.Visible -eq $baseline.Visible) ('visible=' + $afterWrite.Visible)
    $checks += Show-Check 'A1 scratch not left open' ($leftWrite.Count -eq 0) ('left=' + $leftWrite.Count)

    $a2 = Invoke-WpsCli -CliArgs @('spreadsheet-inspect', '--document-id', $idInspect, '--range', 'A1:B1')
    $afterInspect = Read-AppSettings $app
    $checks += Show-Check 'A2 inspect ok' ([bool]$a2.json.ok) ('ok=' + $a2.json.ok)
    $checks += Show-Check 'A2 DisplayAlerts restored after inspect' ($afterInspect.DisplayAlerts -eq $baseline.DisplayAlerts) ('after=' + $afterInspect.DisplayAlerts)
    if ($null -ne $baseline.AskToUpdateLinks) {
        $checks += Show-Check 'A2 AskToUpdateLinks restored' ($afterInspect.AskToUpdateLinks -eq $baseline.AskToUpdateLinks) ('after=' + $afterInspect.AskToUpdateLinks)
    }
    if ($null -ne $baseline.EnableEvents) {
        $checks += Show-Check 'A2 EnableEvents restored' ($afterInspect.EnableEvents -eq $baseline.EnableEvents) ('after=' + $afterInspect.EnableEvents)
    }

    $report.after_write = $afterWrite
    $report.after_inspect = $afterInspect
    $report.cli = [ordered]@{ write = $a1.json; inspect = $a2.json }
    $report.docs_before = $docs0; $report.docs_after_write = $docs1

    if ($RawOpenEvidence) {
        # Destructive only to this scratch's in-memory edit: proves alerts-off Open reloads.
        $dirty = Join-Path $script:Work 'r1_inspect_wps.xlsx'
        $idDirty = Register-VerifyDoc -Path $dirty -Component 'spreadsheets'
        $wb = $app.Workbooks.Open($dirty); $opened += $wb
        $wb.Worksheets.Item(1).Range('B2').Value2 = 'alerts-evidence-edit'
        $evidence = [ordered]@{
            saved_before = [bool]$wb.Saved
            b2_before = [string]$wb.Worksheets.Item(1).Range('B2').Value2
            displayalerts_during = $app.DisplayAlerts
        }
        $trace = Join-Path $script:Work 'trace_a3.jsonl'
        if (Test-Path $trace) { Remove-Item $trace -Force }
        # Keep alerts off to match CLI path, then inject so Open is attempted.
        try { $app.DisplayAlerts = $false } catch { }
        $a3 = Invoke-WpsCli -Script $driver -Env @{ C2_TRACE_FILE = $trace } -CliArgs @('spreadsheet-write', '--document-id', $idDirty, '--range', 'A1:A1', '--values-json', '[[88]]')
        $evidence.cli = $a3.json
        $evidence.trace = @(if (Test-Path $trace) { Get-Content $trace })
        $evidence.b2_after_held = $(try { [string]$wb.Worksheets.Item(1).Range('B2').Value2 } catch { $null })
        $evidence.saved_after_held = $(try { [bool]$wb.Saved } catch { $null })
        $report.raw_open_evidence = $evidence
        Write-Host '[INFO] RawOpenEvidence recorded (edits on scratch may be lost if Open ran). Not an enforced pass/fail.'
        try { $app.DisplayAlerts = $baseline.DisplayAlerts } catch { }
    }

    $report.checks = $checks
    $report.overall_pass = (@($checks | Where-Object { -not $_.pass }).Count -eq 0)
    if (-not $report.overall_pass) { $exitCode = 1 }
} finally {
    foreach ($b in $opened) { try { $b.Close($false) } catch { } }
    try {
        if ($null -ne $baseline) {
            if ($null -ne $baseline.DisplayAlerts) { $app.DisplayAlerts = $baseline.DisplayAlerts }
        } elseif ($forcedBaseline) { $app.DisplayAlerts = $true }
    } catch { }
    Save-Artifact '3_displayalerts' $report | Out-Null
}
exit $exitCode
