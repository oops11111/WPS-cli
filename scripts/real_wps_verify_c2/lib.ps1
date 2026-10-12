# lib.ps1 - shared helpers for the B/C/D/E real-WPS checks. Dot-source it: . .\lib.ps1
# Safe by design: reads COM properties and process lists only. Nothing here kills, quits or closes a
# process or document that it did not create itself.
$ErrorActionPreference = 'Stop'

$script:Root    = if ($env:WPS_VERIFY_DIR) { $env:WPS_VERIFY_DIR } else { Join-Path $env:TEMP 'wps-bcde-verify' }
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
    # The exact PowerShell the CLI embeds in every COM script (Get-RunningWpsApp, Test-WpsPathOpen,
    # Open-WpsDocument, Assert-WpsSingleInstance ...), so the probes below use the shipped code.
    & $script:Python -c "import sys; from wps_ai_agent_cli.wps_script_snippets import PRE_OPEN_GUARD as g; open(sys.argv[1], 'w', encoding='utf-8-sig').write(g)" $script:GuardPs1
    if ($LASTEXITCODE -ne 0) { throw 'could not export PRE_OPEN_GUARD (is PYTHONPATH/python right?)' }
}

function Invoke-WpsCli {
    # Runs the real CLI from the work dir (its .wps-agent state lives there). Returns exit code, parsed JSON, raw text.
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
        [pscustomobject]@{ exit_code = $code; json = $json; stdout = $text; stderr = (Get-Content $errFile -Raw) }
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
    # WPS often exclusive-locks an open workbook; hash via a shared-read stream when FileHash fails.
    try { return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash } catch { }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $fs = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
        try {
            $hash = $sha.ComputeHash($fs)
            return ([System.BitConverter]::ToString($hash) -replace '-', '')
        } finally { $fs.Dispose() }
    } finally { $sha.Dispose() }
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
    # Read-only: path / Saved / ReadOnly of everything open in one COM application object.
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

function Get-AttachProbe {
    # What the CLI would attach to right now (GetActiveObject semantics), plus its open documents.
    # Needs: . $script:GuardPs1 has been dot-sourced by the caller (it defines Get-RunningWpsApp).
    param([Parameter(Mandatory)][string]$Component)
    try { $app = Get-RunningWpsApp $script:ProgIds[$Component] } catch { return [pscustomobject]@{ attached = $false; documents = @(); error = $_.Exception.Message } }
    if ($null -eq $app) { return [pscustomobject]@{ attached = $false; documents = @() } }
    [pscustomobject]@{ attached = $true; documents = (Get-DocStates $app $Component) }
}

function Save-Artifact {
    param([Parameter(Mandatory)][string]$Name, [Parameter(Mandatory)]$Object)
    $path = Join-Path $script:ArtDir ("{0}_{1}.json" -f $Name, $script:Stamp)
    $Object | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $path
    Write-Host "artifact: $path"
    return $path
}

function Show-Check {
    param([string]$Name, [bool]$Pass, [string]$Detail = '')
    $mark = if ($Pass) { 'PASS' } else { 'FAIL' }
    Write-Host ("[{0}] {1} {2}" -f $mark, $Name, $Detail)
    [pscustomobject]@{ check = $Name; pass = $Pass; detail = $Detail }
}

function Get-FirstProgId {
    # First registered ProgID of a component (read-only registry lookup via the same call the CLI uses).
    param([Parameter(Mandatory)][string]$Component)
    foreach ($id in $script:ProgIds[$Component]) {
        if ($null -ne (Get-ItemProperty "Registry::HKEY_CLASSES_ROOT\$id" -ErrorAction SilentlyContinue)) { return $id }
    }
    return $null
}
