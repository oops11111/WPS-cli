param([string]$Out,[string]$LogPath)
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type -TypeDefinition @"
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Text;
public class DlgClick {
  public struct RECT { public int Left, Top, Right, Bottom; }
  public struct POINT { public int X, Y; }
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
  public static IntPtr Find(string titlePart) {
    IntPtr found = IntPtr.Zero;
    EnumWindows(delegate(IntPtr h, IntPtr l) {
      if (!IsWindowVisible(h)) return true;
      var t = new StringBuilder(512); GetWindowText(h, t, 512);
      if (t.ToString().Contains(titlePart)) { found = h; return false; }
      return true;
    }, IntPtr.Zero);
    return found;
  }
  public static void ClickClient(IntPtr h, int x, int y) {
    IntPtr lp = (IntPtr)((y << 16) | (x & 0xFFFF));
    PostMessage(h, 0x0201, (IntPtr)1, lp);
    System.Threading.Thread.Sleep(60);
    PostMessage(h, 0x0202, IntPtr.Zero, lp);
  }
  public static void Print(IntPtr hwnd, string path) {
    RECT r; GetWindowRect(hwnd, out r);
    int w = Math.Max(1, r.Right - r.Left); int h = Math.Max(1, r.Bottom - r.Top);
    using (Bitmap bmp = new Bitmap(w, h)) {
      using (Graphics g = Graphics.FromImage(bmp)) { IntPtr hdc = g.GetHdc(); PrintWindow(hwnd, hdc, 2); g.ReleaseHdc(hdc); }
      bmp.Save(path, ImageFormat.Png);
    }
  }
}
"@ -ReferencedAssemblies System.Drawing,System.Windows.Forms
$log = New-Object System.Collections.ArrayList
function L([string]$m) { [void]$log.Add($m); Write-Output $m }
$deadline = (Get-Date).AddSeconds(30); $h = [IntPtr]::Zero
while ((Get-Date) -lt $deadline) { $h = [DlgClick]::Find("页面设置"); if ($h -ne [IntPtr]::Zero) { break }; Start-Sleep -Milliseconds 500 }
if ($h -eq [IntPtr]::Zero) { L "dialog not found"; $log | Set-Content $LogPath -Encoding UTF8; exit 1 }
$r = New-Object DlgClick+RECT; [void][DlgClick]::GetWindowRect($h, [ref]$r)
$cr = New-Object DlgClick+RECT; [void][DlgClick]::GetClientRect($h, [ref]$cr)
$origin = New-Object DlgClick+POINT; $origin.X = 0; $origin.Y = 0
[void][DlgClick]::ClientToScreen($h, [ref]$origin)
L "window=$($r.Left),$($r.Top),$($r.Right),$($r.Bottom) client=$($cr.Right)x$($cr.Bottom) clientOrigin=$($origin.X),$($origin.Y)"
$targetX = $r.Left + 140; $targetY = $r.Top + 58
$cx = $targetX - $origin.X; $cy = $targetY - $origin.Y
L "target screen=$targetX,$targetY client=$cx,$cy"
[DlgClick]::ClickClient($h, $cx, $cy)
Start-Sleep -Milliseconds 1200
[DlgClick]::Print($h, $Out)
L "saved $Out"
[void][DlgClick]::PostMessage($h, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero)
L "posted WM_CLOSE"
$log | Set-Content -Path $LogPath -Encoding UTF8