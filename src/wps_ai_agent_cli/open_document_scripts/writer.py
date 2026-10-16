"""Writer: the attach wrapper, selection read and edit, and exports."""

from __future__ import annotations

from ..wps_script_snippets import ATTACH_RUNNING_INSTANCE
from .common import _SCRIPT_HEAD, _UNICODE_TEXT_FILE

_ATTACHED_WRITER_WRAPPER = (
    _SCRIPT_HEAD
    + ATTACH_RUNNING_INSTANCE
    + """
$app = $null
$doc = $null
try {
  $app = Get-RunningWpsApp @($params.prog_ids)
  if ($null -eq $app) {
    [pscustomobject]@{ ok = $true; status = (Get-WpsMissingStatus @($params.prog_ids)) } | ConvertTo-Json -Depth 5
    exit 0
  }
  $doc = Find-OpenWriterDocument $app $params.path
  if ($null -eq $doc) {
    [pscustomobject]@{ ok = $true; status = 'not_open' } | ConvertTo-Json -Depth 5
    exit 0
  }
  __ACTION_BODY__
} catch {
  [pscustomobject]@{
    ok = $false
    backend = 'powershell-com'
    error_type = $_.Exception.GetType().FullName
    error_message = $_.Exception.Message
    position = $_.InvocationInfo.PositionMessage
  } | ConvertTo-Json -Depth 5
  exit 2
} finally {
  if ($doc -ne $null) { try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc) } catch { } }
  if ($app -ne $null) { try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) } catch { } }
  [GC]::Collect()
  [GC]::WaitForPendingFinalizers()
}
"""
)

_SELECTION_READ_BODY = """
  $window = $doc.ActiveWindow
  if ($null -eq $window) {
    [pscustomobject]@{ ok = $true; status = 'no_window' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $sel = $window.Selection
  $start = [int]$sel.Start
  $end = [int]$sel.End
  $text = [string]$sel.Text
  $paragraphIndex = $null
  try {
    $firstParagraph = $sel.Paragraphs.Item(1).Range.Start
    if ([int]$firstParagraph -le 0) { $paragraphIndex = 1 }
    else { $paragraphIndex = [int]$doc.Range(0, [int]$firstParagraph).Paragraphs.Count + 1 }
  } catch { }
  $pageNumber = $null
  try { $pageNumber = [int]$sel.Information(3) } catch { }
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'writer'
    name = [string]$doc.Name
    saved = [bool]$doc.Saved
    read_only = [bool]$doc.ReadOnly
    start = $start
    end = $end
    selection_text = $text
    paragraph_index = $paragraphIndex
    page_number = $pageNumber
  } | ConvertTo-Json -Depth 5
"""

_SELECTION_REPLACE_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ([bool]$doc.ReadOnly) {
    [pscustomobject]@{ ok = $true; status = 'read_only' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $start = [int]$params.expected_start
  $end = [int]$params.expected_end
  $range = $doc.Range($start, $end)
  if (([string]$range.Text) -cne [string]$params.expected_text) {
    [pscustomobject]@{ ok = $true; status = 'selection_changed'; current_text = [string]$range.Text } | ConvertTo-Json -Depth 5
    exit 0
  }
  $replacement = [string]$params.text
  # Snapshot uniform character formatting before Text= (mixed runs report wdUndefined=9999999).
  $wdUndefined = 9999999
  $snapName = $null; $snapSize = $null; $snapBold = $null; $snapItalic = $null; $snapUnderline = $null; $snapColor = $null
  try {
    $f = $range.Font
    try { $snapName = [string]$f.Name } catch { }
    try { $snapSize = $f.Size } catch { }
    try { $snapBold = $f.Bold } catch { }
    try { $snapItalic = $f.Italic } catch { }
    try { $snapUnderline = $f.Underline } catch { }
    try { $snapColor = $f.Color } catch { }
  } catch { }
  $range.Text = $replacement
  $newRange = $doc.Range($start, $start + $replacement.Length)
  $formattingApplied = $false
  try {
    $nf = $newRange.Font
    if (-not [string]::IsNullOrEmpty($snapName)) {
      try { $nf.Name = $snapName; $formattingApplied = $true } catch { }
    }
    if ($null -ne $snapSize) {
      try {
        $sz = [double]$snapSize
        if ($sz -gt 0 -and $sz -lt 1000) { $nf.Size = $sz; $formattingApplied = $true }
      } catch { }
    }
    if ($null -ne $snapBold) {
      try { if ([int]$snapBold -ne $wdUndefined) { $nf.Bold = $snapBold; $formattingApplied = $true } } catch { }
    }
    if ($null -ne $snapItalic) {
      try { if ([int]$snapItalic -ne $wdUndefined) { $nf.Italic = $snapItalic; $formattingApplied = $true } } catch { }
    }
    if ($null -ne $snapUnderline) {
      try { if ([int]$snapUnderline -ne $wdUndefined) { $nf.Underline = $snapUnderline; $formattingApplied = $true } } catch { }
    }
    if ($null -ne $snapColor) {
      try { $nf.Color = $snapColor; $formattingApplied = $true } catch { }
    }
  } catch { }
  $doc.Save()
  $readBack = [string]$doc.Range($start, $start + $replacement.Length).Text
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'writer'
    start = $start
    end = $end
    read_back_text = $readBack
    formatting_mode = 'uniform_character'
    formatting_preserved = [bool]$formattingApplied
  } | ConvertTo-Json -Depth 5
"""

_SELECTION_INSERT_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ([bool]$doc.ReadOnly) {
    [pscustomobject]@{ ok = $true; status = 'read_only' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $window = $doc.ActiveWindow
  if ($null -eq $window) {
    [pscustomobject]@{ ok = $true; status = 'no_window' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $sel = $window.Selection
  $start = [int]$sel.Start
  $end = [int]$sel.End
  if ($start -ne $end) {
    [pscustomobject]@{
      ok = $true
      status = 'not_collapsed'
      start = $start
      end = $end
    } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ($start -ne [int]$params.expected_start) {
    [pscustomobject]@{
      ok = $true
      status = 'selection_changed'
      current_start = $start
    } | ConvertTo-Json -Depth 5
    exit 0
  }
  $insert = [string]$params.text
  $range = $doc.Range($start, $start)
  $range.Text = $insert
  $doc.Save()
  $readBack = [string]$doc.Range($start, $start + $insert.Length).Text
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'writer'
    start = $start
    end = $start + $insert.Length
    read_back_text = $readBack
  } | ConvertTo-Json -Depth 5
"""

_SELECTION_DELETE_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ([bool]$doc.ReadOnly) {
    [pscustomobject]@{ ok = $true; status = 'read_only' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $start = [int]$params.expected_start
  $end = [int]$params.expected_end
  $range = $doc.Range($start, $end)
  if (([string]$range.Text) -cne [string]$params.expected_text) {
    [pscustomobject]@{ ok = $true; status = 'selection_changed'; current_text = [string]$range.Text } | ConvertTo-Json -Depth 5
    exit 0
  }
  $range.Text = ''
  $doc.Save()
  $probeLen = [int]$params.expected_text.Length
  $probeEnd = $start + $probeLen
  try {
    $contentEnd = [int]$doc.Content.End
    if ($probeEnd -gt $contentEnd) { $probeEnd = $contentEnd }
  } catch { }
  $probe = ''
  if ($probeEnd -gt $start) {
    try { $probe = [string]$doc.Range($start, $probeEnd).Text } catch { }
  }
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'writer'
    start = $start
    end = $start
    deleted_text = [string]$params.expected_text
    read_back_text = $probe
  } | ConvertTo-Json -Depth 5
"""

_EXPORT_HTML_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $copy = $null
  $method = 'SaveAs2'
  try {
    $copy = $app.Documents.Add([string]$doc.FullName)
    try { $copy.SaveAs2([string]$params.output, 10) }
    catch { $method = 'SaveAs'; $copy.SaveAs([string]$params.output, 10) }
  } finally {
    if ($copy -ne $null) {
      try { $copy.Close($false) } catch { }
      try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($copy) } catch { }
    }
  }
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'writer'
    export_method = $method
    source_still_open = [bool]($null -ne (Find-OpenWriterDocument $app $params.path))
  } | ConvertTo-Json -Depth 5
"""

_EXPORT_PDF_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  try { $app.DisplayAlerts = $false } catch { }
  $copy = $null
  $method = 'ExportAsFixedFormat'
  try {
    $copy = $app.Documents.Add([string]$doc.FullName)
    try {
      $copy.ExportAsFixedFormat([string]$params.output, 17)
    } catch {
      $method = 'SaveAs'
      $copy.SaveAs([string]$params.output, 17)
    }
  } finally {
    if ($copy -ne $null) {
      try { $copy.Close($false) } catch { }
      try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($copy) } catch { }
    }
  }
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'writer'
    export_method = $method
    source_still_open = [bool]($null -ne (Find-OpenWriterDocument $app $params.path))
  } | ConvertTo-Json -Depth 5
"""

_EXPORT_COPY_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  try { $app.DisplayAlerts = $false } catch { }
  $method = 'SaveCopyAs'
  $copy = $null
  try {
    $doc.SaveCopyAs([string]$params.output)
  } catch {
    $method = 'DocumentsAddSaveAs'
    $copy = $app.Documents.Add([string]$doc.FullName)
    $copy.SaveAs([string]$params.output)
  } finally {
    if ($copy -ne $null) {
      try { $copy.Close($false) } catch { }
      try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($copy) } catch { }
    }
  }
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'writer'
    export_method = $method
    source_still_open = [bool]($null -ne (Find-OpenWriterDocument $app $params.path))
  } | ConvertTo-Json -Depth 5
"""

_EXPORT_TEXT_BODY = (
    _UNICODE_TEXT_FILE
    + """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  try { $app.DisplayAlerts = $false } catch { }
  $copy = $null
  $method = 'SaveAsUtf8Text'
  try {
    $copy = $app.Documents.Add([string]$doc.FullName)
    $missing = [Type]::Missing
    try {
      # Encoding 65001 (UTF-8) is SaveAs2's twelfth argument; without it WPS 12.8 wrote the code page (P9-003).
      $copy.SaveAs2([string]$params.output, 7, $missing, $missing, $missing, $missing, $missing, $missing, $missing, $missing, $missing, 65001)
    } catch {
      $method = 'SaveAsUnicodeText'
      try {
        $copy.SaveAs2([string]$params.output, 7)
      } catch {
        try {
          $copy.SaveAs([string]$params.output, 7)
        } catch {
          $method = 'SaveAsText'
          try { $copy.SaveAs2([string]$params.output, 2) }
          catch { $copy.SaveAs([string]$params.output, 2) }
        }
      }
    }
  } finally {
    if ($copy -ne $null) {
      try { $copy.Close($false) } catch { }
      try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($copy) } catch { }
    }
  }
  # The document's text as plain text: Word ends a table cell with CR + BEL, a line with VT, a page with FF.
  $finish = Complete-WpsUnicodeTextFile ([string]$params.output) {
    $text = ([string]$doc.Content.Text).Replace("`r`a", "`t")
    $text = $text -replace '[\\x0B\\x0C]', "`r"
    $text = $text -replace '[\\x00-\\x08\\x0E-\\x1F]', ''
    $text -replace '\\r(?!\\n)', "`r`n"
  }
  if ($finish -ne 'unicode') { $method = $method + '+' + $finish }
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'writer'
    export_method = $method
    source_still_open = [bool]($null -ne (Find-OpenWriterDocument $app $params.path))
  } | ConvertTo-Json -Depth 5
"""
)
