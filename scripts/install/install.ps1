<#
.SYNOPSIS
Installs wps-agent (WPS AI Agent CLI) for the current Windows user (P14-003).

.DESCRIPTION
One command sets up everything wps-agent needs on a Windows machine with WPS Office:

  1. finds Python 3.10 or later (the py launcher, python on PATH, or -Python);
  2. downloads the wheel of the chosen GitHub Release (or takes -WheelPath) and checks its SHA-256 against the
     Release when GitHub publishes one (and warns when it does not);
  3. creates a virtual environment in -InstallDir and installs the wheel with the [all] extra ([all,ocr] with -Ocr);
  4. installs Playwright (without its own browsers: Microsoft Edge is used) into -InstallDir\node when Node.js 18 or
     later is present, and puts its node_modules first in the current user's NODE_PATH, for the HTML conversions;
  5. puts a wps-agent.cmd shim in -InstallDir\bin and adds that folder to the user's PATH (not with -NoPath);
  6. runs "wps-agent inspect-env" and reports whether WPS's COM automation is registered;
  7. connects an MCP client: -McpClient claude-desktop adds the server to Claude Desktop's config (backing it up
     first), claude-code runs "claude mcp add" (replacing an earlier wps-agent entry); none only prints the entry
     to paste into any client. The server keeps its document registry, operation records and backups in -DataDir
     (WPS_AGENT_WORKSPACE), which -Uninstall leaves in place.

The user's PATH and NODE_PATH are edited in the registry entry by entry: other entries, and variables such as
%USERPROFILE% in them, are kept as they are.

-Uninstall removes what the installer put in -InstallDir (venv, bin, node, install.json, then the folder if it is
empty), its PATH entry and its NODE_PATH entry. The MCP client entry is left for you to remove. Nothing outside
-InstallDir, the user's PATH and NODE_PATH, and (when asked) the MCP client's config is changed. Run it again to
upgrade: the virtual environment is rebuilt. Quit Claude Desktop (or any MCP client using wps-agent) first.

Usage (PowerShell):
  irm https://github.com/oops11111/WPS-cli/releases/latest/download/install.ps1 -OutFile install.ps1
  powershell -ExecutionPolicy Bypass -File .\install.ps1 -McpClient claude-desktop

.EXAMPLE
  .\install.ps1 -Version 0.11.0 -McpClient claude-code -Ocr
.EXAMPLE
  .\install.ps1 -WheelPath .\wps_ai_agent_cli-0.11.0-py3-none-any.whl -SkipBrowser
.EXAMPLE
  .\install.ps1 -Uninstall
#>
[CmdletBinding()]
param(
    [string]$Version = 'latest',
    [string]$WheelPath,
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'wps-agent'),
    [string]$DataDir = (Join-Path $env:LOCALAPPDATA 'wps-agent-data'),
    [string]$Python,
    [switch]$Ocr,
    [switch]$SkipBrowser,
    [ValidateSet('none', 'claude-desktop', 'claude-code')]
    [string]$McpClient = 'none',
    [switch]$NoPath,
    [switch]$Uninstall,
    [string]$Repository = 'oops11111/WPS-cli'
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Write-Step([string]$Text) { Write-Host "==> $Text" -ForegroundColor Cyan }
function Write-Note([string]$Text) { Write-Host "    $Text" }
function Write-Warn([string]$Text) { Write-Host "    WARNING: $Text" -ForegroundColor Yellow }

function Resolve-FullPath([string]$Path) {
    # Relative to the PowerShell location (Set-Location), which .NET's own current directory does not follow.
    return $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
}

function Get-UserEnv([string]$Name) {
    # The registry value as stored: %VARIABLES% are not expanded, so writing it back keeps them.
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Environment')
    if (-not $key) { return $null }
    try {
        return $key.GetValue($Name, $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
    } finally { $key.Close() }
}

function Send-SettingChange {
    # Tell Explorer the environment changed, so new terminals see it (writing the registry alone does not).
    if (-not ('WpsAgentInstaller.Native' -as [type])) {
        Add-Type -Namespace WpsAgentInstaller -Name Native -MemberDefinition '[DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern IntPtr SendMessageTimeout(IntPtr hWnd, uint Msg, UIntPtr wParam, string lParam, uint fuFlags, uint uTimeout, out UIntPtr lpdwResult);'
    }
    $ignored = [UIntPtr]::Zero
    [void][WpsAgentInstaller.Native]::SendMessageTimeout([IntPtr]0xffff, 0x1A, [UIntPtr]::Zero, 'Environment', 2, 5000, [ref]$ignored)
}

function Set-UserEnv([string]$Name, [string]$Value, [Microsoft.Win32.RegistryValueKind]$NewKind) {
    # Keeps the value's registry type (PATH is usually REG_EXPAND_SZ); an empty value removes the variable.
    $key = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey('Environment')
    try {
        if ([string]::IsNullOrEmpty($Value)) {
            $key.DeleteValue($Name, $false)
        } else {
            $kind = if ($key.GetValueNames() -contains $Name) { $key.GetValueKind($Name) } else { $NewKind }
            $key.SetValue($Name, $Value, $kind)
        }
    } finally { $key.Close() }
    try { Send-SettingChange } catch { Write-Warn "Could not announce the environment change: $_" }
}

function Get-EnvEntries([string]$Name) {
    $value = Get-UserEnv $Name
    if (-not $value) { return @() }
    return @($value -split ';' | Where-Object { $_ })
}

function Test-SamePath([string]$A, [string]$B) {
    $left = [Environment]::ExpandEnvironmentVariables($A).TrimEnd('\')
    return ($left -ieq $B.TrimEnd('\'))
}

function Test-UnderPath([string]$Path, [string]$Root) {
    $full = [Environment]::ExpandEnvironmentVariables($Path).TrimEnd('\')
    $base = $Root.TrimEnd('\')
    return ($full -ieq $base) -or $full.StartsWith($base + '\', [StringComparison]::OrdinalIgnoreCase)
}

function Assert-NotRunning([string]$Directory) {
    # Files of a running server cannot be deleted: stop before anything is half removed.
    $running = @(Get-Process -ErrorAction SilentlyContinue | Where-Object {
            $path = $null
            try { $path = $_.Path } catch { }
            $path -and (Test-UnderPath $path $Directory)
        })
    if ($running.Count -gt 0) {
        $names = ($running | ForEach-Object { "$($_.ProcessName) (pid $($_.Id))" }) -join ', '
        throw "wps-agent is running from $Directory ($names). Quit Claude Desktop, or any other MCP client that uses wps-agent, and run this again."
    }
}

function Find-Python {
    # A real Python 3.10+ interpreter, not the Microsoft Store placeholder.
    $candidates = @()
    if ($Python) { $candidates += , @($Python) }
    if (Get-Command py -ErrorAction SilentlyContinue) { $candidates += , @('py', '-3') }
    if (Get-Command python -ErrorAction SilentlyContinue) { $candidates += , @('python') }
    foreach ($candidate in $candidates) {
        $exe = $candidate[0]
        $extra = @($candidate | Select-Object -Skip 1)
        try {
            $probe = & $exe @extra -c "import sys; print(sys.version_info >= (3, 10)); print(sys.executable)" 2>$null
        } catch { continue }
        if ($LASTEXITCODE -eq 0 -and $probe -and $probe[0] -eq 'True' -and (Test-Path -LiteralPath $probe[1])) {
            return $probe[1]
        }
    }
    throw 'Python 3.10 or later was not found. Install it from https://www.python.org/downloads/ (tick "Add python.exe to PATH") or pass -Python <path to python.exe>.'
}

function Get-ReleaseWheel([string]$Directory) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    $api = if ($Version -eq 'latest') {
        "https://api.github.com/repos/$Repository/releases/latest"
    } else {
        "https://api.github.com/repos/$Repository/releases/tags/v$($Version.TrimStart('v'))"
    }
    $release = Invoke-RestMethod -Uri $api -Headers @{ 'User-Agent' = 'wps-agent-installer' }
    $asset = @($release.assets | Where-Object { $_.name -like '*.whl' })[0]
    if (-not $asset) { throw "Release $($release.tag_name) has no wheel." }
    $target = Join-Path $Directory $asset.name
    Write-Note "Downloading $($asset.name) from $($release.tag_name)"
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $target -UseBasicParsing
    $digest = [string]$asset.digest
    if ($digest -like 'sha256:*') {
        $actual = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $digest.Substring(7).ToLowerInvariant()) {
            throw "The downloaded wheel's SHA-256 $actual does not match the Release ($digest)."
        }
        Write-Note 'SHA-256 matches the Release.'
    } else {
        Write-Warn "GitHub lists no SHA-256 for $($asset.name): the download was not checked."
    }
    return $target
}

function Find-Edge {
    $paths = @(
        $env:WPS_AGENT_EDGE,
        (Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'),
        (Join-Path $env:ProgramFiles 'Microsoft\Edge\Application\msedge.exe')
    )
    foreach ($path in $paths) { if ($path -and (Test-Path -LiteralPath $path)) { return $path } }
    return $null
}

function Install-Browser([string]$NodeDir) {
    # Playwright drives the installed Edge; its own browsers are not downloaded.
    $node = Get-Command node -ErrorAction SilentlyContinue
    if (-not $node) {
        Write-Warn 'Node.js was not found: HTML to PDF/PNG rendering and browser-measured HTML conversions are off. Install Node.js 18+ from https://nodejs.org and run this installer again.'
        return $null
    }
    $major = [int](((& node --version) -replace '^v', '') -split '\.')[0]
    if ($major -lt 18) {
        Write-Warn "Node.js $(& node --version) is older than 18: HTML rendering is off until it is upgraded."
        return $null
    }
    if (-not (Find-Edge)) {
        Write-Warn 'Microsoft Edge was not found: HTML rendering needs it (or set WPS_AGENT_EDGE to a Chromium executable).'
    }
    New-Item -ItemType Directory -Force -Path $NodeDir | Out-Null
    $env:PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD = '1'
    & npm install --prefix $NodeDir --no-audit --no-fund --loglevel=error 'playwright@1' | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'npm install playwright failed.' }
    $modules = Join-Path $NodeDir 'node_modules'
    # Ours first, the user's own entries after it, unchanged.
    $others = @(Get-EnvEntries 'NODE_PATH' | Where-Object { -not (Test-SamePath $_ $modules) })
    Set-UserEnv 'NODE_PATH' ((@($modules) + $others) -join ';') ([Microsoft.Win32.RegistryValueKind]::String)
    $env:NODE_PATH = (@($modules) + $others) -join ';'
    Write-Note "Playwright installed; NODE_PATH starts with $modules"
    return $modules
}

function Write-InstallRecord([System.Collections.IDictionary]$State) {
    $State | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $InstallDir 'install.json') -Encoding UTF8
}

function Read-InstallRecord {
    $record = Join-Path $InstallDir 'install.json'
    if (-not (Test-Path -LiteralPath $record)) { return $null }
    try { return Get-Content -LiteralPath $record -Raw | ConvertFrom-Json } catch { return $null }
}

function Invoke-Uninstall {
    Write-Step "Removing wps-agent from $InstallDir"
    $record = Join-Path $InstallDir 'install.json'
    $dataDir = $DataDir
    if (Test-Path -LiteralPath $record) {
        $state = Read-InstallRecord
        if ($state -and $state.data_dir) { $dataDir = [string]$state.data_dir }
        Assert-NotRunning $InstallDir
        # Only what the installer made; anything else in the folder (a data folder put there, say) stays.
        foreach ($part in 'venv', 'node', 'bin') {
            $path = Join-Path $InstallDir $part
            if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Recurse -Force }
        }
        Remove-Item -LiteralPath $record -Force
        if (@(Get-ChildItem -LiteralPath $InstallDir -Force).Count -eq 0) {
            Remove-Item -LiteralPath $InstallDir -Force
        } else {
            Write-Note "$InstallDir still holds files the installer did not create; they are kept."
        }
    } elseif (Test-Path -LiteralPath $InstallDir) {
        throw "$InstallDir has no install.json: not removing a folder this installer did not create."
    }
    $path = @(Get-EnvEntries 'Path')
    $keptPath = @($path | Where-Object { -not (Test-SamePath $_ $binDir) })
    if ($keptPath.Count -ne $path.Count) {
        Set-UserEnv 'Path' ($keptPath -join ';') ([Microsoft.Win32.RegistryValueKind]::ExpandString)
    }
    $nodePath = @(Get-EnvEntries 'NODE_PATH')
    $keptNode = @($nodePath | Where-Object { -not (Test-UnderPath $_ $InstallDir) })
    if ($keptNode.Count -ne $nodePath.Count) {
        Set-UserEnv 'NODE_PATH' ($keptNode -join ';') ([Microsoft.Win32.RegistryValueKind]::String)
    }
    Write-Note 'Done. Remove the "wps-agent" server from your MCP client yourself if you added it.'
    Write-Note "Backups and records in $dataDir are kept; delete that folder too if you do not need them."
}

function Invoke-Install {
    Write-Step 'Finding Python 3.10+'
    $pythonExe = Find-Python
    Write-Note $pythonExe

    $downloads = Join-Path ([IO.Path]::GetTempPath()) ("wps-agent-install-" + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force -Path $downloads | Out-Null
    try {
        Write-Step 'Getting the wheel'
        if ($WheelPath) {
            $wheel = (Resolve-Path -LiteralPath $WheelPath).Path
            Write-Note $wheel
        } else {
            $wheel = Get-ReleaseWheel $downloads
        }

        Write-Step "Creating the virtual environment in $venvDir"
        if (Test-Path -LiteralPath $venvDir) { Assert-NotRunning $venvDir }
        New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
        # Written before anything else goes in, so -Uninstall can clean up after a failed install too.
        $state = [ordered]@{ status = 'installing'; installed_at = (Get-Date).ToString('s'); data_dir = $DataDir }
        Write-InstallRecord $state
        if (Test-Path -LiteralPath $venvDir) { Remove-Item -LiteralPath $venvDir -Recurse -Force }
        & $pythonExe -m venv $venvDir
        if ($LASTEXITCODE -ne 0) { throw 'python -m venv failed.' }
        $venvPython = Join-Path $venvDir 'Scripts\python.exe'
        $wpsAgent = Join-Path $venvDir 'Scripts\wps-agent.exe'

        $extras = if ($Ocr) { 'all,ocr' } else { 'all' }
        Write-Step "Installing wps-agent with [$extras]"
        & $venvPython -m pip install --disable-pip-version-check --quiet --upgrade pip | Out-Host
        & $venvPython -m pip install --disable-pip-version-check --quiet "$($wheel)[$extras]" | Out-Host
        if ($LASTEXITCODE -ne 0) { throw 'pip install failed.' }
        $probe = & $venvPython -c "import wps_ai_agent_cli; print(wps_ai_agent_cli.__version__)"
        if ($LASTEXITCODE -ne 0 -or -not $probe) { throw 'wps-agent was installed but does not import; see the error above.' }
        $installedVersion = ([string]$probe).Trim()
        Write-Note "wps-agent $installedVersion"
    } finally {
        Remove-Item -LiteralPath $downloads -Recurse -Force -ErrorAction SilentlyContinue
    }

    $nodeModules = $null
    if ($SkipBrowser) {
        Write-Note 'Skipping Playwright (-SkipBrowser): HTML rendering stays off.'
    } else {
        Write-Step 'Setting up HTML rendering (Node.js, Playwright, Edge)'
        $nodeModules = Install-Browser $nodeDir
    }

    Write-Step "Adding $binDir to your PATH"
    New-Item -ItemType Directory -Force -Path $binDir | Out-Null
    # Relative to the shim itself: no path in the file, so a user name in any script works.
    $shim = "@echo off`r`n`"%~dp0..\venv\Scripts\wps-agent.exe`" %*`r`n"
    [IO.File]::WriteAllText((Join-Path $binDir 'wps-agent.cmd'), $shim, [Text.Encoding]::ASCII)
    if ($NoPath) {
        Write-Note "Not changing PATH (-NoPath); run $binDir\wps-agent.cmd"
    } elseif (-not (Get-EnvEntries 'Path' | Where-Object { Test-SamePath $_ $binDir })) {
        Set-UserEnv 'Path' ((@(Get-EnvEntries 'Path') + $binDir) -join ';') ([Microsoft.Win32.RegistryValueKind]::ExpandString)
        Write-Note 'Open a new terminal for the PATH change to take effect.'
    } else {
        Write-Note 'Already on PATH.'
    }
    $env:Path = "$binDir;$env:Path"

    $state = [ordered]@{
        status = 'installed'
        version = $installedVersion
        installed_at = (Get-Date).ToString('s')
        python = $pythonExe
        executable = $wpsAgent
        node_path = $nodeModules
        ocr = [bool]$Ocr
        data_dir = $DataDir
    }
    Write-InstallRecord $state

    Write-Step 'Checking the environment (wps-agent inspect-env)'
    $inspect = (& $wpsAgent inspect-env) | Out-String | ConvertFrom-Json
    if (-not $inspect.ok) { throw "inspect-env failed: $($inspect.errors | ConvertTo-Json -Compress)" }
    $registered = @(
        foreach ($component in 'writer', 'spreadsheets', 'presentation') {
            $found = $inspect.data.components.$component.selected_prog_id
            if ($found) { $found }
        }
    )
    if ($registered.Count -gt 0) {
        Write-Note "WPS COM automation is registered ($($registered -join ', '))."
    } else {
        Write-Warn 'No WPS COM ProgID is registered: reading documents works, editing and conversion through WPS do not. See docs/USER_GUIDE.md, "WPS is not found".'
    }

    Write-Step "Connecting the MCP client ($McpClient)"
    New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
    $configArgs = @('-m', 'wps_ai_agent_cli.client_config', '--command', $wpsAgent, '--env', "WPS_AGENT_WORKSPACE=$DataDir")
    if ($nodeModules) { $configArgs += @('--env', "NODE_PATH=$nodeModules") }
    switch ($McpClient) {
        'claude-desktop' {
            $result = (& $venvPython @configArgs --client claude-desktop --write) | Out-String | ConvertFrom-Json
            if ($result.error) { throw "Claude Desktop config: $($result.error)" }
            Write-Note "Added to $($result.config_path); restart Claude Desktop."
            if ($result.written.backup) { Write-Note "Previous config saved as $($result.written.backup)" }
        }
        'claude-code' {
            $result = (& $venvPython @configArgs --client claude-code) | Out-String | ConvertFrom-Json
            $command = @($result.command)
            if (Get-Command claude -ErrorAction SilentlyContinue) {
                # An entry from an earlier install would make "claude mcp add" refuse: replace it.
                $previous = $ErrorActionPreference
                $ErrorActionPreference = 'Continue'
                try { & claude mcp remove --scope user $result.name 2>&1 | Out-Null } finally { $ErrorActionPreference = $previous }
                & $command[0] @($command | Select-Object -Skip 1) | Out-Host
                if ($LASTEXITCODE -eq 0) {
                    Write-Note 'Registered with Claude Code (user scope).'
                } else {
                    Write-Warn ("claude mcp add failed (exit code $LASTEXITCODE); run it yourself: " + ($command -join ' '))
                }
            } else {
                Write-Warn ('Claude Code (claude) was not found; run this once it is installed: ' + ($command -join ' '))
            }
        }
        default {
            $result = (& $venvPython @configArgs --client json) | Out-String | ConvertFrom-Json
            Write-Note 'Add this to your MCP client config:'
            Write-Host ($result.entry | ConvertTo-Json -Depth 5)
        }
    }

    Write-Step "wps-agent $installedVersion is installed."
    Write-Note "Try: wps-agent inspect-env    (in a new terminal)"
}

$InstallDir = Resolve-FullPath $InstallDir
$DataDir = Resolve-FullPath $DataDir
$binDir = Join-Path $InstallDir 'bin'
$venvDir = Join-Path $InstallDir 'venv'
$nodeDir = Join-Path $InstallDir 'node'

# Python and the console speak UTF-8 while the installer runs, so JSON from wps-agent and client_config with
# non-ASCII paths (a Chinese user name, say) reads back intact. The session's settings are restored afterwards.
$savedEncoding = [Console]::OutputEncoding
$savedPythonUtf8 = $env:PYTHONUTF8
$savedPythonIo = $env:PYTHONIOENCODING
try {
    try { [Console]::OutputEncoding = New-Object Text.UTF8Encoding $false } catch { }
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    if ($Uninstall) { Invoke-Uninstall } else { Invoke-Install }
} finally {
    try { [Console]::OutputEncoding = $savedEncoding } catch { }
    $env:PYTHONUTF8 = $savedPythonUtf8
    $env:PYTHONIOENCODING = $savedPythonIo
}
