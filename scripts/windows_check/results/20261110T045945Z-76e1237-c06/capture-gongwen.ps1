param([string]$Path,[string]$Png,[string]$LogPath)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type -TypeDefinition @"
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
public class WShot {
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
function Pt2Mm($pt) { return [math]::Round(([double]$pt * 25.4 / 72.0), 1) }
$app = $null; $doc = $null
try {
  $app = New-Object -ComObject kwps.Application
  $app.Visible = $true
  $app.DisplayAlerts = 0
  $doc = $app.Documents.Open($Path)
  try { $app.ActiveWindow.View.Zoom = 70 } catch { try { $app.ActiveWindow.Zoom = 70 } catch { } }
  try { $app.ActiveWindow.WindowState = -4137 } catch { }
  Start-Sleep -Seconds 2
  $proc = Get-Process wps -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
  if (-not $proc) { throw "no wps process with a window" }
  [void][WShot]::ShowWindow($proc.MainWindowHandle, 3)
  [void][WShot]::SetForegroundWindow($proc.MainWindowHandle)
  Start-Sleep -Seconds 1
  [WShot]::Print($proc.MainWindowHandle, $Png)
  L "screenshot: $Png (title '$($proc.MainWindowTitle)')"
  $ps = $doc.PageSetup
  L ("page setup: top={0}mm bottom={1}mm left={2}mm right={3}mm paper={4}x{5}mm orientation={6}" -f (Pt2Mm $ps.TopMargin),(Pt2Mm $ps.BottomMargin),(Pt2Mm $ps.LeftMargin),(Pt2Mm $ps.RightMargin),(Pt2Mm $ps.PageWidth),(Pt2Mm $ps.PageHeight),$ps.Orientation)
  L ("paragraphs={0} tables={1} inlineShapes={2}" -f $doc.Paragraphs.Count,$doc.Tables.Count,$doc.InlineShapes.Count)
  for ($i = 1; $i -le $doc.Paragraphs.Count; $i++) {
    $p = $doc.Paragraphs.Item($i)
    $text = [string]$p.Range.Text
    if ($text.Length -gt 24) { $text = $text.Substring(0,24) + "..." }
    $font = $null; $size = $null; $align = $null; $ls = $null; $rule = $null; $indent = $null; $bold = $null
    try { $font = $p.Range.Font.NameFarEast } catch { }
    try { $size = $p.Range.Font.Size } catch { }
    try { $align = $p.Alignment } catch { }
    try { $ls = $p.LineSpacing } catch { }
    try { $rule = $p.LineSpacingRule } catch { }
    try { $indent = $p.FirstLineIndent } catch { }
    try { $bold = $p.Range.Font.Bold } catch { }
    L ("p{0}: font={1} size={2} bold={3} align={4} lineSpacing={5} rule={6} firstIndent={7}pt text='{8}'" -f $i,$font,$size,$bold,$align,$ls,$rule,$indent,$text)
  }
  $sec = $doc.Sections.Item(1)
  $footer = $sec.Footers.Item(1)
  $fr = $footer.Range
  L ("footer: text='{0}' fields={1} align={2} font={3} size={4}" -f ([string]$fr.Text).Replace("`r","").Replace("`n",""), $fr.Fields.Count, $fr.Paragraphs.Item(1).Alignment, $fr.Font.NameFarEast, $fr.Font.Size)
  if ($fr.Fields.Count -gt 0) {
    for ($f = 1; $f -le $fr.Fields.Count; $f++) { L ("  field {0}: type={1} result='{2}'" -f $f, $fr.Fields.Item($f).Type, [string]$fr.Fields.Item($f).Result.Text) }
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