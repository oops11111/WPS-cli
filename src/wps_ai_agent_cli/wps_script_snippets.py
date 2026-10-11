from __future__ import annotations


# Closing WPS only when no other document is open protects a user's interactive
# session in case the COM server hands out its already-running instance.
QUIT_IF_IDLE = (
    "$wpsIdle = $true; "
    "foreach ($wpsCollection in 'Documents', 'Workbooks', 'Presentations') { "
    "try { $wpsItems = $app.$wpsCollection; "
    "if ($null -ne $wpsItems -and [int]$wpsItems.Count -gt 0) { $wpsIdle = $false } } catch { } }; "
    "if ($wpsIdle) { $app.Quit() }"
)


# Attaching uses GetActiveObject semantics: it never launches WPS and callers
# must never Quit() an instance obtained this way. Marshal.GetActiveObject is
# missing on PowerShell 7 (.NET 5+), so the OLE call is bound directly.
ATTACH_RUNNING_INSTANCE = r'''
if (-not ('WpsAgent.Running' -as [type])) {
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
namespace WpsAgent {
  public static class Running {
    [DllImport("ole32.dll")]
    private static extern int CLSIDFromProgID([MarshalAs(UnmanagedType.LPWStr)] string progId, out Guid clsid);
    [DllImport("oleaut32.dll")]
    private static extern int GetActiveObject(ref Guid rclsid, IntPtr reserved, [MarshalAs(UnmanagedType.IUnknown)] out object obj);
    public static object Get(string progId) {
      Guid clsid;
      if (CLSIDFromProgID(progId, out clsid) != 0) { return null; }
      object obj;
      if (GetActiveObject(ref clsid, IntPtr.Zero, out obj) != 0) { return null; }
      return obj;
    }
  }
}
"@
}
function Get-RunningWpsApp([string[]]$progIds) {
  foreach ($progId in $progIds) {
    $candidate = [WpsAgent.Running]::Get($progId)
    if ($null -ne $candidate) { return $candidate }
  }
  return $null
}
function ConvertTo-WpsLocalPath([string]$fullPath) {
  # Pure string step: \\?\C:\x -> C:\x, \\?\UNC\h\s -> \\h\s, and admin shares of this machine
  # (\\localhost\C$\x, \\<computer name>\C$\x) -> C:\x so they compare equal to the local form.
  $value = $fullPath
  if ($value.StartsWith('\\?\UNC\', [System.StringComparison]::OrdinalIgnoreCase)) { $value = '\\' + $value.Substring(8) }
  elseif ($value.StartsWith('\\?\', [System.StringComparison]::Ordinal)) { $value = $value.Substring(4) }
  $localHosts = @('localhost', '127.0.0.1', '[::1]', $env:COMPUTERNAME) | Where-Object { -not [string]::IsNullOrEmpty($_) }
  if ($value -match '^\\\\([^\\]+)\\([A-Za-z])\$(?:\\(.*))?$') {
    $shareHost = $Matches[1]
    foreach ($name in $localHosts) {
      if ([string]::Equals($name, $shareHost, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $Matches[2] + ':\' + $Matches[3]
      }
    }
  }
  return $value
}
function ConvertTo-WpsComparablePath([string]$path) {
  $value = ConvertTo-WpsLocalPath ([System.IO.Path]::GetFullPath($path))
  if ($value.Contains('~') -and [System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT) {
    # 8.3 short names are only expanded by the OS, not by GetFullPath.
    try {
      if (-not ('WpsAgent.LongPath' -as [type])) {
        Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Text;
namespace WpsAgent {
  public static class LongPath {
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern uint GetLongPathNameW(string shortPath, StringBuilder longPath, uint bufferLength);
    public static string Expand(string path) {
      StringBuilder buffer = new StringBuilder(32768);
      uint length = GetLongPathNameW(path, buffer, (uint)buffer.Capacity);
      return length == 0 || length >= buffer.Capacity ? path : buffer.ToString();
    }
  }
}
"@
      }
      $value = [WpsAgent.LongPath]::Expand($value)
    } catch { }
  }
  return $value
}
function Find-OpenWriterDocument($app, [string]$path) {
  $target = ConvertTo-WpsComparablePath $path
  for ($i = 1; $i -le [int]$app.Documents.Count; $i++) {
    $candidate = $app.Documents.Item($i)
    try { $full = ConvertTo-WpsComparablePath ([string]$candidate.FullName) } catch { continue }
    if ([string]::Equals($full, $target, [System.StringComparison]::OrdinalIgnoreCase)) { return $candidate }
  }
  return $null
}
function Find-OpenPresentation($app, [string]$path) {
  $target = ConvertTo-WpsComparablePath $path
  for ($i = 1; $i -le [int]$app.Presentations.Count; $i++) {
    $candidate = $app.Presentations.Item($i)
    try { $full = ConvertTo-WpsComparablePath ([string]$candidate.FullName) } catch { continue }
    if ([string]::Equals($full, $target, [System.StringComparison]::OrdinalIgnoreCase)) { return $candidate }
  }
  return $null
}
function Find-OpenWorkbook($app, [string]$path) {
  $target = ConvertTo-WpsComparablePath $path
  for ($i = 1; $i -le [int]$app.Workbooks.Count; $i++) {
    $candidate = $app.Workbooks.Item($i)
    try { $full = ConvertTo-WpsComparablePath ([string]$candidate.FullName) } catch { continue }
    if ([string]::Equals($full, $target, [System.StringComparison]::OrdinalIgnoreCase)) { return $candidate }
  }
  return $null
}
'''


# File-based scripts used to start their own COM session with New-Object. On some hosts that is
# not the instance a user is working in (it can even see zero open documents), so a document the
# user had open was invisible to the pre-open guard. These scripts now attach to the running
# instance first (GetActiveObject semantics) and only fall back to New-Object when WPS is not
# running. $weLaunched records which one happened: only an instance the script launched itself may
# be Quit(), and settings changed on an attached instance are restored.
#
# PRE_OPEN_GUARD also lets a script remember whether the document was open before it touched it, so
# it never closes (or silently saves over) a user's interactive document.
PRE_OPEN_GUARD = ATTACH_RUNNING_INSTANCE + r'''
$script:wpsPrevSettings = @{}
function Test-WpsPathOpen($collection, [string]$path) {
  try {
    $target = ConvertTo-WpsComparablePath $path
    for ($i = 1; $i -le [int]$collection.Count; $i++) {
      try { $full = ConvertTo-WpsComparablePath ([string]$collection.Item($i).FullName) } catch { continue }
      if ([string]::Equals($full, $target, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
    }
  } catch { }
  return $false
}
function Open-WpsDocument($collection, [string]$path, [bool]$wasOpen, [bool]$readOnly = $false) {
  # A document that is already open must be used as is: Workbooks.Open() on an open, unsaved workbook
  # can hand back a different object (Saved=true, without the in-memory edits), which hides the dirty
  # state from Assert-WpsPreOpenSaved. Anything else is opened by its local path because WPS cannot
  # open some UNC spellings (\\localhost\C$\...) that point at a local drive.
  if ($wasOpen) {
    $target = ConvertTo-WpsComparablePath $path
    for ($i = 1; $i -le [int]$collection.Count; $i++) {
      $candidate = $collection.Item($i)
      try { $full = ConvertTo-WpsComparablePath ([string]$candidate.FullName) } catch { continue }
      if ([string]::Equals($full, $target, [System.StringComparison]::OrdinalIgnoreCase)) { return $candidate }
    }
  }
  $openPath = ConvertTo-WpsLocalPath $path
  if ($readOnly) { return $collection.Open($openPath, 0, $true) }
  return $collection.Open($openPath)
}
function Assert-WpsPreOpenSaved([bool]$wasOpen, $document) {
  if ($wasOpen -and -not [bool]$document.Saved) {
    throw 'The document is open in WPS with unsaved changes; save or close it before running this command.'
  }
}
function Assert-WpsPresentationNotOpen([bool]$wasOpen) {
  # WPS does not reliably report Presentation.Saved=false after in-memory edits, so unsaved changes
  # in an open presentation cannot be detected; refuse instead of risking the user's edits.
  if ($wasOpen) {
    throw 'The presentation is already open in WPS and WPS does not reliably report unsaved presentation changes; close it before running this command.'
  }
}
function Assert-WpsInputNotOpen([bool]$wasOpen) {
  if ($wasOpen) {
    throw 'The input document is already open in WPS; close it before running this command so it is not saved under another name or closed.'
  }
}
function Set-WpsAppQuiet($app, [string[]]$names) {
  foreach ($name in $names) {
    try { $script:wpsPrevSettings[$name] = $app.$name } catch { }
    try { $app.$name = $false } catch { }
  }
}
function Restore-WpsAppSettings($app) {
  foreach ($name in @($script:wpsPrevSettings.Keys)) {
    try { $app.$name = $script:wpsPrevSettings[$name] } catch { }
  }
  $script:wpsPrevSettings = @{}
}
'''

# Replaces `$app = New-Object -ComObject $params.prog_id`.
ACQUIRE_WPS_APP = (
    "$app = Get-RunningWpsApp @($params.prog_id); "
    "$weLaunched = $false; "
    "if ($null -eq $app) { $app = New-Object -ComObject $params.prog_id; $weLaunched = $true }"
)

# Only a window the script launched may be hidden; an attached instance belongs to the user.
HIDE_LAUNCHED_APP = "if ($weLaunched) { try { $app.Visible = $false } catch { } }"

# Settings are remembered and put back by RELEASE_WPS_APP.
QUIET_ALERTS = "Set-WpsAppQuiet $app @('DisplayAlerts')"


# Used in `finally`: undo setting changes, then Quit() only an instance the script launched itself
# (and only when no other document is open); an attached instance is never Quit().
RELEASE_WPS_APP = "Restore-WpsAppSettings $app; if ($weLaunched) { " + QUIT_IF_IDLE + " }"
