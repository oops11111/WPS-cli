param([string]$Path,[string]$LogPath)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -TypeDefinition @"
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public class WEnumAll {
  public struct RECT { public int Left, Top, Right, Bottom; }
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  public static string[] All() {
    var list = new List<string>();
    EnumWindows(delegate(IntPtr h, IntPtr l) {
      if (!IsWindowVisible(h)) return true;
      var c = new StringBuilder(256); GetClassName(h, c, 256);
      if (!c.ToString().StartsWith("OpusApp")) return true;
      var t = new StringBuilder(512); GetWindowText(h, t, 512);
      RECT r; GetWindowRect(h, out r);
      uint pid; GetWindowThreadProcessId(h, out pid);
      list.Add("pid=" + pid + " h=" + h + " class=" + c + " title=" + t + " rect=" + r.Left + "," + r.Top + "," + r.Right + "," + r.Bottom);
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
  $vs = [System.Windows.Forms.SystemInformation]::VirtualScreen
  L "virtual screen: $($vs.Width)x$($vs.Height) at $($vs.X),$($vs.Y)"
  $app = New-Object -ComObject kwps.Application
  $app.Visible = $true
  $app.DisplayAlerts = 0
  $doc = $app.Documents.Open($Path)
  Start-Sleep -Seconds 3
  L "all OpusApp windows:"
  [WEnumAll]::All() | ForEach-Object { L "  $_" }
  try { L "ActiveWindow.Hwnd=$($app.ActiveWindow.Hwnd)" } catch { L "Hwnd not available: $($_.Exception.Message)" }
} catch {
  L "ERROR: $($_.Exception.GetType().FullName): $($_.Exception.Message)"
} finally {
  if ($doc) { try { $doc.Close(0) } catch { } }
  if ($app) { try { $app.Quit() } catch { } }
  $log | Set-Content -Path $LogPath -Encoding UTF8
}