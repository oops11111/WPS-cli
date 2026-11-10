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
public class WShotR {
  public struct RECT { public int Left, Top, Right, Bottom; }
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
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
  try { $app.ActiveWindow.View.Zoom = 50 } catch { L "zoom failed: $($_.Exception.Message)" }
  Start-Sleep -Seconds 3
  $h = [WShotR]::Find("报告.docx")
  if ($h -eq [IntPtr]::Zero) { throw "OpusApp window not found" }
  [void][WShotR]::SetWindowPos($h, [IntPtr]::Zero, 0, 0, 1536, 864, 0x0040)
  [void][WShotR]::SetForegroundWindow($h)
  Start-Sleep -Seconds 2
  [WShotR]::Print($h, $Png)
  L "screenshot: $Png"
  $ps = $doc.PageSetup
  L ("page setup: top={0}mm bottom={1}mm left={2}mm right={3}mm paper={4}x{5}mm" -f (Pt2Mm $ps.TopMargin),(Pt2Mm $ps.BottomMargin),(Pt2Mm $ps.LeftMargin),(Pt2Mm $ps.RightMargin),(Pt2Mm $ps.PageWidth),(Pt2Mm $ps.PageHeight))
  for ($i = 1; $i -le [Math]::Min(10, $doc.Paragraphs.Count); $i++) {
    $p = $doc.Paragraphs.Item($i)
    $text = [string]$p.Range.Text
    if ($text.Length -gt 22) { $text = $text.Substring(0,22) + "..." }
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
  $fr = $doc.Sections.Item(1).Footers.Item(1).Range
  L ("footer: text='{0}' fields={1} align={2} size={3}" -f ([string]$fr.Text).Replace("`r","").Replace("`n",""), $fr.Fields.Count, $fr.Paragraphs.Item(1).Alignment, $fr.Font.Size)
  try { L "pages: $($doc.ComputeStatistics(2))" } catch { }
} catch {
  L "ERROR: $($_.Exception.GetType().FullName): $($_.Exception.Message)"
} finally {
  if ($doc) { try { $doc.Close(0) } catch { } }
  if ($app) { try { $app.Quit() } catch { } }
  $log | Set-Content -Path $LogPath -Encoding UTF8
}