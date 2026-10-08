param(
  [Parameter(Mandatory = $true)] [string] $Path
)

$ErrorActionPreference = 'Stop'
$resolved = (Resolve-Path -LiteralPath $Path).Path
$before = (Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash
$app = $null
$document = $null
$result = $null
try {
  $app = New-Object -ComObject 'kwps.Application'
  try { $app.Visible = $false } catch { }
  try { $app.DisplayAlerts = 0 } catch { }
  $document = $app.Documents.Open($resolved, $false, $true)
  $paragraphs = @()
  for ($index = 1; $index -le $document.Paragraphs.Count; $index++) {
    $range = $document.Paragraphs.Item($index).Range
    $style = $null
    try { $style = [string] $range.Style.NameLocal }
    catch { try { $style = [string] $range.Style } catch { } }
    $paragraphs += [pscustomobject]@{
      index = $index
      text = ([string] $range.Text).TrimEnd([char]13, [char]7)
      style = $style
      outline_level = [int] $range.ParagraphFormat.OutlineLevel
    }
  }
  $bookmarks = @()
  for ($index = 1; $index -le $document.Bookmarks.Count; $index++) {
    $bookmark = $document.Bookmarks.Item($index)
    $bookmarks += [pscustomobject]@{
      name = [string] $bookmark.Name
      text = [string] $bookmark.Range.Text
    }
  }
  $result = [pscustomobject]@{
    ok = $true
    backend = 'wps-powershell-com'
    read_only = [bool] $document.ReadOnly
    paragraph_count = [int] $document.Paragraphs.Count
    paragraphs = $paragraphs
    bookmark_count = [int] $document.Bookmarks.Count
    bookmarks = $bookmarks
  }
} catch {
  $result = [pscustomobject]@{
    ok = $false
    error = $_.Exception.Message
  }
} finally {
  if ($null -ne $document) {
    try { $document.Close($false) } catch { }
    try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($document) } catch { }
  }
  if ($null -ne $app) {
    try { $app.Quit() } catch { }
    try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) } catch { }
  }
  [GC]::Collect()
  [GC]::WaitForPendingFinalizers()
}
$after = (Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash
$result | Add-Member -NotePropertyName input_path -NotePropertyValue $resolved
$result | Add-Member -NotePropertyName sha256_before -NotePropertyValue $before
$result | Add-Member -NotePropertyName sha256_after -NotePropertyValue $after
$result | Add-Member -NotePropertyName file_unchanged -NotePropertyValue ($before -eq $after)
$result | ConvertTo-Json -Depth 6
if (-not $result.ok -or -not $result.file_unchanged) { exit 2 }
