param([string]$Path,[string]$LogPath)
$ErrorActionPreference = "Stop"
Add-Type -TypeDefinition @"
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public class WEnum {
  public struct RECT { public int Left, Top, Right, Bottom; }
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  public static string[] All(uint targetPid) {
    var list = new List<string>();
    EnumWindows(delegate(IntPtr h, IntPtr l) {
      if (!IsWindowVisible(h)) return true;
      uint pid; GetWindowThreadProcessId(h, out pid);
      if (pid != targetPid) return true;
      var c = new StringBuilder(256); GetClassName(h, c, 256);
      var t = new StringBuilder(512); GetWindowText(h, t, 512);
      RECT r; GetWindowRect(h, out r);
      list.Add("h=" + h + " class=" + c + " title=" + t + " rect=" + r.Left + "," + r.Top + "," + r.Right + "," + r.Bottom);
      return true;
    }, IntPtr.Zero);
    return list.ToArray();
  }
}
"@
$log = New-Object System.Collections.ArrayList
function L([string]$m) { [void]$log.Add($m); Write-Output $m }
$app = $null; $doc = $null
try {
  $app = New-Object -ComObject kwps.Application
  $app.Visible = $true
  $app.DisplayAlerts = 0
  $doc = $app.Documents.Open($Path)
  Start-Sleep -Seconds 3
  $proc = Get-Process wps -ErrorAction SilentlyContinue | Sort-Object Id | Select-Object -First 1
  L "wps pid: $($proc.Id)"
  [WEnum]::All([uint32]$proc.Id) | ForEach-Object { L "  $_" }
  try { L "ActiveWindow.WindowState=$($app.ActiveWindow.WindowState)" } catch { L "state err: $($_.Exception.Message)" }
  try { $app.ActiveWindow.WindowState = 1; L "set WindowState=1 ok" } catch { L "set state 1 err: $($_.Exception.Message)" }
  Start-Sleep -Seconds 2
  [WEnum]::All([uint32]$proc.Id) | ForEach-Object { L "  after: $_" }
} catch {
  L "ERROR: $($_.Exception.GetType().FullName): $($_.Exception.Message)"
} finally {
  if ($doc) { try { $doc.Close(0) } catch { } }
  if ($app) { try { $app.Quit() } catch { } }
  $log | Set-Content -Path $LogPath -Encoding UTF8
}