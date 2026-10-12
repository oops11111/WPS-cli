# 4-concurrency-window.ps1
# The probe→Open micro-race: another party opens the file after Assert-WpsFileNotHeld
# succeeds and before collection.Open(). Hitting this reliably on real WPS is unsafe
# (if the race is lost, Open() can silently reload and discard unsaved edits).
#
# Default (-Mode document): print exemption + point at offline/inject coverage. Recommended.
# Optional (-Mode stress): N rapid injected CLI writes against a scratch that is already
# open+dirty in ET. This does NOT truly race the probe window (inject already skips path
# checks); it only reconfirms that when checks miss, PR #9 probe refuses before Open.
# True cross-process race remains EXEMPT.
#
# usage:
#   pwsh -File .\4-concurrency-window.ps1 -RepoRoot C:\path\to\WPS-cli
#   pwsh -File .\4-concurrency-window.ps1 -RepoRoot C:\path\to\WPS-cli -Mode stress -Iterations 10
# exit: 0 exempt/ok, 1 stress failed enforced check, 3 precondition
param(
    [Parameter(Mandatory)][string]$RepoRoot,
    [ValidateSet('document', 'stress')][string]$Mode = 'document',
    [int]$Iterations = 10,
    [string]$Python = 'python'
)
if (-not $env:WPS_VERIFY_DIR) {
    $env:WPS_VERIFY_DIR = Join-Path (Join-Path $env:TEMP 'wps-remaining-verify') ((Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ'))
}
. (Join-Path $PSScriptRoot 'lib.ps1')
Initialize-Verify -RepoRoot $RepoRoot -Python $Python

$report = [ordered]@{
    mode = $Mode
    commit = (git -C $script:RepoRoot rev-parse HEAD)
    exemption = [ordered]@{
        item = 'probe-to-Open real concurrency window'
        recommend = 'EXEMPT'
        reason = @(
            'The window is sub-second; manual timing cannot hit it stably.',
            'Losing the race calls Open() on a file WPS may already hold; with DisplayAlerts off this can reload and discard unsaved edits (proven on ET in PR #8).',
            'Injected miss of Test-WpsPathOpen/Find-WpsOpenDocument (C2 kit + inject_driver.py) already exercises the post-miss path without requiring a true race.',
            'File-lock probe (PR #9) shrinks but does not eliminate the window between successful probe and Open().'
        ) -join ' '
        offline_coverage = @(
            'tests/test_wps_instance_attach.py::FileLockProbeTests',
            'scripts/real_wps_verify_c2/c2-post-open.ps1',
            'docs/wps-real-verify-remaining/1-inspect-fileshare-read.ps1 I4',
            'docs/wps-real-verify-remaining/2-writer-wpp-lock.ps1 inject cases'
        )
    }
}

if ($Mode -eq 'document') {
    Write-Host '=== Item 4: true concurrency window — recommended EXEMPT ==='
    Write-Host $report.exemption.reason
    Write-Host 'Offline / inject substitutes:'
    $report.exemption.offline_coverage | ForEach-Object { Write-Host "  - $_" }
    $report.overall_pass = $true
    $report.checks = @(Show-Check 'documented exemption (no real race attempted)' $true 'Mode=document')
    Save-Artifact '4_concurrency_window' $report | Out-Null
    exit 0
}

# --- stress mode: reconfirm probe-before-Open under inject (NOT a true race) ---
Copy-Item (Join-Path $PSScriptRoot 'inject_driver.py') $script:Work -Force
& $script:Python (Join-Path $PSScriptRoot 'make_fixtures.py') $script:Work
if ($LASTEXITCODE -ne 0) { throw 'make_fixtures.py failed' }
$path = Join-Path $script:Work 'r4_race.xlsx'
$id = Register-VerifyDoc -Path $path -Component 'spreadsheets'
$driver = Join-Path $script:Work 'inject_driver.py'

$app = Get-RunningWpsAppSafe 'spreadsheets'
if ($null -eq $app) { Write-Host 'No attachable ET.'; exit 3 }
$et = Get-ProcSnap 'et'
if ($et.windowed -gt 1) { Write-Host 'More than one windowed et.'; exit 3 }

$prevAlerts = $null
try { $prevAlerts = $app.DisplayAlerts; $app.DisplayAlerts = $false } catch { }
$exitCode = 0
$checks = @()
$opened = @()
try {
    Write-Host "Stress (inject proxy, not true race): $Iterations iterations on scratch only."
    $wb = $app.Workbooks.Open($path); $opened += $wb
    $userEdit = 'race-scratch-edit'
    $wb.Worksheets.Item(1).Range('B2').Value2 = $userEdit
    if ([bool]$wb.Saved) { Write-Host 'Precondition: Saved stayed true after edit.'; exit 3 }
    $rows = @()
    $allRefusedBeforeOpen = $true
    for ($i = 1; $i -le $Iterations; $i++) {
        $trace = Join-Path $script:Work ("trace_race_{0}.jsonl" -f $i)
        if (Test-Path $trace) { Remove-Item $trace -Force }
        $r = Invoke-WpsCli -Script $driver -Env @{ C2_TRACE_FILE = $trace } -CliArgs @(
            'spreadsheet-write', '--document-id', $id, '--range', 'A1:A1', '--values-json', "[[$i]]"
        )
        $openReached = (Test-Path $trace) -and (@(Get-Content $trace | Where-Object { $_.Trim() }).Count -ge 1)
        $b2 = $(try { [string]$wb.Worksheets.Item(1).Range('B2').Value2 } catch { $null })
        $refusedBefore = (-not [bool]$r.json.ok) -and (Test-MessageHas $r 'Open\(\) was not called') -and -not $openReached
        if (-not $refusedBefore) { $allRefusedBeforeOpen = $false }
        $rows += [pscustomobject]@{
            i = $i; ok = $r.json.ok; open_reached = $openReached; b2 = $b2
            edit_intact = ($b2 -eq $userEdit); refused_before_open = $refusedBefore
        }
    }
    $report.stress_rows = $rows
    $checks += Show-Check 'stress: every inject refuse before Open (PR #9 probe)' $allRefusedBeforeOpen ''
    $checks += Show-Check 'stress: unsaved scratch edit intact after all iterations' (
        ([string]$wb.Worksheets.Item(1).Range('B2').Value2) -eq $userEdit -and -not [bool]$wb.Saved
    ) ''
    $checks += Show-Check 'true cross-process race still EXEMPT' $true $report.exemption.reason
    $report.checks = $checks
    $report.overall_pass = (@($checks | Where-Object { -not $_.pass }).Count -eq 0)
    if (-not $report.overall_pass) { $exitCode = 1 }
} finally {
    foreach ($b in $opened) { try { $b.Close($false) } catch { } }
    try { if ($null -ne $prevAlerts) { $app.DisplayAlerts = $prevAlerts } } catch { }
    Save-Artifact '4_concurrency_window' $report | Out-Null
}
exit $exitCode
