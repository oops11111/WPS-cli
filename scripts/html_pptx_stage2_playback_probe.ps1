param(
  [Parameter(Mandatory=$true)][string]$Deck,
  [Parameter(Mandatory=$true)][string]$OutDir,
  [switch]$WindowCapture
)

$ErrorActionPreference = 'Stop'
$null = New-Item -ItemType Directory -Path $OutDir -Force
$diag = Join-Path $OutDir 'rot.json'
. "$PSScriptRoot/real_wps_verify_p6/automation-diagnostic.ps1" -Out $diag | Out-Null
$path = (Resolve-Path -LiteralPath $Deck).Path
$entry = @([WpsAgentDiagnostic.Probe]::Entries(@('.pptx')) | Where-Object { $_.DisplayName -eq $path })
if ($entry.Count -ne 1 -or $null -eq $entry[0].Value) { throw 'Disposable deck not found uniquely in ROT.' }
$doc = $entry[0].Value

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
if ($WindowCapture) {
  Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class WpsStage2Capture {
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdc, uint flags);
}
"@
}
$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$events = @()
function Capture([string]$Label) {
  $png = Join-Path $OutDir "$Label.png"
  $bitmap = [System.Drawing.Bitmap]::new($screen.Width, $screen.Height)
  $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
  $captureOk = $true
  try {
    if ($WindowCapture) {
      $hdc = $graphics.GetHdc()
      try { $captureOk = [WpsStage2Capture]::PrintWindow([IntPtr]([int64]$window.HWND), $hdc, 2) }
      finally { $graphics.ReleaseHdc($hdc) }
    } else {
      $graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
    }
    $bitmap.Save($png, [System.Drawing.Imaging.ImageFormat]::Png)
  } finally { $graphics.Dispose(); $bitmap.Dispose() }
  $slideIndex = $null
  $viewState = $null
  try { $slideIndex = [int]$view.Slide.SlideIndex } catch { }
  try { $viewState = [int]$view.State } catch { }
  $script:events += [ordered]@{
    label=$Label
    at_utc=(Get-Date).ToUniversalTime().ToString('o')
    png=$png
    capture_ok=$captureOk
    slide=$slideIndex
    view_state=$viewState
  }
}

$window = $doc.SlideShowSettings.Run()
$view = $window.View
Start-Sleep -Milliseconds 150
Capture 'slide1_early'
Start-Sleep -Milliseconds 900
Capture 'slide1_late'
$view.GotoSlide(2)
Start-Sleep -Milliseconds 150
Capture 'slide2_early'
Start-Sleep -Milliseconds 900
Capture 'slide2_initial_done'
$view.Next()
Start-Sleep -Milliseconds 150
Capture 'slide2_click_early'
Start-Sleep -Milliseconds 1450
Capture 'slide2_click_after_done'
$view.GotoSlide(3)
Start-Sleep -Milliseconds 150
Capture 'slide3_early'
Start-Sleep -Milliseconds 1400
Capture 'slide3_late'
$windowHwnd = $null
try { $windowHwnd = [int64]$window.HWND } catch { }
$view.Exit()
$captureMode = if ($WindowCapture) { 'PrintWindow' } else { 'CopyFromScreen' }
@{deck=$path;started_at_utc=$events[0].at_utc;screen=@{width=$screen.Width;height=$screen.Height};window_hwnd=$windowHwnd;capture_mode=$captureMode;events=$events} |
  ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $OutDir 'playback.json') -Encoding utf8
