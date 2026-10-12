# lib.ps1 - shared helpers for remaining real-WPS checks (PR #8/#9 follow-up).
# Safe by design: reads COM properties and process lists only. Closes/Quits only
# documents or instances this script created. Never Kill user WPS.
$ErrorActionPreference = 'Stop'

$script:Root    = if ($env:WPS_VERIFY_DIR) { $env:WPS_VERIFY_DIR } else { Join-Path $env:TEMP 'wps-remaining-verify' }
$script:Work    = Join-Path $script:Root 'work'
$script:ArtDir  = Join-Path $script:Root 'artifacts'
$script:Stamp   = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffffffZ')
$script:GuardPs1 = Join-Path $script:Work 'guard.ps1'
$script:ProgIds = @{
    spreadsheets = @('ket.Application', 'et.Application', 'Kingsoft Spreadsheets.Application')
    presentation = @('kwpp.Application', 'wpp.Application', 'Kingsoft Presentation.Application')
    writer       = @('kwps.Application', 'wps.Application', 'Kingsoft Writer.Application')
}
$script:ProcName = @{ spreadsheets = 'et'; presentation = 'wpp'; writer = 'wps' }
$script:Collection = @{ spreadsheets = 'Workbooks'; presentation = 'Presentations'; writer = 'Documents' }

function Initialize-Verify {
    param([Parameter(Mandatory)][string]$RepoRoot, [string]$Python = 'python')
    $script:RepoRoot = (Resolve-Path $RepoRoot).Path
    $script:Python = $Python
    New-Item -ItemType Directory -Force $script:Work, $script:ArtDir | Out-Null
    $env:PYTHONPATH = Join-Path $script:RepoRoot 'src'
    & $script:Python -c "import sys; from wps_ai_agent_cli.wps_script_snippets import PRE_OPEN_GUARD as g; open(sys.argv[1], 'w', encoding='utf-8-sig').write(g)" $script:GuardPs1
    if ($LASTEXITCODE -ne 0) { throw 'could not export PRE_OPEN_GUARD (is PYTHONPATH/python right?)' }
}

function Invoke-WpsCli {
    param([Parameter(Mandatory)][string[]]$CliArgs, [hashtable]$Env = @{}, [string]$Script = '')
    $saved = @{}
    foreach ($k in $Env.Keys) { $saved[$k] = [Environment]::GetEnvironmentVariable($k); [Environment]::SetEnvironmentVariable($k, $Env[$k]) }
    Push-Location $script:Work
    try {
        $argv = if ($Script) { @($Script) + $CliArgs } else { @('-m', 'wps_ai_agent_cli') + $CliArgs }
        $errFile = Join-Path $script:Work 'last_stderr.txt'
        $out = & $script:Python @argv 2> $errFile
        $code = $LASTEXITCODE
        $text = ($out -join "`n")
        $json = $null
        try { $json = $text | ConvertFrom-Json } catch { }
        [pscustomobject]@{ exit_code = $code; json = $json; stdout = $text; stderr = (Get-Content $errFile -Raw -ErrorAction SilentlyContinue) }
    } finally {
        Pop-Location
        foreach ($k in $saved.Keys) { [Environment]::SetEnvironmentVariable($k, $saved[$k]) }
    }
}

function Register-VerifyDoc {
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)][string]$Component)
    $r = Invoke-WpsCli -CliArgs @('register-document', '--component', $Component, '--path', $Path)
    if (-not $r.json -or -not $r.json.ok) { throw ('register-document failed: ' + $r.stdout) }
    return [string]$r.json.data.document.document_id
}

function Get-Sha([string]$Path) {
    # Prefer shared-read open: WPS/AV may briefly deny exclusive or default Get-FileHash opens.
    $deadline = [datetime]::UtcNow.AddSeconds(60)
    while ($true) {
        try { return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash } catch { }
        $sha = [System.Security.Cryptography.SHA256]::Create()
        try {
            try {
                $fs = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
                try {
                    $hash = $sha.ComputeHash($fs)
                    return ([System.BitConverter]::ToString($hash) -replace '-', '')
                } finally { $fs.Dispose() }
            } catch {
                if ([datetime]::UtcNow -ge $deadline) { return $null }
                Start-Sleep -Milliseconds 400
            }
        } finally { $sha.Dispose() }
    }
}

function Get-ProcSnap {
    param([Parameter(Mandatory)][string]$Name)
    $session = [System.Diagnostics.Process]::GetCurrentProcess().SessionId
    $all = @(Get-Process -Name $Name -ErrorAction SilentlyContinue)
    $rows = @($all | ForEach-Object {
        [pscustomobject]@{
            pid = $_.Id; session = $_.SessionId; main_window = ([int64]$_.MainWindowHandle -ne 0)
            title = [string]$_.MainWindowTitle; start = $(try { $_.StartTime.ToUniversalTime().ToString('o') } catch { $null })
            path = $(try { $_.Path } catch { $null })
        }
    })
    [pscustomobject]@{
        name = $Name; total = $rows.Count
        windowed = @($rows | Where-Object { $_.session -eq $session -and $_.main_window }).Count
        processes = $rows
    }
}

function Get-DocStates {
    param($App, [Parameter(Mandatory)][string]$Component)
    $coll = $App.($script:Collection[$Component])
    $rows = @()
    for ($i = 1; $i -le [int]$coll.Count; $i++) {
        $d = $coll.Item($i)
        $rows += [pscustomobject]@{
            index = $i
            full_name = $(try { [string]$d.FullName } catch { $null })
            saved = $(try { [bool]$d.Saved } catch { $null })
            read_only = $(try { [bool]$d.ReadOnly } catch { $null })
        }
    }
    return , $rows
}

function Get-RunningWpsAppSafe {
    param([Parameter(Mandatory)][string]$Component)
    if (-not (Test-Path -LiteralPath $script:GuardPs1)) { throw 'guard.ps1 missing; call Initialize-Verify first' }
    . $script:GuardPs1
    return (Get-RunningWpsApp $script:ProgIds[$Component])
}

function Save-Artifact {
    param([Parameter(Mandatory)][string]$Name, [Parameter(Mandatory)]$Object)
    $path = Join-Path $script:ArtDir ("{0}_{1}.json" -f $Name, $script:Stamp)
    $Object | ConvertTo-Json -Depth 14 | Set-Content -Encoding UTF8 $path
    Write-Host "artifact: $path"
    return $path
}

function Show-Check {
    param([string]$Name, [bool]$Pass, [string]$Detail = '')
    $mark = if ($Pass) { 'PASS' } else { 'FAIL' }
    Write-Host ("[{0}] {1} {2}" -f $mark, $Name, $Detail)
    [pscustomobject]@{ check = $Name; pass = $Pass; detail = $Detail }
}

function Test-MessageHas {
    param($Result, [string]$Pattern)
    $blob = (@($Result.stdout, $Result.stderr, ($(if ($Result.json) { $Result.json | ConvertTo-Json -Depth 8 -Compress } else { '' }))) -join "`n")
    return [bool]($blob -match $Pattern)
}

function Open-FileHold {
    # Hold a path with a chosen FileShare. Caller must Dispose the returned stream.
    # Retry briefly: WPS can keep a share lock for a short time after Close().
    param(
        [Parameter(Mandatory)][string]$Path,
        [ValidateSet('None', 'Read', 'ReadWrite', 'Write')]
        [string]$Share = 'None',
        [int]$TimeoutMs = 90000
    )
    $shareMode = [System.IO.FileShare]::$Share
    $deadline = [datetime]::UtcNow.AddMilliseconds($TimeoutMs)
    $last = $null
    $attempt = 0
    while ($true) {
        try {
            return [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, $shareMode)
        } catch {
            $last = $_
            $attempt++
            if ([datetime]::UtcNow -ge $deadline) { throw }
            if ($attempt -eq 1 -or ($attempt % 20) -eq 0) {
                Write-Host ("Open-FileHold waiting for share on {0} (attempt {1}): {2}" -f $Path, $attempt, $_.Exception.Message)
            }
            Start-Sleep -Milliseconds 500
        }
    }
    throw $last
}

function Invoke-DirectProbe {
    # Run Assert-WpsFileNotHeld from the shipped PRE_OPEN_GUARD (no CLI, no WPS Open).
    param([Parameter(Mandatory)][string]$Path, [bool]$ReadOnly = $false)
    . $script:GuardPs1
    try {
        Assert-WpsFileNotHeld $Path 'document' $ReadOnly
        return 'PROBE_PASSED'
    } catch {
        return ('PROBE_REFUSED: ' + $_.Exception.Message)
    }
}
