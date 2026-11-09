param([string]$Path,[string]$DropPng,[string]$LogPath)
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
public class WpsCap4 {
  public struct RECT { public int Left, Top, Right, Bottom; }
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hwnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hwnd, int cmd);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, UIntPtr e);
  public static void Click(int x, int y) {
    SetCursorPos(x, y);
    System.Threading.Thread.Sleep(300);
    mouse_event(2, 0, 0, 0, UIntPtr.Zero);
    System.Threading.Thread.Sleep(100);
    mouse_event(4, 0, 0, 0, UIntPtr.Zero);
  }
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
  try { $app.ActiveWindow.Zoom = 90 } catch { }
  try { $app.ActiveWindow.WindowState = -4137 } catch { }
  $ws.Range("D2").Select() | Out-Null
  Start-Sleep -Seconds 2
  $proc = Get-Process et -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
  $h = $proc.MainWindowHandle
  [void][WpsCap4]::ShowWindow($h, 3)
  [void][WpsCap4]::SetForegroundWindow($h)
  Start-Sleep -Seconds 1
  $range = $ws.Range("D2")
  $aw = $app.ActiveWindow
  $x = $null; $y = $null
  try {
    $x = [int]$aw.PointsToScreenPixelsX([double]$range.Left + [double]$range.Width - 4)
    $y = [int]$aw.PointsToScreenPixelsY([double]$range.Top + [double]$range.Height / 2)
    L "computed click point: $x,$y (cell left=$($range.Left) top=$($range.Top) width=$($range.Width) height=$($range.Height))"
  } catch { L "PointsToScreenPixels failed: $($_.Exception.Message)" }
  if ($null -eq $x) { throw "cannot compute the dropdown arrow position" }
  [WpsCap4]::Click($x, $y)
  Start-Sleep -Milliseconds 600
  [WpsCap4]::Click($x, $y)
  Start-Sleep -Seconds 2
  [WpsCap4]::Screen($DropPng)
  [WpsCap4]::Print($h, ($DropPng -replace '\.png$', '-window.png'))
  L "dropdown screenshot: $DropPng"
  [System.Windows.Forms.SendKeys]::SendWait("{ESC}")
  Start-Sleep -Milliseconds 500
} catch {
  L "ERROR: $($_.Exception.GetType().FullName): $($_.Exception.Message)"
} finally {
  if ($wb) { try { $wb.Close($false); L "closed without saving" } catch { L "close failed: $($_.Exception.Message)" } }
  if ($app) { try { $app.Quit(); L "quit" } catch { L "quit failed: $($_.Exception.Message)" } }
  $log | Set-Content -Path $LogPath -Encoding UTF8
}