param([string]$Out,[string]$LogPath)
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type -TypeDefinition @"
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Text;
using System.Collections.Generic;
public class DlgTab {
  public struct RECT { public int Left, Top, Right, Bottom; }
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr p, EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
  public static IntPtr FindDialog(string titlePart) {
    IntPtr found = IntPtr.Zero;
    EnumWindows(delegate(IntPtr h, IntPtr l) {
      if (!IsWindowVisible(h)) return true;
      var t = new StringBuilder(512); GetWindowText(h, t, 512);
      if (t.ToString().Contains(titlePart)) { found = h; return false; }
      return true;
    }, IntPtr.Zero);
    return found;
  }
  public static string[] Children(IntPtr parent) {
    var list = new List<string>();
    EnumChildWindows(parent, delegate(IntPtr h, IntPtr l) {
      var c = new StringBuilder(256); GetClassName(h, c, 256);
      var t = new StringBuilder(512); GetWindowText(h, t, 512);
      RECT r; GetWindowRect(h, out r);
      list.Add("h=" + h + " class=" + c + " title=" + t + " rect=" + r.Left + "," + r.Top + "," + r.Right + "," + r.Bottom);
      return true;
    }, IntPtr.Zero);
    return list.ToArray();
  }
  public static IntPtr FindTab(IntPtr parent) {
    IntPtr found = IntPtr.Zero;
    EnumChildWindows(parent, delegate(IntPtr h, IntPtr l) {
      var c = new StringBuilder(256); GetClassName(h, c, 256);
      if (c.ToString().StartsWith("SysTabControl32")) { found = h; return false; }
      return true;
    }, IntPtr.Zero);
    return found;
  }
  public static int TabCount(IntPtr tab) { return (int)SendMessage(tab, 0x1304, IntPtr.Zero, IntPtr.Zero); }
  public static string TabRect(IntPtr tab, int index) {
    IntPtr mem = Marshal.AllocHGlobal(16);
    SendMessage(tab, 0x130A, (IntPtr)index, mem);
    int[] r = new int[4]; Marshal.Copy(mem, r, 0, 4); Marshal.FreeHGlobal(mem);
    return r[0] + "," + r[1] + "," + r[2] + "," + r[3];
  }
  public static void Click(IntPtr h, int x, int y) {
    IntPtr lp = (IntPtr)((y << 16) | (x & 0xFFFF));
    SendMessage(h, 0x0201, (IntPtr)1, lp);
    SendMessage(h, 0x0202, IntPtr.Zero, lp);
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
while ((Get-Date) -lt $deadline) { $h = [DlgTab]::FindDialog("页面设置"); if ($h -ne [IntPtr]::Zero) { break }; Start-Sleep -Milliseconds 500 }
if ($h -eq [IntPtr]::Zero) { L "dialog not found"; $log | Set-Content $LogPath -Encoding UTF8; exit 1 }
L "dialog h=$h"
[DlgTab]::Children($h) | ForEach-Object { L "child: $_" }
$tab = [DlgTab]::FindTab($h)
L "tab control: $tab"
if ($tab -ne [IntPtr]::Zero) {
  L "tab count: $([DlgTab]::TabCount($tab))"
  L "tab 1 rect: $([DlgTab]::TabRect($tab,1))"
  $parts = ([DlgTab]::TabRect($tab,1)).Split(',')
  $cx = [int](([int]$parts[0] + [int]$parts[2]) / 2); $cy = [int](([int]$parts[1] + [int]$parts[3]) / 2)
  L "clicking tab 1 at $cx,$cy"
  [DlgTab]::Click($tab, $cx, $cy)
  Start-Sleep -Milliseconds 1000
}
[DlgTab]::Print($h, $Out)
L "saved $Out"
[void][DlgTab]::PostMessage($h, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero)
L "posted WM_CLOSE"
$log | Set-Content -Path $LogPath -Encoding UTF8