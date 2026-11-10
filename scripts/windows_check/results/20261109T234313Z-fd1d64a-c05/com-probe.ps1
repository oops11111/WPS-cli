$ErrorActionPreference = "Stop"
$sw = [Diagnostics.Stopwatch]::StartNew()
try {
  $app = New-Object -ComObject ket.Application
  "created after $($sw.Elapsed.TotalSeconds)s"
  $app.Visible = $false
  "visible set"
  "version=$($app.Version)"
} catch {
  "ERROR: $($_.Exception.GetType().FullName): $($_.Exception.Message)"
} finally {
  try { if ($app) { $app.Quit() } } catch { "quit error: $($_.Exception.Message)" }
}
