param([string]$Path,[string]$Png,[string]$LogPath)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type -TypeDefinition @"
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
public class WpsShot {
  public struct RECT { public int Left, Top, Right, Bottom; }
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd, out RECT r);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hwnd, int cmd);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hwnd);
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
$app = $null; $doc = $null
try {
  $app = New-Object -ComObject kwps.Application
  $app.Visible = $true
  $app.DisplayAlerts = 0
  $doc = $app.Documents.Open($Path)
  try { $app.ActiveWindow.View.Zoom = 60 } catch { try { $app.ActiveWindow.Zoom = 60 } catch { L "zoom failed: $($_.Exception.Message)" } }
  try { $app.ActiveWindow.WindowState = -4137 } catch { }
  Start-Sleep -Seconds 2
  $proc = Get-Process wps -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
  if (-not $proc) { throw "no wps process with a window" }
  [void][WpsShot]::ShowWindow($proc.MainWindowHandle, 3)
  [void][WpsShot]::SetForegroundWindow($proc.MainWindowHandle)
  Start-Sleep -Seconds 1
  [WpsShot]::Print($proc.MainWindowHandle, $Png)
  L "screenshot: $Png (pid $($proc.Id), title '$($proc.MainWindowTitle)')"
  L "inline shapes: $($doc.InlineShapes.Count); tables: $($doc.Tables.Count); paragraphs: $($doc.Paragraphs.Count)"
  try { L "pages: $($doc.ComputeStatistics(2))" } catch { L "page statistic failed: $($_.Exception.Message)" }
  for ($i = 1; $i -le $doc.Paragraphs.Count; $i++) {
    $p = $doc.Paragraphs.Item($i)
    $text = [string]$p.Range.Text
    if ($text.Length -gt 28) { $text = $text.Substring(0,28) + "..." }
    $shapes = 0
    try { $shapes = $p.Range.InlineShapes.Count } catch { }
    $align = $null; $font = $null; $size = $null; $indent = $null; $spacing = $null; $spaceRule = $null
    try { $align = $p.Alignment } catch { }
    try { $font = $p.Range.Font.NameFarEast } catch { }
    try { $size = $p.Range.Font.Size } catch { }
    try { $indent = $p.FirstLineIndent } catch { }
    try { $spacing = $p.LineSpacing } catch { }
    try { $spaceRule = $p.LineSpacingRule } catch { }
    L ("p{0}: shapes={1} align={2} font={3} size={4} firstIndent={5} lineSpacing={6} rule={7} text='{8}'" -f $i,$shapes,$align,$font,$size,$indent,$spacing,$spaceRule,$text)
  }
  for ($i = 1; $i -le $doc.InlineShapes.Count; $i++) {
    $s = $doc.InlineShapes.Item($i)
    L ("shape {0}: width={1}pt height={2}pt type={3}" -f $i, $s.Width, $s.Height, $s.Type)
  }
  $doc.Close(0)
  $doc = $null
  $app.Quit()
  $app = $null
} catch {
  L "ERROR: $($_.Exception.GetType().FullName): $($_.Exception.Message)"
} finally {
  if ($doc) { try { $doc.Close(0) } catch { } }
  if ($app) { try { $app.Quit() } catch { } }
  $log | Set-Content -Path $LogPath -Encoding UTF8
}