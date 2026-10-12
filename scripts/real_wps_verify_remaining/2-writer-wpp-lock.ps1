# 2-writer-wpp-lock.ps1
# Verify writer / presentation lock probe + Open behaviour on real WPS.
#
# Writer (component=writer, process=wps):
#   W0 control: closed scratch -> writer-replace ok
#   W1 exclusive .NET hold on closed file -> refuse, "Open() was not called"
#   W2 open in Writer (saved) -> normal CLI reuses / writes (ok); then
#   W3 open + inject (path checks miss) -> Assert-WpsFileNotHeld exclusive must refuse before Open
#
# Presentation (wpp): Presentations already refuse when open (Assert-WpsPresentationNotOpen).
#   P0 control: closed scratch -> presentation-replace ok
#   P1 exclusive hold -> refuse before Open
#   P2 open in WPP -> normal CLI refuses "already open" WITHOUT Open (Saved untrusted)
#   P3 open + inject -> exclusive probe should refuse before Open (or already-open path)
#
# Safety: only scratch docs; Close($false) only those; never Quit/Kill user Writer/WPP.
# usage:
#   pwsh -File .\2-writer-wpp-lock.ps1 -RepoRoot C:\path\to\WPS-cli -Component writer
#   pwsh -File .\2-writer-wpp-lock.ps1 -RepoRoot C:\path\to\WPS-cli -Component presentation
# exit: 0 pass, 1 fail, 3 precondition
param(
    [Parameter(Mandatory)][string]$RepoRoot,
    [ValidateSet('writer', 'presentation')][string]$Component = 'writer',
    [string]$Python = 'python'
)
if (-not $env:WPS_VERIFY_DIR) {
    $env:WPS_VERIFY_DIR = Join-Path (Join-Path $env:TEMP 'wps-remaining-verify') ((Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ'))
}
. (Join-Path $PSScriptRoot 'lib.ps1')
Initialize-Verify -RepoRoot $RepoRoot -Python $Python
Copy-Item (Join-Path $PSScriptRoot 'inject_driver.py') $script:Work -Force
& $script:Python (Join-Path $PSScriptRoot 'make_fixtures.py') $script:Work
if ($LASTEXITCODE -ne 0) { throw 'make_fixtures.py failed' }

$proc = $script:ProcName[$Component]
$collName = $script:Collection[$Component]
$driver = Join-Path $script:Work 'inject_driver.py'

if ($Component -eq 'writer') {
    $clean = Join-Path $script:Work 'r2_writer_clean.docx'
    $holdPath = Join-Path $script:Work 'r2_writer_hold.docx'
    $cliName = 'writer-replace'
} else {
    $clean = Join-Path $script:Work 'r2_wpp_clean.pptx'
    $holdPath = Join-Path $script:Work 'r2_wpp_hold.pptx'
    $cliName = 'presentation-replace'
}
$idClean = Register-VerifyDoc -Path $clean -Component $Component
$idHold = Register-VerifyDoc -Path $holdPath -Component $Component

$app = Get-RunningWpsAppSafe $Component
if ($null -eq $app) { Write-Host "No attachable $Component app. Start it first."; exit 3 }
$snap = Get-ProcSnap $proc
if ($snap.windowed -gt 1) { Write-Host "More than one windowed $proc ($($snap.windowed))."; exit 3 }

$opened = @()
$prevAlerts = $null
try { $prevAlerts = $app.DisplayAlerts; $app.DisplayAlerts = $false } catch { }
$checks = @()
$report = [ordered]@{ component = $Component; commit = (git -C $script:RepoRoot rev-parse HEAD); proc = $snap; work_dir = $script:Work }
$exitCode = 0

function Invoke-Replace([string]$DocId, [string]$Find, [string]$Replace, [string]$Script = '', [hashtable]$Env = @{}) {
    Invoke-WpsCli -Script $Script -Env $Env -CliArgs @($cliName, '--document-id', $DocId, '--find', $Find, '--replace', $Replace)
}

try {
    # Control on free file
    $sha0 = Get-Sha $clean
    $c0 = Invoke-Replace $idClean 'ALPHA' 'BETA'
    $checks += Show-Check 'control free file replace ok' ([bool]$c0.json.ok) ('ok=' + $c0.json.ok)
    # File was closed: CLI should have saved/closed its own open; do not leave it in the user's app.
    $left = @(Get-DocStates $app $Component | Where-Object { $_.full_name -and $_.full_name.EndsWith([IO.Path]::GetFileName($clean)) })
    $checks += Show-Check 'control did not leave scratch open in user app' ($left.Count -eq 0) ('left=' + $left.Count)

    # Exclusive hold (retry inside Open-FileHold: AV/WPS may briefly lock freshly written fixtures)
    Start-Sleep -Seconds 2
    $shaHoldBefore = Get-Sha $holdPath
    $stream = Open-FileHold -Path $holdPath -Share None
    try {
        $direct = Invoke-DirectProbe -Path $holdPath -ReadOnly $false
        $c1 = Invoke-Replace $idHold 'ALPHA' 'GAMMA'
        $shaHoldDuring = Get-Sha $holdPath
        $c1Ok = $false; if ($null -ne $c1.json) { $c1Ok = [bool]$c1.json.ok }
        $c1BeforeOpen = (-not $c1Ok) -and (Test-MessageHas $c1 'Open\(\) was not called') -and (Test-MessageHas $c1 'held open')
        $c1Identity = (-not $c1Ok) -and ((Test-MessageHas $c1 'DOCUMENT_IDENTITY_UNAVAILABLE') -or (Test-MessageHas $c1 'Permission denied') -or (($c1.stderr + '') -match 'PermissionError|Permission denied'))
        $checks += Show-Check 'exclusive hold: direct probe refuses' ($direct -match 'PROBE_REFUSED:.*held open') $direct
        $checks += Show-Check 'exclusive hold: CLI refuses (before-Open text OR pre-COM identity deny)' ($c1BeforeOpen -or $c1Identity) ('ok=' + $(if ($null -ne $c1.json) { $c1.json.ok } else { 'null' }) + ' before_open=' + $c1BeforeOpen + ' identity=' + $c1Identity)
        $checks += Show-Check 'exclusive hold: disk unread or unchanged while held' (($null -eq $shaHoldDuring) -or ($shaHoldDuring -eq $shaHoldBefore)) ('sha=' + $shaHoldDuring)
        $report.exclusive_cli = [ordered]@{ json = $c1.json; stderr = $c1.stderr; stdout = $c1.stdout }
    } finally {
        $stream.Dispose()
    }
    $shaHoldAfter = Get-Sha $holdPath
    $checks += Show-Check 'exclusive hold: disk sha unchanged after release' ($shaHoldAfter -eq $shaHoldBefore) $shaHoldAfter

    # Open in user app
    $coll = $app.$collName
    if ($Component -eq 'writer') {
        $doc = $coll.Open($holdPath); $opened += $doc
        # mark dirty-ish: append text then clear Saved if possible
        try { $doc.Content.InsertAfter(' USEREDIT') } catch { }
        $savedFlag = try { [bool]$doc.Saved } catch { $null }
        $report.open_saved_flag = $savedFlag

        $c2 = Invoke-Replace $idHold 'ALPHA' 'DELTA'
        $c2Ok = $false; if ($null -ne $c2.json) { $c2Ok = [bool]$c2.json.ok }
        # If unsaved, expect refuse with unsaved changes; if saved, may succeed on reuse path.
        if ($savedFlag -eq $false) {
            $checks += Show-Check 'open dirty writer: refused unsaved (no Open needed)' ((-not $c2Ok) -and (Test-MessageHas $c2 'unsaved')) ('ok=' + $c2Ok)
        } else {
            $checks += Show-Check 'open clean writer: reuse path ok or refuse without held-open false positive' (
                $c2Ok -or (-not (Test-MessageHas $c2 'held open by another handle'))
            ) ('ok=' + $c2Ok)
        }

        $trace = Join-Path $script:Work 'trace_w3.jsonl'
        if (Test-Path $trace) { Remove-Item $trace -Force }
        $c3 = Invoke-Replace $idHold 'ALPHA' 'EPS' -Script $driver -Env @{ C2_TRACE_FILE = $trace }
        $c3Ok = $false; if ($null -ne $c3.json) { $c3Ok = [bool]$c3.json.ok }
        $openReached = (Test-Path $trace) -and (@(Get-Content $trace | Where-Object { $_.Trim() }).Count -ge 1)
        $checks += Show-Check 'inject+open writer: refuse before Open (exclusive probe)' (
            (-not $c3Ok) -and (
                ((Test-MessageHas $c3 'Open\(\) was not called') -and (Test-MessageHas $c3 'held open')) -or
                (Test-MessageHas $c3 'unsaved')
            ) -and -not $openReached
        ) ('ok=' + $c3Ok + ' open_reached=' + $openReached)
        $report.writer_cli = [ordered]@{ control = $c0.json; held = $c1.json; open_normal = $c2.json; open_inject = $c3.json }
    } else {
        $doc = $coll.Open($holdPath); $opened += $doc
        $c2 = Invoke-Replace $idHold 'ALPHA' 'DELTA'
        $c2Ok = $false; if ($null -ne $c2.json) { $c2Ok = [bool]$c2.json.ok }
        $checks += Show-Check 'open presentation: refuses already-open without Open' (
            (-not $c2Ok) -and (Test-MessageHas $c2 'already open') -and (
                (Test-MessageHas $c2 'Open\(\) was not called') -or (Test-MessageHas $c2 'close it before')
            )
        ) ('ok=' + $c2Ok)

        $trace = Join-Path $script:Work 'trace_p3.jsonl'
        if (Test-Path $trace) { Remove-Item $trace -Force }
        $c3 = Invoke-Replace $idHold 'ALPHA' 'EPS' -Script $driver -Env @{ C2_TRACE_FILE = $trace }
        $c3Ok = $false; if ($null -ne $c3.json) { $c3Ok = [bool]$c3.json.ok }
        $openReached = (Test-Path $trace) -and (@(Get-Content $trace | Where-Object { $_.Trim() }).Count -ge 1)
        # Inject makes Test-WpsPathOpen false, so Assert-WpsPresentationNotOpen may not fire; then FileNotHeld should.
        $checks += Show-Check 'inject+open presentation: refuse before Open' (
            (-not $c3Ok) -and -not $openReached -and (
                (Test-MessageHas $c3 'held open') -or (Test-MessageHas $c3 'already open') -or (Test-MessageHas $c3 'Open\(\) was not called')
            )
        ) ('ok=' + $c3Ok + ' open_reached=' + $openReached)
        $report.wpp_cli = [ordered]@{ control = $c0.json; held = $c1.json; open_normal = $c2.json; open_inject = $c3.json }
    }

    $report.checks = $checks
    $report.overall_pass = (@($checks | Where-Object { -not $_.pass }).Count -eq 0)
    if (-not $report.overall_pass) { $exitCode = 1 }
} finally {
    foreach ($d in $opened) {
        try {
            if ($Component -eq 'writer') { $d.Close($false) }
            else { $d.Close() }
        } catch { }
    }
    try { if ($null -ne $prevAlerts) { $app.DisplayAlerts = $prevAlerts } } catch { }
    Save-Artifact ("2_{0}_lock" -f $Component) $report | Out-Null
}
exit $exitCode
