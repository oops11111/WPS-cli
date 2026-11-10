param([string]$Path,[string]$LogPath)
$ErrorActionPreference = "Stop"
$log = New-Object System.Collections.ArrayList
function L([string]$m) { [void]$log.Add($m); Write-Output $m }
$app = $null; $doc = $null
try {
  $app = New-Object -ComObject kwps.Application
  $app.Visible = $true
  $app.DisplayAlerts = 0
  $doc = $app.Documents.Open($Path)
  try { $app.ActiveWindow.WindowState = -4137 } catch { }
  Start-Sleep -Seconds 2
  L "document opened; showing page setup dialog"
  $dlg = $app.Dialogs.Item(178)
  $dlg.Show(0) | Out-Null
  L "dialog closed"
  Start-Sleep -Seconds 1
} catch {
  L "ERROR: $($_.Exception.GetType().FullName): $($_.Exception.Message)"
} finally {
  if ($doc) { try { $doc.Close(0); L "closed without saving" } catch { L "close failed: $($_.Exception.Message)" } }
  if ($app) { try { $app.Quit(); L "quit" } catch { L "quit failed: $($_.Exception.Message)" } }
  $log | Set-Content -Path $LogPath -Encoding UTF8
}