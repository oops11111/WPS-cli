# c2-post-open.ps1 - real-WPS check of the branch "Open() was called but the workbook Count did not grow".
#
# Merged behaviour under test: when Open() returns without growing the collection (someone else opened the document
# between the last check and Open()), every non read-only command is refused, whatever Saved of any object says.
#
# The old c-toctou injection only made Test-WpsPathOpen lie, so the recheck right before Open() (Find-WpsOpenDocument)
# caught the document and Open() was never called. c2_post_open_driver.py also blinds that recheck, so the CLI really
# calls Workbooks.Open() on a workbook that is already open in ET. Test-only: the CLI's PowerShell text is patched in
# memory, no production hook exists, nothing in the repo changes.
#
#   P0 control      : normal CLI write on the open, clean scratch workbook (no injection)       -> ok, stays open
#   P1 post-Open    : scratch workbook with unsaved edits, check + recheck blinded              -> ok:false, refused
#   P2 post-Open    : clean scratch workbook, same injection                                    -> ok:false, refused
#   P3 raw probe    : plain Open() on the dirty workbook from this script (evidence only, last)
#
# Recorded for P1 after the CLI call, via the reference held from before: Saved, A1, B2 of the ORIGINAL object, the
# workbook count, the disk sha256; and from the CLI's trace: count before/after Open() and the returned object's
# Saved/B2. Fresh scratch files and a fresh state dir are created on every run (never reuses an earlier fixture).
#
# Opens two scratch workbooks in your attached ET (two tabs/windows appear) and closes exactly those two at the end,
# WITHOUT saving. Needs a running ET with a single windowed et process. Never quits ET. Touches no user document.
#
# usage:  pwsh -File .\scripts\real_wps_verify_c2\c2-post-open.ps1 -RepoRoot C:\path\to\WPS-cli [-Python python]
# needs:  python with the repo's test extra (openpyxl):  pip install -e ".[test]"
# exit:   0 all checks pass, 1 a check failed, 2 scenario not reproduced (Open() grew the count), 3 precondition missing
param([Parameter(Mandatory)][string]$RepoRoot, [string]$Python = 'python')
if (-not $env:WPS_VERIFY_DIR) {
    $env:WPS_VERIFY_DIR = Join-Path (Join-Path $env:TEMP 'wps-c2-verify') ((Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ'))
}
. (Join-Path $PSScriptRoot 'lib.ps1')
Initialize-Verify -RepoRoot $RepoRoot -Python $Python
. $script:GuardPs1

& $script:Python (Join-Path $PSScriptRoot 'make_c2_fixtures.py') $script:Work
if ($LASTEXITCODE -ne 0) { throw 'make_c2_fixtures.py failed (pip install -e ".[test]" in the repo?)' }
Copy-Item (Join-Path $PSScriptRoot 'c2_post_open_driver.py') $script:Work -Force
$driver = Join-Path $script:Work 'c2_post_open_driver.py'
$clean = Join-Path $script:Work 'c2_clean.xlsx'
$dirty = Join-Path $script:Work 'c2_dirty.xlsx'
$idClean = Register-VerifyDoc -Path $clean -Component 'spreadsheets'
$idDirty = Register-VerifyDoc -Path $dirty -Component 'spreadsheets'
$userEdit = 'user typed this, not saved'

$app = Get-RunningWpsApp $script:ProgIds['spreadsheets']
if ($null -eq $app) { Write-Host 'No attachable ET. Start ET first.'; exit 3 }
$et = Get-ProcSnap 'et'
if ($et.windowed -gt 1) { Write-Host "More than one windowed et process ($($et.windowed)); close the extra ET windows first."; exit 3 }

function Find-Book($app, $path) {
    for ($i = 1; $i -le [int]$app.Workbooks.Count; $i++) {
        $b = $app.Workbooks.Item($i)
        if ([string]::Equals((ConvertTo-WpsComparablePath ([string]$b.FullName)), (ConvertTo-WpsComparablePath $path), 'OrdinalIgnoreCase')) { return $b }
    }
    return $null
}
function Read-Book($b) {
    if ($null -eq $b) { return $null }
    [pscustomobject]@{
        saved = $(try { [bool]$b.Saved } catch { $null })
        a1 = $(try { [string]$b.Worksheets.Item(1).Range('A1').Value2 } catch { $null })
        b2 = $(try { [string]$b.Worksheets.Item(1).Range('B2').Value2 } catch { $null })
    }
}
function Snapshot($app, $held, [string]$path) {
    $found = Find-Book $app $path
    [pscustomobject]@{
        workbook_count = [int]$app.Workbooks.Count
        open = [bool]$found
        found_by_path = Read-Book $found
        held_reference = $(try { Read-Book $held } catch { [pscustomobject]@{ error = $_.Exception.Message } })
        disk_sha = Get-Sha $path
    }
}
function Read-Trace([string]$file) {
    if (-not (Test-Path -LiteralPath $file)) { return @() }
    @(Get-Content -LiteralPath $file | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json })
}
function Invoke-Injected([string]$docId, [string]$traceFile, [int]$value) {
    if (Test-Path -LiteralPath $traceFile) { Remove-Item -LiteralPath $traceFile -Force }
    Invoke-WpsCli -Script $driver -Env @{ C2_TRACE_FILE = $traceFile } -CliArgs @('spreadsheet-write', '--document-id', $docId, '--range', 'A1:A1', '--values-json', "[[$value]]")
}
$refusal = 'between the check and the open call'

$opened = @()
$prevAlerts = $null
try { $prevAlerts = $app.DisplayAlerts; $app.DisplayAlerts = $false } catch { }
$report = [ordered]@{ et = $et; work_dir = $script:Work; commit = (git -C $script:RepoRoot rev-parse HEAD) }
$exitCode = 0
try {
    $wbClean = $app.Workbooks.Open($clean); $opened += $wbClean
    $wbDirty = $app.Workbooks.Open($dirty); $opened += $wbDirty
    $wbDirty.Worksheets.Item(1).Range('B2').Value2 = $userEdit
    $report.dirty_precondition_saved_flag = [bool]$wbDirty.Saved
    if ([bool]$wbDirty.Saved) { Write-Host 'Precondition failed: the dirty scratch workbook reports Saved=true after an edit.'; exit 3 }

    $s0 = Snapshot $app $wbClean $clean
    $p0 = Invoke-WpsCli -CliArgs @('spreadsheet-write', '--document-id', $idClean, '--range', 'A1:A1', '--values-json', '[[4]]')
    $s0b = Snapshot $app $wbClean $clean

    $sd0 = Snapshot $app $wbDirty $dirty
    $trace1 = Join-Path $script:Work 'trace_p1.jsonl'
    $p1 = Invoke-Injected $idDirty $trace1 6
    $sd1 = Snapshot $app $wbDirty $dirty
    $t1 = Read-Trace $trace1

    $sc0 = Snapshot $app $wbClean $clean
    $trace2 = Join-Path $script:Work 'trace_p2.jsonl'
    $p2 = Invoke-Injected $idClean $trace2 7
    $sc1 = Snapshot $app $wbClean $clean
    $t2 = Read-Trace $trace2

    $reproduced = (@($t1).Count -ge 1) -and (@($t2).Count -ge 1) -and (@($t1 + $t2 | Where-Object { [int]$_.count_after -gt [int]$_.count_before }).Count -eq 0)
    $held1 = $sd1.held_reference
    $checks = @()
    $checks += Show-Check 'P0 control ok, workbook stays open, count unchanged' ([bool]$p0.json.ok -and $s0b.open -and $s0b.workbook_count -eq $s0.workbook_count) ('ok=' + $p0.json.ok)
    $checks += Show-Check 'scenario reproduced: CLI called Open() and Count did not grow (P1 and P2)' $reproduced ('P1 trace=' + (($t1 | ConvertTo-Json -Compress -Depth 4)) + ' P2 trace=' + (($t2 | ConvertTo-Json -Compress -Depth 4)))
    $checks += Show-Check 'P1 dirty workbook refused (ok:false)' (($p1.json.ok -eq $false) -and ($p1.stdout -match $refusal)) ('ok=' + $p1.json.ok)
    $checks += Show-Check 'P1 original object still dirty with the user edit (held reference)' (($held1.saved -eq $false) -and ($held1.b2 -eq $userEdit)) ('saved=' + $held1.saved + ' b2=' + $held1.b2)
    $checks += Show-Check 'P1 original object unchanged A1 (the write was not applied)' ($held1.a1 -eq $sd0.held_reference.a1) ('a1=' + $held1.a1)
    $checks += Show-Check 'P1 still open, same workbook count' ($sd1.open -and $sd1.workbook_count -eq $sd0.workbook_count) ('count=' + $sd1.workbook_count)
    $checks += Show-Check 'P1 disk sha256 unchanged' ($sd1.disk_sha -eq $sd0.disk_sha) $sd1.disk_sha
    $checks += Show-Check 'P2 clean workbook also refused (ok:false)' (($p2.json.ok -eq $false) -and ($p2.stdout -match $refusal)) ('ok=' + $p2.json.ok)
    $checks += Show-Check 'P2 still open, count and disk sha256 unchanged' ($sc1.open -and $sc1.workbook_count -eq $sc0.workbook_count -and $sc1.disk_sha -eq $sc0.disk_sha) ('count=' + $sc1.workbook_count)

    $probe = [ordered]@{}
    $orig = Find-Book $app $dirty
    $probe.count_before = [int]$app.Workbooks.Count
    $probe.orig_before_open = Read-Book $orig
    $o = $app.Workbooks.Open($dirty)
    $probe.count_after = [int]$app.Workbooks.Count
    $probe.same_object = [object]::ReferenceEquals($o, $orig)
    $probe.returned = Read-Book $o
    $probe.orig_after_open_via_held_ref = $(try { Read-Book $orig } catch { [pscustomobject]@{ error = $_.Exception.Message } })
    $probe.orig_after_open_via_find = Read-Book (Find-Book $app $dirty)
    if ($probe.count_after -gt $probe.count_before -and -not $probe.same_object) { try { $o.Close($false) } catch { } }

    $report.snapshots = [ordered]@{ clean_before_control = $s0; clean_after_control = $s0b; dirty_before = $sd0; dirty_after_injected = $sd1; clean_before_injected = $sc0; clean_after_injected = $sc1 }
    $report.cli = [ordered]@{ control = $p0.json; injected_dirty = $p1.json; injected_dirty_stderr = $p1.stderr; injected_clean = $p2.json }
    $report.open_trace = [ordered]@{ dirty = $t1; clean = $t2 }
    $report.raw_open_probe_on_dirty_workbook = $probe
    $report.checks = $checks
    $report.overall_pass = (@($checks | Where-Object { -not $_.pass }).Count -eq 0)
    if (-not $reproduced) { $exitCode = 2; Write-Host 'The scenario was not reproduced (Open() was not reached or Count grew): the refusal checks are not conclusive. Send the artifact.' }
    elseif (-not $report.overall_pass) { $exitCode = 1; Write-Host 'A check failed: send the artifact (raw_open_probe_on_dirty_workbook and open_trace explain what Open() returned).' }
} finally {
    foreach ($b in $opened) { try { $b.Close($false) } catch { } }
    try { if ($null -ne $prevAlerts) { $app.DisplayAlerts = $prevAlerts } } catch { }
    Save-Artifact 'c2_post_open' $report | Out-Null
}
exit $exitCode
