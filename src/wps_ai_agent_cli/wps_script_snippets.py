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
function Find-OpenWriterDocument($app, [string]$path) {
  $target = [System.IO.Path]::GetFullPath($path)
  for ($i = 1; $i -le [int]$app.Documents.Count; $i++) {
    $candidate = $app.Documents.Item($i)
    try { $full = [System.IO.Path]::GetFullPath([string]$candidate.FullName) } catch { continue }
    if ([string]::Equals($full, $target, [System.StringComparison]::OrdinalIgnoreCase)) { return $candidate }
  }
  return $null
}
'''
