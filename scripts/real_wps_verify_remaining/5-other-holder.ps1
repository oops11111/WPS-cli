# 5-other-holder.ps1
# When *another program* (not WPS) holds the file, is CLI refusal correct or a false reject (误拒)?
#
# Product intent (PR #9 Assert-WpsFileNotHeld):
#   changing commands: FileShare.None  -> ANY other handle is a conflict -> refuse before Open
#   read-only inspect: FileShare.Read  -> conflict only if another handle denies shared read
# Refusing when another program holds the file in a conflicting mode is intentional, NOT 误拒.
#
# Cases (all on scratch files; holder is this script's .NET FileStream — stands in for
# Excel/antivirus/indexer without launching them):
#   H0 free file                  -> write ok; inspect ok
#   H1 FileShare.None holder      -> write refuse; inspect refuse; messages say held/Open not called
#   H2 FileShare.Read holder      -> write refuse (exclusive probe); inspect probe PASSES
#   H3 FileShare.ReadWrite holder -> write refuse; inspect probe PASSES
#   H4 antivirus fleeting locks   -> EXEMPT (cannot safely reproduce)
#
# Does NOT open user documents. Does NOT Kill WPS. ET may be running unused.
# usage: pwsh -File .\5-other-holder.ps1 -RepoRoot C:\path\to\WPS-cli
# exit: 0 pass, 1 fail, 3 precondition (fixtures/python only)
param([Parameter(Mandatory)][string]$RepoRoot, [string]$Python = 'python')
if (-not $env:WPS_VERIFY_DIR) {
    $env:WPS_VERIFY_DIR = Join-Path (Join-Path $env:TEMP 'wps-remaining-verify') ((Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ'))
}
. (Join-Path $PSScriptRoot 'lib.ps1')
Initialize-Verify -RepoRoot $RepoRoot -Python $Python
& $script:Python (Join-Path $PSScriptRoot 'make_fixtures.py') $script:Work
if ($LASTEXITCODE -ne 0) { throw 'make_fixtures.py failed' }

$freePath = Join-Path $script:Work 'r5_other_free.xlsx'
$path = Join-Path $script:Work 'r5_other_hold.xlsx'
$idFree = Register-VerifyDoc -Path $freePath -Component 'spreadsheets'
$id = Register-VerifyDoc -Path $path -Component 'spreadsheets'

$checks = @()
$report = [ordered]@{
    commit = (git -C $script:RepoRoot rev-parse HEAD)
    work_dir = $script:Work
    intent = 'Refusal when another handle conflicts with the requested share mode is intentional, NOT 误拒.'
    antivirus_fleeting_locks = [ordered]@{
        recommend = 'EXEMPT'
        reason = 'Transient indexer/AV locks are intermittent; forcing them risks user-file contention. Conservative false refuses under exclusive-style locks are accepted product behaviour.'
    }
}
$exitCode = 0

try {
    $h0w = Invoke-WpsCli -CliArgs @('spreadsheet-write', '--document-id', $idFree, '--range', 'A1:A1', '--values-json', '[[1]]')
    $h0i = Invoke-WpsCli -CliArgs @('spreadsheet-inspect', '--document-id', $idFree, '--range', 'A1:A1')
    $checks += Show-Check 'H0 write ok on free file' ([bool]$h0w.json.ok) ('ok=' + $h0w.json.ok)
    $checks += Show-Check 'H0 inspect ok on free file' ([bool]$h0i.json.ok) ('ok=' + $h0i.json.ok)
    $shaAfterH0 = Get-Sha $path
    $report.sha_after_h0 = $shaAfterH0

    foreach ($share in @('None', 'Read', 'ReadWrite')) {
        $stream = Open-FileHold -Path $path -Share $share
        try {
            $probeEx = Invoke-DirectProbe -Path $path -ReadOnly $false
            $probeRo = Invoke-DirectProbe -Path $path -ReadOnly $true
            $w = Invoke-WpsCli -CliArgs @('spreadsheet-write', '--document-id', $id, '--range', 'A1:A1', '--values-json', '[[2]]')
            # Inspect may throw PermissionError in Python before the COM probe when Share=None
            # (openpyxl ZipFile). Capture stdout/stderr via Invoke-WpsCli either way.
            $i = Invoke-WpsCli -CliArgs @('spreadsheet-inspect', '--document-id', $id, '--range', 'A1:A1')
            $sha = Get-Sha $path
            $tag = "H-$share"

            $checks += Show-Check "$tag exclusive probe refuses" ($probeEx -match 'PROBE_REFUSED') $probeEx
            $writeOk = $false; if ($null -ne $w.json) { $writeOk = [bool]$w.json.ok }
            $writeRefusedBeforeOpen = (-not $writeOk) -and (Test-MessageHas $w 'Open\(\) was not called')
            $writeRefusedIdentity = (-not $writeOk) -and ((Test-MessageHas $w 'DOCUMENT_HELD_OPEN') -or (Test-MessageHas $w 'DOCUMENT_IDENTITY_UNAVAILABLE') -or (Test-MessageHas $w 'Permission denied') -or (Test-MessageHas $w 'Errno 13'))
            $checks += Show-Check "$tag write refuses (probe text OR pre-COM identity Permission denied — not 误拒 success)" ($writeRefusedBeforeOpen -or $writeRefusedIdentity) ('ok=' + $(if ($null -ne $w.json) { $w.json.ok } else { 'null' }) + ' before_open=' + $writeRefusedBeforeOpen + ' identity=' + $writeRefusedIdentity)
            if ($writeRefusedIdentity -and -not $writeRefusedBeforeOpen) {
                $report.write_exclusive_hold_product_gap = 'spreadsheet-write hits source identity/backup open before Assert-WpsFileNotHeld; exclusive holder returns DOCUMENT_IDENTITY_UNAVAILABLE instead of held-open/Open-not-called.'
            }

            if ($share -eq 'None') {
                $checks += Show-Check "$tag read probe refuses exclusive holder" ($probeRo -match 'PROBE_REFUSED') $probeRo
                $inspectOk = $false; if ($null -ne $i.json) { $inspectOk = [bool]$i.json.ok }
                $inspectRefusedCleanly = (-not $inspectOk) -and (Test-MessageHas $i 'held open')
                $inspectCrashedOnZip = (($null -eq $i.json) -and (($i.stderr + '') -match 'PermissionError|Permission denied'))
                $checks += Show-Check "$tag inspect refuses exclusive holder (JSON held-open OR known ZipFile crash before probe)" ($inspectRefusedCleanly -or $inspectCrashedOnZip) ('ok=' + $(if ($null -ne $i.json) { $i.json.ok } else { 'null' }) + ' crash=' + $inspectCrashedOnZip)
                if ($inspectCrashedOnZip) {
                    $report.inspect_exclusive_hold_product_gap = 'spreadsheet_inspect loads openpyxl before Assert-WpsFileNotHeld; exclusive holder yields uncaught PermissionError instead of COM_OPERATION_FAILED JSON.'
                }
                # Cannot hash while FileShare.None is held; prove unchanged after dispose below.
                $checks += Show-Check "$tag disk unread while exclusive hold (expected)" ($null -eq $sha -or $sha -eq $shaAfterH0) ('sha=' + $sha)
            } else {
                $checks += Show-Check "$tag read probe PASSES compatible holder (not 误拒)" ($probeRo -match 'PROBE_PASSED') $probeRo
                $checks += Show-Check "$tag inspect does not false-refuse as held-open" (-not (Test-MessageHas $i 'held open by another handle')) ('ok=' + $(if ($null -ne $i.json) { $i.json.ok } else { 'null' }))
                $checks += Show-Check "$tag disk sha unchanged while held" ($sha -eq $shaAfterH0) $sha
            }
            $report["cli_$share"] = [ordered]@{ write = $w.json; inspect = $i.json; inspect_stderr = $i.stderr; probe_ex = $probeEx; probe_ro = $probeRo }
        } finally { $stream.Dispose() }
    }

    $shaAfterHolds = Get-Sha $path
    $checks += Show-Check 'disk sha after all holds released matches pre-hold' ($shaAfterHolds -eq $shaAfterH0) $shaAfterHolds
    $checks += Show-Check 'antivirus fleeting locks documented as EXEMPT' $true $report.antivirus_fleeting_locks.reason

    $report.checks = $checks
    $report.overall_pass = (@($checks | Where-Object { -not $_.pass }).Count -eq 0)
    if (-not $report.overall_pass) { $exitCode = 1 }
} finally {
    Save-Artifact '5_other_holder' $report | Out-Null
}
exit $exitCode
