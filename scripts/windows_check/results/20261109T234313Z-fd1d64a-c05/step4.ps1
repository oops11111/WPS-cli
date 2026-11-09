param([string]$Path,[string]$SheetPng,[string]$DropPng,[string]$RejectPng,[string]$LogPath)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type -TypeDefinition @"
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Text;
using System.Collections.Generic;
public class WpsCap {
  public struct RECT { public int Left, Top, Right, Bottom; }
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hwnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hwnd, int cmd);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  public static void Print(IntPtr hwnd, string path) {
    RECT r; GetWindowRect(hwnd, out r);
    int w = Math.Max(1, r.Right - r.Left); int h = Math.Max(1, r.Bottom - r.Top);
    using (Bitmap bmp = new Bitmap(w, h)) {
      using (Graphics g = Graphics.FromImage(bmp)) { IntPtr hdc = g.GetHdc(); PrintWindow(hwnd, hdc, 2); g.ReleaseHdc(hdc); }
      bmp.Save(path, ImageFormat.Png);
    }
  }
  public static void Screen(string path) {
    Rectangle b = System.Windows.Forms.SystemInformation.VirtualScreen;
    using (Bitmap bmp = new Bitmap(b.Width, b.Height)) {
      using (Graphics g = Graphics.FromImage(bmp)) { g.CopyFromScreen(b.Left, b.Top, 0, 0, bmp.Size); }
      bmp.Save(path, ImageFormat.Png);
    }
  }
  public static string[] Windows(uint targetPid) {
    List<string> list = new List<string>();
    EnumWindows(delegate(IntPtr h, IntPtr l) {
      uint pid; GetWindowThreadProcessId(h, out pid);
      if (pid == targetPid && IsWindowVisible(h)) {
        StringBuilder c = new StringBuilder(256); GetClassName(h, c, 256);
        StringBuilder t = new StringBuilder(512); GetWindowText(h, t, 512);
        list.Add("class=" + c + " title=" + t);
      }
      return true;
    }, IntPtr.Zero);
    return list.ToArray();
  }
}
"@ -ReferencedAssemblies System.Drawing,System.Windows.Forms
$log = New-Object System.Collections.ArrayList
function L([string]$m) { [void]$log.Add($m); Write-Output $m }
$app = $null; $wb = $null
try {
  $app = New-Object -ComObject ket.Application
  $app.Visible = $true
  $app.DisplayAlerts = $false
  $wb = $app.Workbooks.Open($Path)
  $ws = $wb.Worksheets.Item(1)
  $ws.Activate()
  try { $app.ActiveWindow.Zoom = 90 } catch { L "zoom failed: $($_.Exception.Message)" }
  try { $app.ActiveWindow.WindowState = -4137 } catch { L "maximize failed: $($_.Exception.Message)" }
  $ws.Range("A1").Select() | Out-Null
  Start-Sleep -Seconds 2
  $proc = Get-Process et -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
  if (-not $proc) { throw "no et process with a main window" }
  $h = $proc.MainWindowHandle
  [void][WpsCap]::ShowWindow($h, 3)
  [void][WpsCap]::SetForegroundWindow($h)
  Start-Sleep -Seconds 2
  [WpsCap]::Print($h, $SheetPng)
  L "sheet screenshot: $SheetPng"
  L "windows:"; [WpsCap]::Windows([uint32]$proc.Id) | ForEach-Object { L "  $_" }
  $ws.Range("D2").Select() | Out-Null
  [void][WpsCap]::SetForegroundWindow($h)
  Start-Sleep -Seconds 2
  [WpsCap]::Screen($DropPng)
  [WpsCap]::Print($h, ($DropPng -replace '\.png$', '-window.png'))
  L "dropdown screenshot: $DropPng"
  L "windows after D2:"; [WpsCap]::Windows([uint32]$proc.Id) | ForEach-Object { L "  $_" }
  $ws.Range("E2").Select() | Out-Null
  [void][WpsCap]::SetForegroundWindow($h)
  Start-Sleep -Milliseconds 800
  $wsh = New-Object -ComObject WScript.Shell
  [void]$wsh.AppActivate($proc.Id)
  Start-Sleep -Milliseconds 500
  $wsh.SendKeys("200~")
  Start-Sleep -Seconds 2
  [WpsCap]::Screen($RejectPng)
  [WpsCap]::Print($h, ($RejectPng -replace '\.png$', '-window.png'))
  L "reject screenshot: $RejectPng"
  L "windows after typing 200:"; [WpsCap]::Windows([uint32]$proc.Id) | ForEach-Object { L "  $_" }
  $wsh.SendKeys("{ESC}")
  Start-Sleep -Milliseconds 800
  $wsh.SendKeys("{ESC}")
  Start-Sleep -Milliseconds 500
  L "windows after ESC:"; [WpsCap]::Windows([uint32]$proc.Id) | ForEach-Object { L "  $_" }
} catch {
  L "ERROR: $($_.Exception.GetType().FullName): $($_.Exception.Message)"
} finally {
  if ($wb) { try { $wb.Close($false); L "closed workbook without saving" } catch { L "close failed: $($_.Exception.Message)" } }
  if ($app) { try { $app.Quit(); L "quit" } catch { L "quit failed: $($_.Exception.Message)" } }
  $log | Set-Content -Path $LogPath -Encoding UTF8
}