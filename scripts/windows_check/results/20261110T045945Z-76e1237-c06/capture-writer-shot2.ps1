param([string]$Path,[string]$Png,[string]$LogPath)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type -TypeDefinition @"
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Text;
public class WShot3 {
  public struct RECT { public int Left, Top, Right, Bottom; }
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
  public static IntPtr Find(string titlePart) {
    IntPtr found = IntPtr.Zero;
    EnumWindows(delegate(IntPtr h, IntPtr l) {
      if (!IsWindowVisible(h)) return true;
      var c = new StringBuilder(256); GetClassName(h, c, 256);
      var t = new StringBuilder(512); GetWindowText(h, t, 512);
      if (c.ToString() == "OpusApp" && t.ToString().Contains(titlePart)) { found = h; return false; }
      return true;
    }, IntPtr.Zero);
    return found;
  }
  public static string Rect(IntPtr h) { RECT r; GetWindowRect(h, out r); return r.Left + "," + r.Top + "," + r.Right + "," + r.Bottom; }
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
$app = $null; $doc = $null
try {
  $app = New-Object -ComObject kwps.Application
  $app.Visible = $true
  $app.DisplayAlerts = 0
  $doc = $app.Documents.Open($Path)
  try { $app.ActiveWindow.View.Zoom = 50 } catch { }
  Start-Sleep -Seconds 3
  $h = [WShot3]::Find("通知.docx")
  if ($h -eq [IntPtr]::Zero) { throw "OpusApp window not found" }
  L "before rect: $([WShot3]::Rect($h))"
  [void][WShot3]::ShowWindow($h, 9)
  Start-Sleep -Milliseconds 500
  [void][WShot3]::SetWindowPos($h, [IntPtr]::Zero, 0, 0, 1536, 864, 0x0040)
  Start-Sleep -Seconds 1
  [void][WShot3]::SetForegroundWindow($h)
  Start-Sleep -Seconds 1
  L "after rect: $([WShot3]::Rect($h))"
  [WShot3]::Print($h, $Png)
  [WShot3]::Screen(($Png -replace '\.png$','-screen.png'))
  L "saved $Png"
} catch {
  L "ERROR: $($_.Exception.GetType().FullName): $($_.Exception.Message)"
} finally {
  if ($doc) { try { $doc.Close(0) } catch { } }
  if ($app) { try { $app.Quit() } catch { } }
  $log | Set-Content -Path $LogPath -Encoding UTF8
}