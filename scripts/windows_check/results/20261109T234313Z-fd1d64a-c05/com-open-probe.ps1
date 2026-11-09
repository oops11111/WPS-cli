$ErrorActionPreference = "Stop"
$sw = [Diagnostics.Stopwatch]::StartNew()
$path = $args[0]
$app = $null; $wb = $null
try {
  $app = New-Object -ComObject ket.Application
  $app.Visible = $false
  $app.DisplayAlerts = $false
  "app ready $($sw.Elapsed.TotalSeconds)s"
  $wb = $app.Workbooks.Open($path)
  "opened $($sw.Elapsed.TotalSeconds)s; sheets=$($wb.Worksheets.Count)"
  $ws = $wb.Worksheets.Item(1)
  "sheet name=$($ws.Name) used=$($ws.UsedRange.Address())"
  "A1=$($ws.Range('A1').Value2)"
} catch {
  "ERROR at $($sw.Elapsed.TotalSeconds)s: $($_.Exception.GetType().FullName): $($_.Exception.Message)"
} finally {
  if ($wb) { try { $wb.Close($false) } catch { "close error: $($_.Exception.Message)" } }
  if ($app) { try { $app.Quit() } catch { "quit error: $($_.Exception.Message)" } }
}