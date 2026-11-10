param([string]$Out,[string]$FullOut,[string]$LogPath)
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type -TypeDefinition @"
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Text;
public class DlgShot {
  public struct RECT { public int Left, Top, Right, Bottom; }
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
  public static IntPtr Find(string titlePart, string classPart) {
    IntPtr found = IntPtr.Zero;
    EnumWindows(delegate(IntPtr h, IntPtr l) {
      if (!IsWindowVisible(h)) return true;
      var c = new StringBuilder(256); GetClassName(h, c, 256);
      var t = new StringBuilder(512); GetWindowText(h, t, 512);
      if (t.ToString().Contains(titlePart) && (classPart == "" || c.ToString().StartsWith(classPart))) { found = h; return false; }
      return true;
    }, IntPtr.Zero);
    return found;
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
  public static bool Close(IntPtr h) { return PostMessage(h, 0x0010, IntPtr.Zero, IntPtr.Zero); }
}
"@ -ReferencedAssemblies System.Drawing,System.Windows.Forms
$log = New-Object System.Collections.ArrayList
function L([string]$m) { [void]$log.Add($m); Write-Output $m }
$h = [DlgShot]::Find("页面设置", "")
if ($h -eq [IntPtr]::Zero) { L "dialog not found"; $log | Set-Content $LogPath -Encoding UTF8; exit 1 }
$r = New-Object DlgShot+RECT
[void][DlgShot]::GetWindowRect($h, [ref]$r)
L "dialog handle=$h rect=$($r.Left),$($r.Top),$($r.Right),$($r.Bottom)"
[void][DlgShot]::SetForegroundWindow($h)
Start-Sleep -Milliseconds 800
[DlgShot]::Print($h, $Out)
[DlgShot]::Screen($FullOut)
L "saved $Out and $FullOut"
[void][DlgShot]::Close($h)
L "posted WM_CLOSE"
$log | Set-Content -Path $LogPath -Encoding UTF8