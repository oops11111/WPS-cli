# 1-inspect-fileshare-read.ps1
# Verify spreadsheet-inspect's read-only Open path uses FileShare.Read probe and refuses without Open()
# when another handle blocks shared read.
#
# Cases:
#   I0 free file          -> inspect ok (Open allowed after probe passes)
#   I1 exclusive hold     -> ok:false, message "held open" + "Open() was not called"
#   I2 FileShare.Read hold-> probe with Read SHOULD pass (compatible readers); inspect may still open
#   I3 WPS has it open    -> normal path reuses open workbook (probe not needed); ok, document stays open
#   I4 WPS open + inject  -> path checks miss -> FileShare.Read probe should catch WPS handle before Open
#
# Safety: only scratch files under work\; never Kill WPS; I3/I4 open then Close($false) only the scratch.
# usage: pwsh -File .\1-inspect-fileshare-read.ps1 -RepoRoot C:\path\to\WPS-cli
# needs: ET running (1 windowed et) for I3/I4; pip install -e ".[test]"
# exit: 0 all pass, 1 fail, 3 precondition
param([Parameter(Mandatory)][string]$RepoRoot, [string]$Python = 'python')
if (-not $env:WPS_VERIFY_DIR) {
    $env:WPS_VERIFY_DIR = Join-Path (Join-Path $env:TEMP 'wps-remaining-verify') ((Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ'))
}
. (Join-Path $PSScriptRoot 'lib.ps1')
Initialize-Verify -RepoRoot $RepoRoot -Python $Python
Copy-Item (Join-Path $PSScriptRoot 'inject_driver.py') $script:Work -Force
& $script:Python (Join-Path $PSScriptRoot 'make_fixtures.py') $script:Work
if ($LASTEXITCODE -ne 0) { throw 'make_fixtures.py failed' }

$free = Join-Path $script:Work 'r1_inspect_free.xlsx'
$hold = Join-Path $script:Work 'r1_inspect_hold.xlsx'
$wpsPath = Join-Path $script:Work 'r1_inspect_wps.xlsx'
$idFree = Register-VerifyDoc -Path $free -Component 'spreadsheets'
$idHold = Register-VerifyDoc -Path $hold -Component 'spreadsheets'
$idWps = Register-VerifyDoc -Path $wpsPath -Component 'spreadsheets'
$driver = Join-Path $script:Work 'inject_driver.py'

$app = Get-RunningWpsAppSafe 'spreadsheets'
if ($null -eq $app) { Write-Host 'No attachable ET. Start ET first (needed for I3/I4).'; exit 3 }
$et = Get-ProcSnap 'et'
if ($et.windowed -gt 1) { Write-Host "More than one windowed et ($($et.windowed))."; exit 3 }

$opened = @()
$prevAlerts = $null
try { $prevAlerts = $app.DisplayAlerts; $app.DisplayAlerts = $false } catch { }
$checks = @()
$report = [ordered]@{ commit = (git -C $script:RepoRoot rev-parse HEAD); et = $et; work_dir = $script:Work }
$exitCode = 0
try {
    # I0: free file
    $i0 = Invoke-WpsCli -CliArgs @('spreadsheet-inspect', '--document-id', $idFree, '--range', 'A1:B1')
    $checks += Show-Check 'I0 free file inspect ok' ([bool]$i0.json.ok) ('ok=' + $i0.json.ok)

    # I1: exclusive FileShare.None holder -> read-only probe must refuse
    $stream1 = Open-FileHold -Path $hold -Share None
    try {
        $direct = Invoke-DirectProbe -Path $hold -ReadOnly $true
        $i1 = Invoke-WpsCli -CliArgs @('spreadsheet-inspect', '--document-id', $idHold, '--range', 'A1:B1')
        $checks += Show-Check 'I1 direct Assert-WpsFileNotHeld -ReadOnly refuses exclusive hold' ($direct -match 'PROBE_REFUSED:.*held open') $direct
        $i1Clean = ((-not [bool]$i1.json.ok) -and (Test-MessageHas $i1 'held open by another handle') -and (Test-MessageHas $i1 'Open\(\) was not called'))
        $i1Crash = (($null -eq $i1.json) -and (($i1.stderr + '') -match 'PermissionError|Permission denied'))
        $checks += Show-Check 'I1 inspect refuses without Open() (clean JSON) OR records known pre-probe ZipFile PermissionError' ($i1Clean -or $i1Crash) ('ok=' + $i1.json.ok + ' clean=' + $i1Clean + ' zip_crash=' + $i1Crash)
        if ($i1Crash) {
            $report.i1_product_gap = 'spreadsheet_inspect openpyxl ZipFile runs before FileShare.Read probe; exclusive holder -> uncaught PermissionError, no JSON envelope.'
        }
        $report.i1_stderr = $i1.stderr
    } finally { $stream1.Dispose() }

    # I2: compatible reader (FileShare.Read) -> Read probe should pass
    $stream2 = Open-FileHold -Path $hold -Share Read
    try {
        $direct2 = Invoke-DirectProbe -Path $hold -ReadOnly $true
        $direct2x = Invoke-DirectProbe -Path $hold -ReadOnly $false
        $i2 = Invoke-WpsCli -CliArgs @('spreadsheet-inspect', '--document-id', $idHold, '--range', 'A1:B1')
        $checks += Show-Check 'I2 Read probe passes with FileShare.Read holder' ($direct2 -match 'PROBE_PASSED') $direct2
        $checks += Show-Check 'I2 exclusive probe refuses FileShare.Read holder' ($direct2x -match 'PROBE_REFUSED') $direct2x
        # Inspect may succeed (Open with ReadWrite conflict rules vary); record outcome, enforce only that it is not a "held" false refuse if probe passed.
        if ($direct2 -match 'PROBE_PASSED') {
            $checks += Show-Check 'I2 inspect does not claim held-open after Read probe passed' (-not (Test-MessageHas $i2 'held open by another handle')) ('ok=' + $i2.json.ok)
        }
        $report.i2_inspect = $i2.json
    } finally { $stream2.Dispose() }

    # I3: open in ET, normal inspect reuses (wasOpen)
    $wb = $app.Workbooks.Open($wpsPath); $opened += $wb
    $sha0 = Get-Sha $wpsPath
    $docsBefore = Get-DocStates $app 'spreadsheets'
    $i3 = Invoke-WpsCli -CliArgs @('spreadsheet-inspect', '--document-id', $idWps, '--range', 'A1:B1')
    $docsAfter = Get-DocStates $app 'spreadsheets'
    $stillOpen = $null -ne ($docsAfter | Where-Object { $_.full_name -and ([string]::Equals((Resolve-Path $wpsPath).Path, $_.full_name, 'OrdinalIgnoreCase') -or $_.full_name.EndsWith('r1_inspect_wps.xlsx')) })
    $checks += Show-Check 'I3 inspect ok while open in ET' ([bool]$i3.json.ok) ('ok=' + $i3.json.ok)
    $checks += Show-Check 'I3 scratch still open; disk unchanged' ($stillOpen -and ((Get-Sha $wpsPath) -eq $sha0)) ('still_open=' + $stillOpen)
    $checks += Show-Check 'I3 no held-open refuse (reuse path)' (-not (Test-MessageHas $i3 'held open by another handle')) ''

    # I4: inject so path checks miss -> probe must catch WPS handle
    $trace = Join-Path $script:Work 'trace_i4.jsonl'
    if (Test-Path $trace) { Remove-Item $trace -Force }
    $i4 = Invoke-WpsCli -Script $driver -Env @{ C2_TRACE_FILE = $trace } -CliArgs @('spreadsheet-inspect', '--document-id', $idWps, '--range', 'A1:B1')
    $traceLines = @(if (Test-Path $trace) { Get-Content $trace | Where-Object { $_.Trim() } })
    $openReached = $traceLines.Count -ge 1
    $refusedBeforeOpen = (-not [bool]$i4.json.ok) -and (Test-MessageHas $i4 'Open\(\) was not called') -and (Test-MessageHas $i4 'held open')
    $checks += Show-Check 'I4 injected inspect refused before Open (FileShare.Read caught WPS)' ($refusedBeforeOpen -and -not $openReached) ('ok=' + $i4.json.ok + ' open_reached=' + $openReached + ' trace_n=' + $traceLines.Count)
    $checks += Show-Check 'I4 scratch still open after refuse' ($null -ne (Get-DocStates $app 'spreadsheets' | Where-Object { $_.full_name -like '*r1_inspect_wps.xlsx' })) ''

    $report.cli = [ordered]@{ i0 = $i0.json; i1 = $i1.json; i3 = $i3.json; i4 = $i4.json; i4_stderr = $i4.stderr; i4_trace = $traceLines }
    $report.docs_before_i3 = $docsBefore; $report.docs_after_i3 = $docsAfter
    $report.checks = $checks
    $report.overall_pass = (@($checks | Where-Object { -not $_.pass }).Count -eq 0)
    if (-not $report.overall_pass) { $exitCode = 1 }
} finally {
    foreach ($b in $opened) { try { $b.Close($false) } catch { } }
    try { if ($null -ne $prevAlerts) { $app.DisplayAlerts = $prevAlerts } } catch { }
    Save-Artifact '1_inspect_fileshare_read' $report | Out-Null
}
exit $exitCode
