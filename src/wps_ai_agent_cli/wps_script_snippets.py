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
ATTACH_RUNNING_INSTANCE = r"""
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
"""


# File-based scripts used to start their own COM session with New-Object. On some hosts that is
# not the instance a user is working in (it can even see zero open documents), so a document the
# user had open was invisible to the pre-open guard. These scripts now attach to the running
# instance first (GetActiveObject semantics) and only fall back to New-Object when WPS is not
# running. $weLaunched records which one happened: only an instance the script launched itself may
# be Quit(), and settings changed on an attached instance are restored.
#
# PRE_OPEN_GUARD also lets a script remember whether the document was open before it touched it, so
# it never closes (or silently saves over) a user's interactive document.
PRE_OPEN_GUARD = (
    ATTACH_RUNNING_INSTANCE
    + r"""
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
function Get-WpsProcessName([string]$progId) {
  $id = ([string]$progId).ToLowerInvariant()
  if ($id.Contains('wpp') -or $id.Contains('presentation')) { return 'wpp' }
  if ($id.Contains('ket') -or $id.StartsWith('et.') -or $id.Contains('spreadsheet')) { return 'et' }
  if ($id.Contains('wps') -or $id.Contains('writer')) { return 'wps' }
  return $null
}
function Get-WpsProcessSnapshot([string]$processName) {
  # "Windowed" = a process of this user session that owns a main window. Only those can hold a document
  # the user is working in; helper, cloud and background WPS processes (several `wps` processes are
  # normal) have no main window or live in another session, so they are reported but not counted.
  $mySession = [System.Diagnostics.Process]::GetCurrentProcess().SessionId
  $all = @(Get-Process -Name $processName -ErrorAction SilentlyContinue)
  $windowed = @($all | Where-Object { $_.SessionId -eq $mySession -and [int64]$_.MainWindowHandle -ne 0 })
  return [pscustomobject]@{ All = $all; Windowed = $windowed }
}
function Format-WpsProcessList($processes) {
  return (@($processes | Select-Object -First 5 | ForEach-Object {
    $title = [string]$_.MainWindowTitle
    if ($title.Length -gt 60) { $title = $title.Substring(0, 60) }
    'pid ' + $_.Id + $(if ($title) { ' "' + $title + '"' } else { '' })
  }) -join ', ')
}
function Assert-WpsSingleInstance([string]$progId) {
  # GetActiveObject returns one instance. With several windowed WPS processes of the same component, a
  # document the user has open can live in another one that this script cannot see, so opening it here
  # could race with (or silently duplicate) the user's session. Refuse instead of guessing. When only
  # one process has a window the others are assumed to be background processes: proceed, with a warning.
  if ($env:WPS_AGENT_ALLOW_MULTI_INSTANCE -eq '1') { return }
  $name = Get-WpsProcessName $progId
  if ([string]::IsNullOrEmpty($name)) { return }
  try { $snapshot = Get-WpsProcessSnapshot $name } catch { return }
  $windowed = @($snapshot.Windowed)
  $total = @($snapshot.All).Count
  if ($windowed.Count -gt 1) {
    throw ('Several WPS instances with a window are running (' + $name + ' x' + $windowed.Count + ': ' + (Format-WpsProcessList $windowed) + '), so it cannot be determined whether this document is already open in another instance. Close the extra WPS windows and retry, or set WPS_AGENT_ALLOW_MULTI_INSTANCE=1 to skip this check.')
  }
  if ($total -gt 1) {
    [Console]::Error.WriteLine('WPS_AGENT_WARNING: ' + $total + ' ' + $name + ' processes are running but only ' + $windowed.Count + ' has a window; the others are assumed to be background processes, so a document open in a hidden instance cannot be ruled out.')
  }
}
function Find-WpsOpenDocument($collection, [string]$path) {
  try {
    $target = ConvertTo-WpsComparablePath $path
    for ($i = 1; $i -le [int]$collection.Count; $i++) {
      $candidate = $collection.Item($i)
      try { $full = ConvertTo-WpsComparablePath ([string]$candidate.FullName) } catch { continue }
      if ([string]::Equals($full, $target, [System.StringComparison]::OrdinalIgnoreCase)) { return $candidate }
    }
  } catch { }
  return $null
}
function Stop-WpsConcurrentOpen([string]$what, [string]$detail) {
  throw ('The ' + $what + ' was opened in WPS between the check and the open call' + $detail + '. Open() had already been called on it, and WPS can reload an open document from disk without asking (alerts are turned off here), so unsaved edits made in WPS may already be lost. The command was refused and wrote, saved and closed nothing; check the document in WPS before retrying.')
}
function Stop-WpsAlreadyOpen([string]$what) {
  throw ('The ' + $what + ' is open in WPS. Open() was not called and nothing was touched, written, saved or closed. Close it in WPS (or save it, for a document with no unsaved changes) and retry.')
}
function Assert-WpsFileNotHeld([string]$path, [string]$what, [bool]$readOnly = $false) {
  # Open() on a document that is already open reloads it from disk (silently, because alerts are turned off here) and
  # throws away unsaved edits, so Open() must not be called for a file that may be open in WPS. WPS keeps a handle
  # on a document it has open: a changing command asks for exclusive access (any other handle is a conflict); a
  # read-only command only asks to be allowed to read next to other readers (a writer or an exclusive holder is a conflict).
  # A file that cannot be probed is refused as well. A missing file is left to Open() to report.
  $localPath = ConvertTo-WpsLocalPath $path
  $share = if ($readOnly) { [System.IO.FileShare]::Read } else { [System.IO.FileShare]::None }
  $stream = $null
  $held = $null
  $unknown = $null
  try {
    $stream = [System.IO.File]::Open($localPath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, $share)
  } catch [System.IO.FileNotFoundException] {
    return
  } catch [System.IO.DirectoryNotFoundException] {
    return
  } catch [System.IO.IOException] {
    $held = $_.Exception.Message
  } catch {
    $unknown = $_.Exception.Message
  } finally {
    if ($null -ne $stream) { $stream.Dispose() }
  }
  if ($null -ne $held) {
    throw ('The ' + $what + ' is held open by another handle (' + $held + '), most likely because it is open in WPS. Open() was not called: on a document that is already open it reloads the file from disk without asking (alerts are turned off here) and discards unsaved edits made in WPS. The command was refused and nothing was written, saved or closed. Save or close the document in WPS (or the program that holds the file) and retry.')
  }
  if ($null -ne $unknown) {
    throw ('The ' + $what + ' could not be checked for being open in WPS (' + $unknown + '). Open() was not called, because on a document that is already open it reloads the file from disk without asking (alerts are turned off here) and discards unsaved edits. The command was refused as a precaution and nothing was written, saved or closed.')
  }
}
function Open-WpsDocument($collection, [string]$path, [bool]$wasOpen, [bool]$readOnly = $false) {
  # A document that is already open must be used as is: Workbooks.Open() on an open workbook reloads it from disk
  # and drops unsaved edits (the object held before is left empty). Anything else is opened by its local path because
  # WPS cannot open some UNC spellings (\\localhost\C$\...) that point at a local drive.
  if ($wasOpen) {
    $existing = Find-WpsOpenDocument $collection $path
    if ($null -ne $existing) { return $existing }
  }
  if (-not $readOnly) { Assert-WpsSingleInstance $params.prog_id }
  # Look once more right before Open(): the user may have opened the document since the caller's check.
  $existing = Find-WpsOpenDocument $collection $path
  if ($null -ne $existing) { $script:wpsPreOpen = $true; return $existing }
  # Then make sure nothing holds the file open (WPS does for an open document) so Open() is never called on it.
  Assert-WpsFileNotHeld $path 'document' $readOnly
  $openPath = ConvertTo-WpsLocalPath $path
  $countBefore = [int]$collection.Count
  if ($readOnly) { $opened = $collection.Open($openPath, 0, $true) } else { $opened = $collection.Open($openPath) }
  if ([int]$collection.Count -le $countBefore) {
    # Nothing new appeared in the collection, so the document was opened by someone else between the
    # lock check and Open(), and Open() has run on it. It is not ours to close. Which copy Open() returned cannot
    # be told (on ET it can be a detached copy read from disk with Saved=true, and so can the copy found afterwards
    # by path), so Saved is not trusted here: a command that changes the document is refused outright.
    $script:wpsPreOpen = $true
    if (-not $readOnly) { Stop-WpsConcurrentOpen 'document' ' (which copy Open() returned cannot be told)' }
    [Console]::Error.WriteLine('WPS_AGENT_WARNING: the document was opened in WPS between the check and the open call; Open() had already been called on it, and WPS can reload an open document from disk without asking, so the values read come from the saved file and unsaved edits made in WPS may have been discarded.')
    $existing = Find-WpsOpenDocument $collection $path
    if ($null -ne $existing) { return $existing }
  }
  return $opened
}
function Open-WpsPresentation($collection, [string]$path) {
  # Presentation.Saved cannot be trusted, so a presentation that turns out to be open is never touched.
  if ($null -ne (Find-WpsOpenDocument $collection $path)) { $script:wpsPreOpen = $true; Stop-WpsAlreadyOpen 'presentation' }
  Assert-WpsFileNotHeld $path 'presentation'
  $countBefore = [int]$collection.Count
  $opened = $collection.Open((ConvertTo-WpsLocalPath $path), $false, $false, $false)
  if ([int]$collection.Count -le $countBefore) { $script:wpsPreOpen = $true; Stop-WpsConcurrentOpen 'presentation' '' }
  return $opened
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
"""
)

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
