param([string]$Out,[string]$LogPath)
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type -TypeDefinition @"
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Text;
public class DlgCap {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  public static void Screen(string path) {
    Rectangle b = System.Windows.Forms.SystemInformation.VirtualScreen;
    using (Bitmap bmp = new Bitmap(b.Width, b.Height)) {
      using (Graphics g = Graphics.FromImage(bmp)) { g.CopyFromScreen(b.Left, b.Top, 0, 0, bmp.Size); }
      bmp.Save(path, ImageFormat.Png);
    }
  }
  public static string[] Windows() {
    var list = new System.Collections.Generic.List<string>();
    EnumWindows(delegate(IntPtr h, IntPtr l) {
      if (IsWindowVisible(h)) {
        var c = new StringBuilder(256); GetClassName(h, c, 256);
        var t = new StringBuilder(512); GetWindowText(h, t, 512);
        uint pid; GetWindowThreadProcessId(h, out pid);
        list.Add("pid=" + pid + " class=" + c + " title=" + t);
      }
      return true;
    }, IntPtr.Zero);
    return list.ToArray();
  }
}
"@ -ReferencedAssemblies System.Drawing,System.Windows.Forms
$log = New-Object System.Collections.ArrayList
function L([string]$m) { [void]$log.Add($m); Write-Output $m }
$deadline = (Get-Date).AddSeconds(30)
$found = $false
while ((Get-Date) -lt $deadline) {
  $fg = [DlgCap]::GetForegroundWindow()
  $c = New-Object System.Text.StringBuilder 256; [void][DlgCap]::GetClassName($fg, $c, 256)
  $t = New-Object System.Text.StringBuilder 512; [void][DlgCap]::GetWindowText($fg, $t, 512)
  if (("$t" -like "*页面设置*") -or ("$t" -like "*页面*") -or ("$c" -eq "#32770")) {
    $found = $true
    L "foreground dialog: class=$c title=$t"
    break
  }
  Start-Sleep -Milliseconds 700
}
L "found dialog: $found"
[void][DlgCap]::SetForegroundWindow([DlgCap]::GetForegroundWindow())
Start-Sleep -Milliseconds 800
[DlgCap]::Screen($Out)
L "screenshot: $Out"
L "visible windows:"
[DlgCap]::Windows() | Where-Object { $_ -like '*WPS*' -or $_ -like '*页面*' -or $_ -like '*#32770*' } | ForEach-Object { L "  $_" }
[System.Windows.Forms.SendKeys]::SendWait("{ESC}")
L "sent ESC"
$log | Set-Content -Path $LogPath -Encoding UTF8