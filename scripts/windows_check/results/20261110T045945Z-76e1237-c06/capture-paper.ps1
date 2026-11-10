param([string]$Out,[string]$LogPath)
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type -TypeDefinition @"
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Text;
public class DlgShot2 {
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
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, UIntPtr e);
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
  public static void Print(IntPtr hwnd, string path) {
    RECT r; GetWindowRect(hwnd, out r);
    int w = Math.Max(1, r.Right - r.Left); int h = Math.Max(1, r.Bottom - r.Top);
    using (Bitmap bmp = new Bitmap(w, h)) {
      using (Graphics g = Graphics.FromImage(bmp)) { IntPtr hdc = g.GetHdc(); PrintWindow(hwnd, hdc, 2); g.ReleaseHdc(hdc); }
      bmp.Save(path, ImageFormat.Png);
    }
  }
  public static void Click(int x, int y) {
    SetCursorPos(x, y); System.Threading.Thread.Sleep(250);
    mouse_event(2, 0, 0, 0, UIntPtr.Zero); System.Threading.Thread.Sleep(80);
    mouse_event(4, 0, 0, 0, UIntPtr.Zero);
  }
  public static bool Close(IntPtr h) { return PostMessage(h, 0x0010, IntPtr.Zero, IntPtr.Zero); }
}
"@ -ReferencedAssemblies System.Drawing,System.Windows.Forms
$log = New-Object System.Collections.ArrayList
function L([string]$m) { [void]$log.Add($m); Write-Output $m }
$deadline = (Get-Date).AddSeconds(30)
$h = [IntPtr]::Zero
while ((Get-Date) -lt $deadline) {
  $h = [DlgShot2]::Find("页面设置")
  if ($h -ne [IntPtr]::Zero) { break }
  Start-Sleep -Milliseconds 500
}
if ($h -eq [IntPtr]::Zero) { L "dialog not found"; $log | Set-Content $LogPath -Encoding UTF8; exit 1 }
$r = New-Object DlgShot2+RECT
[void][DlgShot2]::GetWindowRect($h, [ref]$r)
L "dialog rect=$($r.Left),$($r.Top),$($r.Right),$($r.Bottom)"
[void][DlgShot2]::SetForegroundWindow($h)
Start-Sleep -Milliseconds 500
[void][DlgShot2]::Click(($r.Left + 150), ($r.Top + 58))
Start-Sleep -Milliseconds 900
[DlgShot2]::Print($h, $Out)
L "saved $Out"
[void][DlgShot2]::Close($h)
L "posted WM_CLOSE"
$log | Set-Content -Path $LogPath -Encoding UTF8