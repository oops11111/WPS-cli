"""PowerShell scripts that open_documents runs against documents already open in WPS.

Each wrapper attaches to the running WPS instance and runs one body. The bodies read their parameters from
__PARAMS_JSON__, which open_documents._render fills in.
"""

from __future__ import annotations

from .wps_script_snippets import ATTACH_RUNNING_INSTANCE

MAX_SPREADSHEET_SELECTION_SAMPLE_CELLS = 100

_SCRIPT_HEAD = """
$ErrorActionPreference = 'Stop'
$params = @'
__PARAMS_JSON__
'@ | ConvertFrom-Json
"""

_ATTACHED_WRITER_WRAPPER = (
    _SCRIPT_HEAD
    + ATTACH_RUNNING_INSTANCE
    + """
$app = $null
$doc = $null
try {
  $app = Get-RunningWpsApp @($params.prog_ids)
  if ($null -eq $app) {
    [pscustomobject]@{ ok = $true; status = 'no_instance' } | ConvertTo-Json -Depth 5
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

_LIST_SCRIPT = (
    _SCRIPT_HEAD
    + ATTACH_RUNNING_INSTANCE
    + """
function Get-Safe([scriptblock]$block) { try { return & $block } catch { return $null } }
$instances = @()
foreach ($spec in $params.components) {
  $app = Get-RunningWpsApp @($spec.prog_ids)
  if ($null -eq $app) { continue }
  try {
    $collection = $app.($spec.collection)
    $activeFullName = Get-Safe { [string]$app.($spec.active).FullName }
    $documents = @()
    $count = [int]$collection.Count
    for ($i = 1; $i -le $count; $i++) {
      $item = $collection.Item($i)
      $fullName = Get-Safe { [string]$item.FullName }
      $documents += [pscustomobject]@{
        name = Get-Safe { [string]$item.Name }
        full_name = $fullName
        saved = Get-Safe { [bool]$item.Saved }
        read_only = Get-Safe { [bool]$item.ReadOnly }
        active = [bool]($null -ne $activeFullName -and $fullName -eq $activeFullName)
      }
    }
    $instances += [pscustomobject]@{
      component = $spec.component
      version = Get-Safe { [string]$app.Version }
      documents = $documents
    }
  } finally {
    try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) } catch { }
  }
}
[pscustomobject]@{ ok = $true; backend = 'powershell-com'; instances = $instances } | ConvertTo-Json -Depth 6
"""
)

_SAVE_AS_UNTITLED_SCRIPT = (
    _SCRIPT_HEAD
    + ATTACH_RUNNING_INSTANCE
    + """
$app = $null
$doc = $null
try {
  $app = Get-RunningWpsApp @($params.prog_ids)
  if ($null -eq $app) {
    [pscustomobject]@{ ok = $true; status = 'no_instance' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $collection = $app.($params.collection)
  $untitled = New-Object System.Collections.Generic.List[object]
  $pathed = New-Object System.Collections.Generic.List[object]
  $count = [int]$collection.Count
  for ($i = 1; $i -le $count; $i++) {
    $item = $collection.Item($i)
    $itemName = ''
    try { $itemName = [string]$item.Name } catch { continue }
    if (-not [string]::Equals($itemName, [string]$params.name, [System.StringComparison]::OrdinalIgnoreCase)) {
      continue
    }
    $fullName = ''
    try { $fullName = [string]$item.FullName } catch { $fullName = '' }
    $onDisk = $false
    if (-not [string]::IsNullOrEmpty($fullName)) {
      try {
        $candidatePath = [System.IO.Path]::GetFullPath($fullName)
        $onDisk = [System.IO.File]::Exists($candidatePath)
      } catch { $onDisk = $false }
    }
    if ($onDisk) { [void]$pathed.Add($item) } else { [void]$untitled.Add($item) }
  }
  if ([int]$untitled.Count -eq 0 -and [int]$pathed.Count -ge 1) {
    [pscustomobject]@{
      ok = $true
      status = 'already_pathed'
      match_count = [int]$pathed.Count
      name = [string]$params.name
    } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ([int]$untitled.Count -eq 0) {
    [pscustomobject]@{ ok = $true; status = 'not_found'; name = [string]$params.name } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ([int]$untitled.Count -gt 1) {
    [pscustomobject]@{
      ok = $true
      status = 'ambiguous'
      match_count = [int]$untitled.Count
      name = [string]$params.name
    } | ConvertTo-Json -Depth 5
    exit 0
  }
  $doc = $untitled[0]
  if ([bool]$doc.ReadOnly) {
    [pscustomobject]@{
      ok = $true
      status = 'read_only'
      name = [string]$doc.Name
      saved = [bool]$doc.Saved
      read_only = $true
    } | ConvertTo-Json -Depth 5
    exit 0
  }
  if (-not [bool]$params.do_save) {
    [pscustomobject]@{
      ok = $true
      status = 'ok'
      backend = 'powershell-com'
      component = [string]$params.component
      name = [string]$doc.Name
      saved = [bool]$doc.Saved
      read_only = $false
      would_modify = $true
      wrote = $false
      source_still_open = $true
    } | ConvertTo-Json -Depth 5
    exit 0
  }
  try { $app.DisplayAlerts = $false } catch { }
  $output = [string]$params.output
  $component = [string]$params.component
  if ($component -eq 'spreadsheets') {
    try { $doc.SaveAs($output, 51) }
    catch { $doc.SaveAs($output) }
  } elseif ($component -eq 'presentation') {
    try { $doc.SaveAs($output, 24) }
    catch { $doc.SaveAs($output) }
  } else {
    try { $doc.SaveAs2($output) }
    catch {
      try { $doc.SaveAs($output) }
      catch { $doc.SaveAs($output, 16) }
    }
  }
  $fullAfter = ''
  try { $fullAfter = [System.IO.Path]::GetFullPath([string]$doc.FullName) } catch { $fullAfter = [string]$doc.FullName }
  $target = [System.IO.Path]::GetFullPath($output)
  $pathMatched = [string]::Equals($fullAfter, $target, [System.StringComparison]::OrdinalIgnoreCase)
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = $component
    name = [string]$doc.Name
    full_name = $fullAfter
    saved = [bool]$doc.Saved
    read_only = [bool]$doc.ReadOnly
    wrote = $true
    source_still_open = $true
    path_matched = [bool]$pathMatched
    output_exists = [bool]([System.IO.File]::Exists($target))
  } | ConvertTo-Json -Depth 5
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

_DOCUMENT_SAVE_BODY = """
  if ([bool]$doc.ReadOnly) {
    [pscustomobject]@{ ok = $true; status = 'read_only'; saved = [bool]$doc.Saved; read_only = $true } | ConvertTo-Json -Depth 5
    exit 0
  }
  $wasSaved = [bool]$doc.Saved
  if (-not [bool]$params.do_save) {
    [pscustomobject]@{
      ok = $true
      status = 'ok'
      backend = 'powershell-com'
      saved = $wasSaved
      read_only = $false
      wrote = $false
      source_still_open = $true
    } | ConvertTo-Json -Depth 5
    exit 0
  }
  if (-not $wasSaved) {
    $doc.Save()
  }
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    saved = [bool]$doc.Saved
    read_only = $false
    wrote = (-not $wasSaved)
    source_still_open = $true
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

_ATTACHED_PRESENTATION_WRAPPER = (
    _SCRIPT_HEAD
    + ATTACH_RUNNING_INSTANCE
    + """
$app = $null
$doc = $null
try {
  $app = Get-RunningWpsApp @($params.prog_ids)
  if ($null -eq $app) {
    [pscustomobject]@{ ok = $true; status = 'no_instance' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $doc = Find-OpenPresentation $app $params.path
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

_PRESENTATION_EXPORT_HTML_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $method = 'SaveCopyAsHtml'
  try {
    $doc.SaveCopyAs([string]$params.output, 12)
  } catch {
    $method = 'SaveCopyAsHtmlDual'
    $doc.SaveCopyAs([string]$params.output, 23)
  }
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'presentation'
    export_method = $method
    source_still_open = [bool]($null -ne (Find-OpenPresentation $app $params.path))
  } | ConvertTo-Json -Depth 5
"""

_SPREADSHEET_EXPORT_HTML_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  # WPS Spreadsheets SaveCopyAs accepts only a path (no FileFormat). Export via a
  # temporary copy + SaveAs so the open source is never renamed or closed.
  $tempCopy = [System.IO.Path]::Combine(
    [System.IO.Path]::GetTempPath(),
    ('wps-agent-html-' + [guid]::NewGuid().ToString('N') + '.xlsx')
  )
  $copy = $null
  $method = 'SaveCopyAsThenSaveAsHtml'
  try {
    $doc.SaveCopyAs([string]$tempCopy)
    $copy = $app.Workbooks.Open([string]$tempCopy)
    try {
      $copy.SaveAs([string]$params.output, 44)
    } catch {
      $method = 'SaveCopyAsThenSaveAsWebArchive'
      $copy.SaveAs([string]$params.output, 45)
    }
  } finally {
    if ($copy -ne $null) {
      try { $copy.Close($false) } catch { }
      try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($copy) } catch { }
    }
    try {
      if (Test-Path -LiteralPath $tempCopy) { Remove-Item -LiteralPath $tempCopy -Force -ErrorAction SilentlyContinue }
    } catch { }
  }
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'spreadsheets'
    export_method = $method
    source_still_open = [bool]($null -ne (Find-OpenWorkbook $app $params.path))
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

_PRESENTATION_EXPORT_PDF_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  try { $app.DisplayAlerts = $false } catch { }
  $method = 'ExportAsFixedFormat'
  $exported = $false
  try {
    $doc.ExportAsFixedFormat([string]$params.output, 2)
    $exported = $true
  } catch { }
  if (-not $exported) {
    $tempCopy = [System.IO.Path]::Combine(
      [System.IO.Path]::GetTempPath(),
      ('wps-agent-pdf-' + [guid]::NewGuid().ToString('N') + '.pptx')
    )
    $copy = $null
    $method = 'SaveCopyAsThenSaveAsPdf'
    try {
      $doc.SaveCopyAs([string]$tempCopy)
      $copy = $app.Presentations.Open([string]$tempCopy, $false, $false, $false)
      $copy.SaveAs([string]$params.output, 32)
    } finally {
      if ($copy -ne $null) {
        try { $copy.Close() } catch { }
        try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($copy) } catch { }
      }
      try {
        if (Test-Path -LiteralPath $tempCopy) { Remove-Item -LiteralPath $tempCopy -Force -ErrorAction SilentlyContinue }
      } catch { }
    }
  }
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'presentation'
    export_method = $method
    source_still_open = [bool]($null -ne (Find-OpenPresentation $app $params.path))
  } | ConvertTo-Json -Depth 5
"""

_SPREADSHEET_EXPORT_PDF_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  try { $app.DisplayAlerts = $false } catch { }
  $method = 'ExportAsFixedFormat'
  try {
    $doc.ExportAsFixedFormat(0, [string]$params.output)
  } catch {
    $method = 'ExportAsFixedFormatAlt'
    $doc.ExportAsFixedFormat([string]$params.output, 0)
  }
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'spreadsheets'
    export_method = $method
    source_still_open = [bool]($null -ne (Find-OpenWorkbook $app $params.path))
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

_PRESENTATION_EXPORT_COPY_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  try { $app.DisplayAlerts = $false } catch { }
  $doc.SaveCopyAs([string]$params.output)
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'presentation'
    export_method = 'SaveCopyAs'
    source_still_open = [bool]($null -ne (Find-OpenPresentation $app $params.path))
  } | ConvertTo-Json -Depth 5
"""

_SPREADSHEET_EXPORT_COPY_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  try { $app.DisplayAlerts = $false } catch { }
  $doc.SaveCopyAs([string]$params.output)
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'spreadsheets'
    export_method = 'SaveCopyAs'
    source_still_open = [bool]($null -ne (Find-OpenWorkbook $app $params.path))
  } | ConvertTo-Json -Depth 5
"""

_EXPORT_TEXT_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  try { $app.DisplayAlerts = $false } catch { }
  $copy = $null
  $method = 'SaveAsUnicodeText'
  try {
    $copy = $app.Documents.Add([string]$doc.FullName)
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

_PRESENTATION_EXPORT_TEXT_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  try { $app.DisplayAlerts = $false } catch { }
  $parts = New-Object System.Collections.Generic.List[string]
  $slideCount = [int]$doc.Slides.Count
  for ($s = 1; $s -le $slideCount; $s++) {
    $slide = $doc.Slides.Item($s)
    $shapeCount = [int]$slide.Shapes.Count
    for ($i = 1; $i -le $shapeCount; $i++) {
      $shape = $slide.Shapes.Item($i)
      try {
        $hasFrame = $false
        try { $hasFrame = [bool]$shape.HasTextFrame } catch { }
        if (-not $hasFrame) { continue }
        $frame = $shape.TextFrame
        $hasText = $false
        try { $hasText = [bool]$frame.HasText } catch { $hasText = $true }
        if (-not $hasText) { continue }
        $text = [string]$frame.TextRange.Text
        if (-not [string]::IsNullOrWhiteSpace($text)) {
          $parts.Add(($text -replace "`r", '').TrimEnd())
        }
      } catch { }
    }
    if ($s -lt $slideCount) { $parts.Add('') }
  }
  $content = [string]::Join([Environment]::NewLine, $parts)
  [System.IO.File]::WriteAllText([string]$params.output, $content, [System.Text.UTF8Encoding]::new($false))
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'presentation'
    export_method = 'ExtractShapeText'
    source_still_open = [bool]($null -ne (Find-OpenPresentation $app $params.path))
  } | ConvertTo-Json -Depth 5
"""

_SPREADSHEET_EXPORT_TEXT_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  try { $app.DisplayAlerts = $false } catch { }
  $tempCopy = [System.IO.Path]::Combine(
    [System.IO.Path]::GetTempPath(),
    ('wps-agent-txt-' + [guid]::NewGuid().ToString('N') + '.xlsx')
  )
  $copy = $null
  $method = 'SaveCopyAsThenUnicodeText'
  try {
    $doc.SaveCopyAs([string]$tempCopy)
    $copy = $app.Workbooks.Open([string]$tempCopy)
    try {
      $copy.SaveAs([string]$params.output, 42)
    } catch {
      $method = 'SaveCopyAsThenWindowsText'
      $copy.SaveAs([string]$params.output, 20)
    }
  } finally {
    if ($copy -ne $null) {
      try { $copy.Close($false) } catch { }
      try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($copy) } catch { }
    }
    try {
      if (Test-Path -LiteralPath $tempCopy) { Remove-Item -LiteralPath $tempCopy -Force -ErrorAction SilentlyContinue }
    } catch { }
  }
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'spreadsheets'
    export_method = $method
    source_still_open = [bool]($null -ne (Find-OpenWorkbook $app $params.path))
  } | ConvertTo-Json -Depth 5
"""

_PRESENTATION_SELECTION_READ_BODY = """
  $window = $null
  try {
    if ([int]$doc.Windows.Count -ge 1) { $window = $doc.Windows.Item(1) }
  } catch { }
  if ($null -eq $window) {
    try {
      $active = $app.ActivePresentation
      if ($null -ne $active -and [string]::Equals(
        [System.IO.Path]::GetFullPath([string]$active.FullName),
        [System.IO.Path]::GetFullPath([string]$params.path),
        [System.StringComparison]::OrdinalIgnoreCase
      )) { $window = $app.ActiveWindow }
    } catch { }
  }
  if ($null -eq $window) {
    [pscustomobject]@{ ok = $true; status = 'no_window' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $sel = $window.Selection
  $selType = 0
  try { $selType = [int]$sel.Type } catch { }
  $kind = switch ($selType) {
    0 { 'none' }
    1 { 'slides' }
    2 { 'shapes' }
    3 { 'text' }
    default { 'unknown' }
  }
  $text = ''
  $slideIndex = $null
  $shapeName = $null
  $shapeCount = 0
  $textStart = $null
  $textLength = $null
  try {
    if ($selType -eq 3) {
      $tr = $sel.TextRange
      $text = [string]$tr.Text
      try { $textStart = [int]$tr.Start } catch { }
      try { $textLength = [int]$tr.Length } catch { }
      try { $shapeName = [string]$sel.ShapeRange.Item(1).Name } catch { }
      try { $slideIndex = [int]$sel.SlideRange.SlideIndex } catch { }
    } elseif ($selType -eq 2) {
      $shapeCount = [int]$sel.ShapeRange.Count
      try { $shapeName = [string]$sel.ShapeRange.Item(1).Name } catch { }
      try { $text = [string]$sel.ShapeRange.Item(1).TextFrame.TextRange.Text } catch { }
      try { $slideIndex = [int]$sel.SlideRange.SlideIndex } catch { }
    } elseif ($selType -eq 1) {
      try { $slideIndex = [int]$sel.SlideRange.Item(1).SlideIndex } catch { }
    }
  } catch { }
  $collapsed = [bool]($selType -eq 3 -and $null -ne $textLength -and [int]$textLength -eq 0)
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'presentation'
    saved = [bool]$doc.Saved
    read_only = [bool]$doc.ReadOnly
    selection_type = $selType
    selection_kind = $kind
    selection_text = $text
    text_range_start = $textStart
    text_range_length = $textLength
    collapsed = $collapsed
    slide_index = $slideIndex
    shape_name = $shapeName
    shape_count = $shapeCount
  } | ConvertTo-Json -Depth 5
"""

_PRESENTATION_SELECTION_REPLACE_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ([bool]$doc.ReadOnly) {
    [pscustomobject]@{ ok = $true; status = 'read_only' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $window = $null
  try {
    if ([int]$doc.Windows.Count -ge 1) { $window = $doc.Windows.Item(1) }
  } catch { }
  if ($null -eq $window) {
    try {
      $active = $app.ActivePresentation
      if ($null -ne $active -and [string]::Equals(
        [System.IO.Path]::GetFullPath([string]$active.FullName),
        [System.IO.Path]::GetFullPath([string]$params.path),
        [System.StringComparison]::OrdinalIgnoreCase
      )) { $window = $app.ActiveWindow }
    } catch { }
  }
  if ($null -eq $window) {
    [pscustomobject]@{ ok = $true; status = 'no_window' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $sel = $window.Selection
  $selType = 0
  try { $selType = [int]$sel.Type } catch { }
  if ($selType -ne 3) {
    [pscustomobject]@{ ok = $true; status = 'not_text_selection'; selection_type = $selType } | ConvertTo-Json -Depth 5
    exit 0
  }
  $tr = $sel.TextRange
  $before = [string]$tr.Text
  if ($before -cne [string]$params.expected_text) {
    [pscustomobject]@{ ok = $true; status = 'selection_changed'; current_text = $before } | ConvertTo-Json -Depth 5
    exit 0
  }
  $replacement = [string]$params.text
  $shape = $null
  try { $shape = $sel.ShapeRange.Item(1) } catch { }
  $wdUndefined = 9999999
  $snapName = $null; $snapSize = $null; $snapBold = $null; $snapItalic = $null; $snapUnderline = $null; $snapColor = $null
  try {
    $f = $tr.Font
    try { $snapName = [string]$f.Name } catch { }
    try { $snapSize = $f.Size } catch { }
    try { $snapBold = $f.Bold } catch { }
    try { $snapItalic = $f.Italic } catch { }
    try { $snapUnderline = $f.Underline } catch { }
    try { $snapColor = $f.Color.RGB } catch {
      try { $snapColor = $f.Color } catch { }
    }
  } catch { }
  $tr.Text = $replacement
  # WPS may invalidate the original TextRange/selection after assignment or Save.
  $readBack = ''
  $formattingApplied = $false
  try {
    $tr2 = $null
    try { $tr2 = $sel.TextRange } catch { }
    if ($null -eq $tr2 -and $null -ne $shape) {
      try { $tr2 = $shape.TextFrame.TextRange } catch { }
    }
    if ($null -eq $tr2) { $tr2 = $tr }
    try { $readBack = [string]$tr2.Text } catch { }
    try {
      $nf = $tr2.Font
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
        try { $nf.Color.RGB = $snapColor; $formattingApplied = $true }
        catch { try { $nf.Color = $snapColor; $formattingApplied = $true } catch { } }
      }
    } catch { }
  } catch { }
  if ([string]::IsNullOrEmpty($readBack)) {
    try { $readBack = [string]$tr.Text } catch { }
  }
  if ([string]::IsNullOrEmpty($readBack)) {
    try { $readBack = [string]$sel.TextRange.Text } catch { }
  }
  if ([string]::IsNullOrEmpty($readBack) -and $null -ne $shape) {
    try { $readBack = [string]$shape.TextFrame.TextRange.Text } catch { }
  }
  $doc.Save()
  if ([string]::IsNullOrEmpty($readBack)) {
    try { $readBack = [string]$window.Selection.TextRange.Text } catch { }
  }
  if ([string]::IsNullOrEmpty($readBack) -and $null -ne $shape) {
    try { $readBack = [string]$shape.TextFrame.TextRange.Text } catch { }
  }
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'presentation'
    read_back_text = $readBack
    formatting_mode = 'uniform_character'
    formatting_preserved = [bool]$formattingApplied
  } | ConvertTo-Json -Depth 5
"""

_PRESENTATION_SELECTION_INSERT_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ([bool]$doc.ReadOnly) {
    [pscustomobject]@{ ok = $true; status = 'read_only' } | ConvertTo-Json -Depth 5
    exit 0
  }
  try { $app.DisplayAlerts = $false } catch { }
  $window = $null
  try {
    if ([int]$doc.Windows.Count -ge 1) { $window = $doc.Windows.Item(1) }
  } catch { }
  if ($null -eq $window) {
    try {
      $active = $app.ActivePresentation
      if ($null -ne $active -and [string]::Equals(
        [System.IO.Path]::GetFullPath([string]$active.FullName),
        [System.IO.Path]::GetFullPath([string]$params.path),
        [System.StringComparison]::OrdinalIgnoreCase
      )) { $window = $app.ActiveWindow }
    } catch { }
  }
  if ($null -eq $window) {
    [pscustomobject]@{ ok = $true; status = 'no_window' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $sel = $window.Selection
  $selType = 0
  try { $selType = [int]$sel.Type } catch { }
  if ($selType -ne 3) {
    [pscustomobject]@{ ok = $true; status = 'not_text_selection'; selection_type = $selType } | ConvertTo-Json -Depth 5
    exit 0
  }
  $tr = $sel.TextRange
  $length = 0
  try { $length = [int]$tr.Length } catch { }
  if ($length -ne 0) {
    [pscustomobject]@{ ok = $true; status = 'not_collapsed'; text_range_length = $length } | ConvertTo-Json -Depth 5
    exit 0
  }
  $start = [int]$tr.Start
  if ($start -ne [int]$params.expected_start) {
    [pscustomobject]@{ ok = $true; status = 'selection_changed'; current_start = $start } | ConvertTo-Json -Depth 5
    exit 0
  }
  $shape = $null
  try { $shape = $sel.ShapeRange.Item(1) } catch { }
  $insert = [string]$params.text
  # Collapsed TextRange.Text assignment inserts at the caret on WPS builds where Insert-After hangs.
  $tr.Text = $insert
  $doc.Save()
  # TextRange.Start is 1-based in Presentation; .NET Substring is 0-based.
  $zeroStart = [Math]::Max(0, $start - 1)
  $readBack = ''
  if ($null -ne $shape) {
    try {
      $full = [string]$shape.TextFrame.TextRange.Text
      if ($full -eq $insert) { $readBack = $full }
      elseif ($full.Length -ge ($zeroStart + $insert.Length)) {
        $readBack = $full.Substring($zeroStart, $insert.Length)
      }
    } catch { }
    if ([string]::IsNullOrEmpty($readBack)) {
      try { $readBack = [string]$shape.TextFrame.TextRange.Characters($start, $insert.Length).Text } catch { }
    }
  }
  if ([string]::IsNullOrEmpty($readBack)) {
    try { $readBack = [string]$window.Selection.TextRange.Text } catch { }
  }
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'presentation'
    start = $start
    end = $start + $insert.Length
    read_back_text = $readBack
  } | ConvertTo-Json -Depth 5
"""

_PRESENTATION_SELECTION_DELETE_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ([bool]$doc.ReadOnly) {
    [pscustomobject]@{ ok = $true; status = 'read_only' } | ConvertTo-Json -Depth 5
    exit 0
  }
  try { $app.DisplayAlerts = $false } catch { }
  $window = $null
  try {
    if ([int]$doc.Windows.Count -ge 1) { $window = $doc.Windows.Item(1) }
  } catch { }
  if ($null -eq $window) {
    try {
      $active = $app.ActivePresentation
      if ($null -ne $active -and [string]::Equals(
        [System.IO.Path]::GetFullPath([string]$active.FullName),
        [System.IO.Path]::GetFullPath([string]$params.path),
        [System.StringComparison]::OrdinalIgnoreCase
      )) { $window = $app.ActiveWindow }
    } catch { }
  }
  if ($null -eq $window) {
    [pscustomobject]@{ ok = $true; status = 'no_window' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $sel = $window.Selection
  $selType = 0
  try { $selType = [int]$sel.Type } catch { }
  if ($selType -ne 3) {
    [pscustomobject]@{ ok = $true; status = 'not_text_selection'; selection_type = $selType } | ConvertTo-Json -Depth 5
    exit 0
  }
  $tr = $sel.TextRange
  $before = [string]$tr.Text
  if ($before -cne [string]$params.expected_text) {
    [pscustomobject]@{ ok = $true; status = 'selection_changed'; current_text = $before } | ConvertTo-Json -Depth 5
    exit 0
  }
  $shape = $null
  try { $shape = $sel.ShapeRange.Item(1) } catch { }
  $expected = [string]$params.expected_text
  $tr.Text = ''
  $doc.Save()
  $probe = ''
  if ($null -ne $shape) {
    try {
      $full = [string]$shape.TextFrame.TextRange.Text
      # If the whole shape still equals the deleted text, the delete did not stick.
      if ($full -ceq $expected) { $probe = $full }
    } catch { }
  }
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'presentation'
    deleted_text = $expected
    read_back_text = $probe
  } | ConvertTo-Json -Depth 5
"""

_ATTACHED_SPREADSHEET_WRAPPER = (
    _SCRIPT_HEAD
    + ATTACH_RUNNING_INSTANCE
    + """
$app = $null
$doc = $null
try {
  $app = Get-RunningWpsApp @($params.prog_ids)
  if ($null -eq $app) {
    [pscustomobject]@{ ok = $true; status = 'no_instance' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $doc = Find-OpenWorkbook $app $params.path
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

_SPREADSHEET_SELECTION_READ_BODY = """
  $window = $null
  try {
    if ([int]$doc.Windows.Count -ge 1) { $window = $doc.Windows.Item(1) }
  } catch { }
  if ($null -eq $window) {
    try {
      $active = $app.ActiveWorkbook
      if ($null -ne $active -and [string]::Equals(
        [System.IO.Path]::GetFullPath([string]$active.FullName),
        [System.IO.Path]::GetFullPath([string]$params.path),
        [System.StringComparison]::OrdinalIgnoreCase
      )) { $window = $app.ActiveWindow }
    } catch { }
  }
  if ($null -eq $window) {
    [pscustomobject]@{ ok = $true; status = 'no_window' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $sel = $null
  try { $sel = $window.Selection } catch { }
  if ($null -eq $sel) {
    try { $sel = $window.RangeSelection } catch { }
  }
  $address = $null
  $sheetName = $null
  $cellCount = 0
  $areaCount = 0
  $kind = 'unknown'
  $text = ''
  $formula = $null
  $sampleTruncated = $false
  $objectKind = $null
  $objectName = $null
  $hasTextFrame = $false
  $hasChartTitle = $false
  $hasAxisTitle = $false
  $hasSeriesValues = $false
  $seriesName = $null
  $shape = $null
  try {
    $address = [string]$sel.Address($true, $true)
    try { $sheetName = [string]$sel.Worksheet.Name } catch { }
    try { $areaCount = [int]$sel.Areas.Count } catch { $areaCount = 1 }
    try { $cellCount = [int]$sel.Cells.Count } catch { $cellCount = 0 }
    if ($cellCount -le 0) { $kind = 'none' }
    elseif ($areaCount -gt 1) { $kind = 'multi_area' }
    elseif ($cellCount -eq 1) { $kind = 'cell' }
    else { $kind = 'range' }
    $maxSample = __MAX_SAMPLE_CELLS__
    if ($cellCount -eq 1) {
      try { $text = [string]$sel.Text } catch { $text = '' }
      try {
        $formulaValue = [string]$sel.Formula
        if ($formulaValue.StartsWith('=')) { $formula = $formulaValue }
      } catch { }
    } else {
      $parts = New-Object System.Collections.Generic.List[string]
      $sampled = 0
      foreach ($area in $sel.Areas) {
        foreach ($cell in $area.Cells) {
          if ($sampled -ge $maxSample) { $sampleTruncated = $true; break }
          try { $parts.Add([string]$cell.Text) } catch { $parts.Add('') }
          $sampled++
        }
        if ($sampleTruncated) { break }
      }
      $text = [string]::Join("`t", $parts)
      if ($cellCount -gt $maxSample) { $sampleTruncated = $true }
    }
  } catch {
    $kind = 'non_range'
    $address = $null
    $cellCount = 0
    $areaCount = 0
    $text = ''
  }
  if ($kind -eq 'non_range' -or $kind -eq 'unknown') {
    try {
      $shapeRange = $sel.ShapeRange
      if ([int]$shapeRange.Count -ge 1) {
        $shape = $shapeRange.Item(1)
        $objectName = [string]$shape.Name
        $objectKind = 'shape'
        try {
          # msoChart = 3 (Excel); WPS often omits Type — treat a usable .Chart as chart.
          if ([int]$shape.Type -eq 3) { $objectKind = 'chart' }
        } catch { }
        try {
          if ($null -ne $shape.Chart) { $objectKind = 'chart' }
        } catch { }
        try {
          if ([string]::IsNullOrEmpty($sheetName)) { $sheetName = [string]$shape.Parent.Name }
        } catch { }
      }
    } catch { }
    # Series or SeriesPoint selection: Selection.Values or Parent.Values is readable.
    if ($objectKind -ne 'chart') {
      try {
        $seriesCom = $null
        try {
          $null = $sel.Values
          $seriesCom = $sel
        } catch {
          try {
            $null = $sel.Parent.Values
            $seriesCom = $sel.Parent
          } catch { }
        }
        if ($null -ne $seriesCom) {
          $chartCom = $null
          try {
            $null = $seriesCom.Parent.ChartType
            $chartCom = $seriesCom.Parent
          } catch {
            try {
              $null = $seriesCom.Parent.Parent.ChartType
              $chartCom = $seriesCom.Parent.Parent
            } catch { }
          }
          $chartObjectName = $null
          if ($null -ne $chartCom) {
            try { $chartObjectName = [string]$chartCom.Parent.Name } catch { }
          }
          if ([string]::IsNullOrEmpty($chartObjectName)) {
            try { $chartObjectName = [string]$seriesCom.Parent.Parent.Name } catch {
              try { $chartObjectName = [string]$seriesCom.Parent.Name } catch { }
            }
          }
          if (-not [string]::IsNullOrEmpty($chartObjectName)) {
            $objectKind = 'chart'
            $objectName = $chartObjectName
            $shape = $null
            $hasSeriesValues = $true
            try { $seriesName = [string]$seriesCom.Name } catch { $seriesName = $null }
            $parts = New-Object System.Collections.Generic.List[string]
            $valueIndex = 0
            foreach ($value in @($seriesCom.Values)) {
              $valueIndex++
              if ($valueIndex -gt __MAX_SAMPLE_CELLS__) {
                $sampleTruncated = $true
                break
              }
              if ($null -eq $value) { [void]$parts.Add('') }
              else { [void]$parts.Add([string]$value) }
            }
            $text = [string]::Join("`t", $parts)
            try {
              if ([string]::IsNullOrEmpty($sheetName) -and $null -ne $chartCom) {
                $sheetName = [string]$chartCom.Parent.Parent.Name
              }
            } catch { }
          }
        }
      } catch { }
    }
    # AxisTitle selection: Parent is Axis (HasTitle + AxisTitle; ChartType absent).
    # WPS may expose a hollow ChartTitle on Axis, so do not use ChartTitle presence alone.
    if ($objectKind -ne 'chart') {
      try {
        $maybeAxis = $sel.Parent
        $null = [bool]$maybeAxis.HasTitle
        $axisTitleText = [string]$maybeAxis.AxisTitle.Text
        $axisChartType = $null
        try { $axisChartType = $maybeAxis.ChartType } catch { }
        if ($null -eq $axisChartType) {
          $chartObjectName = $null
          try { $chartObjectName = [string]$maybeAxis.Parent.Parent.Name } catch { }
          if (-not [string]::IsNullOrEmpty($chartObjectName)) {
            $objectKind = 'chart'
            $objectName = $chartObjectName
            $shape = $null
            $hasAxisTitle = $true
            $text = $axisTitleText
            try {
              if ([string]::IsNullOrEmpty($sheetName)) {
                $sheetName = [string]$maybeAxis.Parent.Parent.Parent.Name
              }
            } catch { }
          }
        }
      } catch { }
    }
    # WPS ChartObject selection is often ChartArea/ChartTitle (Name=图表/标题),
    # ShapeRange.Count=0, and Selection.Parent is the Chart (HasTitle + ChartType).
    if ($objectKind -ne 'chart') {
      try {
        $maybeChart = $sel.Parent
        $null = [bool]$maybeChart.HasTitle
        $chartType = $null
        try { $chartType = $maybeChart.ChartType } catch { }
        if ($null -eq $chartType) { throw 'not a chart parent' }
        $chartObjectName = $null
        try { $chartObjectName = [string]$maybeChart.Parent.Name } catch { }
        if (-not [string]::IsNullOrEmpty($chartObjectName)) {
          $objectKind = 'chart'
          $objectName = $chartObjectName
          $shape = $null
          try {
            if ([string]::IsNullOrEmpty($sheetName)) {
              $sheetName = [string]$maybeChart.Parent.Parent.Name
            }
          } catch { }
        }
      } catch {
        try {
          $chartType = $null
          try { $chartType = $sel.Parent.ChartType } catch { }
          if ($null -ne $chartType) {
            $chartObject = $sel.Parent.Parent
            $objectName = [string]$chartObject.Name
            $objectKind = 'chart'
            $shape = $null
            try {
              if ([string]::IsNullOrEmpty($sheetName)) { $sheetName = [string]$chartObject.Parent.Name }
            } catch { }
          }
        } catch { }
      }
    }
    # WPS may return the Shape COM object itself rather than a ShapeRange wrapper.
    if ($objectKind -ne 'chart' -and [string]::IsNullOrEmpty($objectName)) {
      try {
        $maybeType = $null
        try { $maybeType = [int]$sel.Type } catch { }
        $maybeName = [string]$sel.Name
        if (-not [string]::IsNullOrEmpty($maybeName) -and $null -ne $maybeType) {
          $shape = $sel
          $objectName = $maybeName
          $objectKind = 'shape'
          if ($maybeType -eq 3) { $objectKind = 'chart' }
          try {
            if ($null -ne $sel.Chart) { $objectKind = 'chart' }
          } catch { }
          try {
            if ([string]::IsNullOrEmpty($sheetName)) { $sheetName = [string]$sel.Parent.Name }
          } catch { }
        }
      } catch { }
    }
    if ([string]::IsNullOrEmpty($objectName)) {
      try {
        $objectName = [string]$sel.Name
        if (-not [string]::IsNullOrEmpty($objectName)) { $objectKind = 'object' }
      } catch { }
    }
    if (-not [string]::IsNullOrEmpty($objectName) -and $kind -eq 'unknown') {
      $kind = 'non_range'
    }
    if ($objectKind -eq 'shape' -and $null -ne $shape) {
      try {
        $tf = $shape.TextFrame
        try {
          $text = [string]$tf.Characters().Text
          $hasTextFrame = $true
        } catch {
          try {
            $text = [string]$tf.Characters.Text
            $hasTextFrame = $true
          } catch { }
        }
      } catch { }
    }
    if ($objectKind -eq 'chart' -and -not $hasAxisTitle -and -not $hasSeriesValues) {
      $chartCom = $null
      try {
        if ($null -ne $shape) { $chartCom = $shape.Chart }
      } catch { }
      if ($null -eq $chartCom) {
        try {
          $maybeChart = $sel.Parent
          $null = [bool]$maybeChart.HasTitle
          $chartTypeProbe = $null
          try { $chartTypeProbe = $maybeChart.ChartType } catch { }
          if ($null -eq $chartTypeProbe) { throw 'not chart' }
          $chartCom = $maybeChart
        } catch {
          try {
            $chartTypeProbe = $null
            try { $chartTypeProbe = $sel.Parent.ChartType } catch { }
            if ($null -ne $chartTypeProbe) { $chartCom = $sel.Parent }
          } catch { }
        }
      }
      if ($null -ne $chartCom) {
        try {
          if ([bool]$chartCom.HasTitle) {
            $text = [string]$chartCom.ChartTitle.Text
          } else {
            $text = ''
          }
          $hasChartTitle = $true
        } catch {
          try {
            $text = [string]$chartCom.ChartTitle.Text
            $hasChartTitle = $true
          } catch { }
        }
      }
    }
  }
  $rowCount = 0
  $columnCount = 0
  try {
    if ($kind -eq 'cell' -or $kind -eq 'range') {
      $rowCount = [int]$sel.Rows.Count
      $columnCount = [int]$sel.Columns.Count
    }
  } catch { }
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'spreadsheets'
    saved = [bool]$doc.Saved
    read_only = [bool]$doc.ReadOnly
    selection_kind = $kind
    address = $address
    sheet_name = $sheetName
    cell_count = $cellCount
    area_count = $areaCount
    row_count = $rowCount
    column_count = $columnCount
    selection_text = $text
    sample_truncated = [bool]$sampleTruncated
    formula = $formula
    object_kind = $objectKind
    object_name = $objectName
    has_text_frame = [bool]$hasTextFrame
    has_chart_title = [bool]$hasChartTitle
    has_axis_title = [bool]$hasAxisTitle
    has_series_values = [bool]$hasSeriesValues
    series_name = $seriesName
  } | ConvertTo-Json -Depth 5
""".replace("__MAX_SAMPLE_CELLS__", str(MAX_SPREADSHEET_SELECTION_SAMPLE_CELLS))

_SPREADSHEET_SHAPE_TEXT_REPLACE_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ([bool]$doc.ReadOnly) {
    [pscustomobject]@{ ok = $true; status = 'read_only' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $window = $null
  try {
    if ([int]$doc.Windows.Count -ge 1) { $window = $doc.Windows.Item(1) }
  } catch { }
  if ($null -eq $window) {
    try {
      $active = $app.ActiveWorkbook
      if ($null -ne $active -and [string]::Equals(
        [System.IO.Path]::GetFullPath([string]$active.FullName),
        [System.IO.Path]::GetFullPath([string]$params.path),
        [System.StringComparison]::OrdinalIgnoreCase
      )) { $window = $app.ActiveWindow }
    } catch { }
  }
  if ($null -eq $window) {
    [pscustomobject]@{ ok = $true; status = 'no_window' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $sel = $null
  try { $sel = $window.Selection } catch { }
  $shape = $null
  try {
    $shapeRange = $sel.ShapeRange
    if ([int]$shapeRange.Count -ge 1) { $shape = $shapeRange.Item(1) }
  } catch { }
  if ($null -eq $shape) {
    try {
      $maybeName = [string]$sel.Name
      $maybeType = $null
      try { $maybeType = [int]$sel.Type } catch { }
      if (-not [string]::IsNullOrEmpty($maybeName) -and $null -ne $maybeType -and $maybeType -ne 3) {
        $shape = $sel
      }
    } catch { }
  }
  if ($null -eq $shape) {
    [pscustomobject]@{ ok = $true; status = 'not_shape_selection' } | ConvertTo-Json -Depth 5
    exit 0
  }
  try {
    if ([int]$shape.Type -eq 3) {
      [pscustomobject]@{ ok = $true; status = 'not_shape_selection' } | ConvertTo-Json -Depth 5
      exit 0
    }
  } catch { }
  try {
    if ($null -ne $shape.Chart) {
      [pscustomobject]@{ ok = $true; status = 'not_shape_selection' } | ConvertTo-Json -Depth 5
      exit 0
    }
  } catch { }
  # WPS chart ChartArea/Title selections must not be treated as TextFrame shapes.
  try {
    $null = [bool]$sel.Parent.HasTitle
    [pscustomobject]@{ ok = $true; status = 'not_shape_selection' } | ConvertTo-Json -Depth 5
    exit 0
  } catch { }
  $objectName = [string]$shape.Name
  if ($objectName -cne [string]$params.expected_object_name) {
    [pscustomobject]@{ ok = $true; status = 'selection_changed'; current_object_name = $objectName } | ConvertTo-Json -Depth 5
    exit 0
  }
  $before = ''
  $chars = $null
  try {
    $tf = $shape.TextFrame
    try { $chars = $tf.Characters() } catch { try { $chars = $tf.Characters } catch { } }
    if ($null -eq $chars) {
      [pscustomobject]@{ ok = $true; status = 'no_text_frame' } | ConvertTo-Json -Depth 5
      exit 0
    }
    $before = [string]$chars.Text
  } catch {
    [pscustomobject]@{ ok = $true; status = 'no_text_frame' } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ($before -cne [string]$params.expected_text) {
    [pscustomobject]@{ ok = $true; status = 'selection_changed'; current_text = $before } | ConvertTo-Json -Depth 5
    exit 0
  }
  $chars.Text = [string]$params.text
  $doc.Save()
  $readBack = ''
  try {
    try { $readBack = [string]$shape.TextFrame.Characters().Text }
    catch { $readBack = [string]$shape.TextFrame.Characters.Text }
  } catch { }
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'spreadsheets'
    object_kind = 'shape'
    object_name = $objectName
    cells_matched = ($readBack -ceq [string]$params.text)
    read_back_text = [string]$readBack
  } | ConvertTo-Json -Depth 5
"""

_SPREADSHEET_SHAPE_TEXT_DELETE_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ([bool]$doc.ReadOnly) {
    [pscustomobject]@{ ok = $true; status = 'read_only' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $window = $null
  try {
    if ([int]$doc.Windows.Count -ge 1) { $window = $doc.Windows.Item(1) }
  } catch { }
  if ($null -eq $window) {
    try {
      $active = $app.ActiveWorkbook
      if ($null -ne $active -and [string]::Equals(
        [System.IO.Path]::GetFullPath([string]$active.FullName),
        [System.IO.Path]::GetFullPath([string]$params.path),
        [System.StringComparison]::OrdinalIgnoreCase
      )) { $window = $app.ActiveWindow }
    } catch { }
  }
  if ($null -eq $window) {
    [pscustomobject]@{ ok = $true; status = 'no_window' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $sel = $null
  try { $sel = $window.Selection } catch { }
  $shape = $null
  try {
    $shapeRange = $sel.ShapeRange
    if ([int]$shapeRange.Count -ge 1) { $shape = $shapeRange.Item(1) }
  } catch { }
  if ($null -eq $shape) {
    try {
      $maybeName = [string]$sel.Name
      $maybeType = $null
      try { $maybeType = [int]$sel.Type } catch { }
      if (-not [string]::IsNullOrEmpty($maybeName) -and $null -ne $maybeType -and $maybeType -ne 3) {
        $shape = $sel
      }
    } catch { }
  }
  if ($null -eq $shape) {
    [pscustomobject]@{ ok = $true; status = 'not_shape_selection' } | ConvertTo-Json -Depth 5
    exit 0
  }
  try {
    if ([int]$shape.Type -eq 3) {
      [pscustomobject]@{ ok = $true; status = 'not_shape_selection' } | ConvertTo-Json -Depth 5
      exit 0
    }
  } catch { }
  try {
    if ($null -ne $shape.Chart) {
      [pscustomobject]@{ ok = $true; status = 'not_shape_selection' } | ConvertTo-Json -Depth 5
      exit 0
    }
  } catch { }
  try {
    $null = [bool]$sel.Parent.HasTitle
    [pscustomobject]@{ ok = $true; status = 'not_shape_selection' } | ConvertTo-Json -Depth 5
    exit 0
  } catch { }
  $objectName = [string]$shape.Name
  if ($objectName -cne [string]$params.expected_object_name) {
    [pscustomobject]@{ ok = $true; status = 'selection_changed'; current_object_name = $objectName } | ConvertTo-Json -Depth 5
    exit 0
  }
  $before = ''
  $chars = $null
  try {
    $tf = $shape.TextFrame
    try { $chars = $tf.Characters() } catch { try { $chars = $tf.Characters } catch { } }
    if ($null -eq $chars) {
      [pscustomobject]@{ ok = $true; status = 'no_text_frame' } | ConvertTo-Json -Depth 5
      exit 0
    }
    $before = [string]$chars.Text
  } catch {
    [pscustomobject]@{ ok = $true; status = 'no_text_frame' } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ($before -cne [string]$params.expected_text) {
    [pscustomobject]@{ ok = $true; status = 'selection_changed'; current_text = $before } | ConvertTo-Json -Depth 5
    exit 0
  }
  $chars.Text = ''
  $doc.Save()
  $readBack = ''
  try {
    try { $readBack = [string]$shape.TextFrame.Characters().Text }
    catch { $readBack = [string]$shape.TextFrame.Characters.Text }
  } catch { }
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'spreadsheets'
    object_kind = 'shape'
    object_name = $objectName
    cells_matched = [string]::IsNullOrEmpty($readBack)
    deleted_text = [string]$params.expected_text
    read_back_text = [string]$readBack
  } | ConvertTo-Json -Depth 5
"""

_SPREADSHEET_CHART_TITLE_REPLACE_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ([bool]$doc.ReadOnly) {
    [pscustomobject]@{ ok = $true; status = 'read_only' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $window = $null
  try {
    if ([int]$doc.Windows.Count -ge 1) { $window = $doc.Windows.Item(1) }
  } catch { }
  if ($null -eq $window) {
    try {
      $active = $app.ActiveWorkbook
      if ($null -ne $active -and [string]::Equals(
        [System.IO.Path]::GetFullPath([string]$active.FullName),
        [System.IO.Path]::GetFullPath([string]$params.path),
        [System.StringComparison]::OrdinalIgnoreCase
      )) { $window = $app.ActiveWindow }
    } catch { }
  }
  if ($null -eq $window) {
    [pscustomobject]@{ ok = $true; status = 'no_window' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $sel = $null
  try { $sel = $window.Selection } catch { }
  $chartCom = $null
  $objectName = $null
  try {
    $shapeRange = $sel.ShapeRange
    if ([int]$shapeRange.Count -ge 1) {
      $shape = $shapeRange.Item(1)
      try {
        if ($null -ne $shape.Chart) {
          $chartCom = $shape.Chart
          $objectName = [string]$shape.Name
        }
      } catch { }
    }
  } catch { }
  if ($null -eq $chartCom) {
    try {
      if ($null -ne $sel.Chart) {
        $chartCom = $sel.Chart
        $objectName = [string]$sel.Name
      }
    } catch { }
  }
  if ($null -eq $chartCom) {
    try {
      $maybeChart = $sel.Parent
      $null = [bool]$maybeChart.HasTitle
      $chartCom = $maybeChart
      try { $objectName = [string]$maybeChart.Parent.Name } catch { }
    } catch {
      try {
        $chartTypeProbe = $null
        try { $chartTypeProbe = $sel.Parent.ChartType } catch { }
        if ($null -ne $chartTypeProbe) {
          $chartCom = $sel.Parent
          try { $objectName = [string]$sel.Parent.Parent.Name } catch { }
        }
      } catch { }
    }
  }
  if ($null -eq $chartCom) {
    [pscustomobject]@{ ok = $true; status = 'not_chart_selection' } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ([string]::IsNullOrEmpty($objectName)) { $objectName = [string]$params.expected_object_name }
  if ($objectName -cne [string]$params.expected_object_name) {
    [pscustomobject]@{ ok = $true; status = 'selection_changed'; current_object_name = $objectName } | ConvertTo-Json -Depth 5
    exit 0
  }
  $before = ''
  try {
    if ([bool]$chartCom.HasTitle) { $before = [string]$chartCom.ChartTitle.Text }
  } catch {
    [pscustomobject]@{ ok = $true; status = 'no_chart_title' } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ($before -cne [string]$params.expected_text) {
    [pscustomobject]@{ ok = $true; status = 'selection_changed'; current_text = $before } | ConvertTo-Json -Depth 5
    exit 0
  }
  try {
    if (-not [bool]$chartCom.HasTitle) { $chartCom.HasTitle = $true }
    $chartCom.ChartTitle.Text = [string]$params.text
  } catch {
    [pscustomobject]@{ ok = $true; status = 'no_chart_title' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $doc.Save()
  $readBack = ''
  try {
    if ([bool]$chartCom.HasTitle) { $readBack = [string]$chartCom.ChartTitle.Text }
  } catch { }
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'spreadsheets'
    object_kind = 'chart'
    object_name = $objectName
    cells_matched = ($readBack -ceq [string]$params.text)
    read_back_text = [string]$readBack
  } | ConvertTo-Json -Depth 5
"""

_SPREADSHEET_CHART_TITLE_DELETE_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ([bool]$doc.ReadOnly) {
    [pscustomobject]@{ ok = $true; status = 'read_only' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $window = $null
  try {
    if ([int]$doc.Windows.Count -ge 1) { $window = $doc.Windows.Item(1) }
  } catch { }
  if ($null -eq $window) {
    try {
      $active = $app.ActiveWorkbook
      if ($null -ne $active -and [string]::Equals(
        [System.IO.Path]::GetFullPath([string]$active.FullName),
        [System.IO.Path]::GetFullPath([string]$params.path),
        [System.StringComparison]::OrdinalIgnoreCase
      )) { $window = $app.ActiveWindow }
    } catch { }
  }
  if ($null -eq $window) {
    [pscustomobject]@{ ok = $true; status = 'no_window' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $sel = $null
  try { $sel = $window.Selection } catch { }
  $chartCom = $null
  $objectName = $null
  try {
    $shapeRange = $sel.ShapeRange
    if ([int]$shapeRange.Count -ge 1) {
      $shape = $shapeRange.Item(1)
      try {
        if ($null -ne $shape.Chart) {
          $chartCom = $shape.Chart
          $objectName = [string]$shape.Name
        }
      } catch { }
    }
  } catch { }
  if ($null -eq $chartCom) {
    try {
      if ($null -ne $sel.Chart) {
        $chartCom = $sel.Chart
        $objectName = [string]$sel.Name
      }
    } catch { }
  }
  if ($null -eq $chartCom) {
    try {
      $maybeChart = $sel.Parent
      $null = [bool]$maybeChart.HasTitle
      $chartCom = $maybeChart
      try { $objectName = [string]$maybeChart.Parent.Name } catch { }
    } catch {
      try {
        $chartTypeProbe = $null
        try { $chartTypeProbe = $sel.Parent.ChartType } catch { }
        if ($null -ne $chartTypeProbe) {
          $chartCom = $sel.Parent
          try { $objectName = [string]$sel.Parent.Parent.Name } catch { }
        }
      } catch { }
    }
  }
  if ($null -eq $chartCom) {
    [pscustomobject]@{ ok = $true; status = 'not_chart_selection' } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ([string]::IsNullOrEmpty($objectName)) { $objectName = [string]$params.expected_object_name }
  if ($objectName -cne [string]$params.expected_object_name) {
    [pscustomobject]@{ ok = $true; status = 'selection_changed'; current_object_name = $objectName } | ConvertTo-Json -Depth 5
    exit 0
  }
  $before = ''
  try {
    if ([bool]$chartCom.HasTitle) { $before = [string]$chartCom.ChartTitle.Text }
  } catch {
    [pscustomobject]@{ ok = $true; status = 'no_chart_title' } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ($before -cne [string]$params.expected_text) {
    [pscustomobject]@{ ok = $true; status = 'selection_changed'; current_text = $before } | ConvertTo-Json -Depth 5
    exit 0
  }
  try {
    if ([bool]$chartCom.HasTitle) {
      $chartCom.ChartTitle.Text = ''
      $chartCom.HasTitle = $false
    }
  } catch {
    [pscustomobject]@{ ok = $true; status = 'no_chart_title' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $doc.Save()
  $readBack = ''
  try {
    if ([bool]$chartCom.HasTitle) { $readBack = [string]$chartCom.ChartTitle.Text }
  } catch { }
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'spreadsheets'
    object_kind = 'chart'
    object_name = $objectName
    cells_matched = [string]::IsNullOrEmpty($readBack)
    deleted_text = [string]$params.expected_text
    read_back_text = [string]$readBack
  } | ConvertTo-Json -Depth 5
"""

_SPREADSHEET_AXIS_TITLE_REPLACE_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ([bool]$doc.ReadOnly) {
    [pscustomobject]@{ ok = $true; status = 'read_only' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $window = $null
  try {
    if ([int]$doc.Windows.Count -ge 1) { $window = $doc.Windows.Item(1) }
  } catch { }
  if ($null -eq $window) {
    try {
      $active = $app.ActiveWorkbook
      if ($null -ne $active -and [string]::Equals(
        [System.IO.Path]::GetFullPath([string]$active.FullName),
        [System.IO.Path]::GetFullPath([string]$params.path),
        [System.StringComparison]::OrdinalIgnoreCase
      )) { $window = $app.ActiveWindow }
    } catch { }
  }
  if ($null -eq $window) {
    [pscustomobject]@{ ok = $true; status = 'no_window' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $sel = $null
  try { $sel = $window.Selection } catch { }
  $axis = $null
  $objectName = $null
  try {
    $maybeAxis = $sel.Parent
    $null = [bool]$maybeAxis.HasTitle
    $null = [string]$maybeAxis.AxisTitle.Text
    $axisChartType = $null
    try { $axisChartType = $maybeAxis.ChartType } catch { }
    if ($null -eq $axisChartType) {
      $axis = $maybeAxis
      try { $objectName = [string]$axis.Parent.Parent.Name } catch { }
    }
  } catch { }
  if ($null -eq $axis) {
    [pscustomobject]@{ ok = $true; status = 'not_axis_title_selection' } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ([string]::IsNullOrEmpty($objectName)) { $objectName = [string]$params.expected_object_name }
  if ($objectName -cne [string]$params.expected_object_name) {
    [pscustomobject]@{ ok = $true; status = 'selection_changed'; current_object_name = $objectName } | ConvertTo-Json -Depth 5
    exit 0
  }
  $before = ''
  try {
    if ([bool]$axis.HasTitle) { $before = [string]$axis.AxisTitle.Text }
  } catch {
    [pscustomobject]@{ ok = $true; status = 'no_axis_title' } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ($before -cne [string]$params.expected_text) {
    [pscustomobject]@{ ok = $true; status = 'selection_changed'; current_text = $before } | ConvertTo-Json -Depth 5
    exit 0
  }
  try {
    if (-not [bool]$axis.HasTitle) { $axis.HasTitle = $true }
    $axis.AxisTitle.Text = [string]$params.text
  } catch {
    [pscustomobject]@{ ok = $true; status = 'no_axis_title' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $doc.Save()
  $readBack = ''
  try {
    if ([bool]$axis.HasTitle) { $readBack = [string]$axis.AxisTitle.Text }
  } catch { }
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'spreadsheets'
    object_kind = 'chart'
    object_name = $objectName
    cells_matched = ($readBack -ceq [string]$params.text)
    read_back_text = [string]$readBack
  } | ConvertTo-Json -Depth 5
"""

_SPREADSHEET_AXIS_TITLE_DELETE_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ([bool]$doc.ReadOnly) {
    [pscustomobject]@{ ok = $true; status = 'read_only' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $window = $null
  try {
    if ([int]$doc.Windows.Count -ge 1) { $window = $doc.Windows.Item(1) }
  } catch { }
  if ($null -eq $window) {
    try {
      $active = $app.ActiveWorkbook
      if ($null -ne $active -and [string]::Equals(
        [System.IO.Path]::GetFullPath([string]$active.FullName),
        [System.IO.Path]::GetFullPath([string]$params.path),
        [System.StringComparison]::OrdinalIgnoreCase
      )) { $window = $app.ActiveWindow }
    } catch { }
  }
  if ($null -eq $window) {
    [pscustomobject]@{ ok = $true; status = 'no_window' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $sel = $null
  try { $sel = $window.Selection } catch { }
  $axis = $null
  $objectName = $null
  try {
    $maybeAxis = $sel.Parent
    $null = [bool]$maybeAxis.HasTitle
    $null = [string]$maybeAxis.AxisTitle.Text
    $axisChartType = $null
    try { $axisChartType = $maybeAxis.ChartType } catch { }
    if ($null -eq $axisChartType) {
      $axis = $maybeAxis
      try { $objectName = [string]$axis.Parent.Parent.Name } catch { }
    }
  } catch { }
  if ($null -eq $axis) {
    [pscustomobject]@{ ok = $true; status = 'not_axis_title_selection' } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ([string]::IsNullOrEmpty($objectName)) { $objectName = [string]$params.expected_object_name }
  if ($objectName -cne [string]$params.expected_object_name) {
    [pscustomobject]@{ ok = $true; status = 'selection_changed'; current_object_name = $objectName } | ConvertTo-Json -Depth 5
    exit 0
  }
  $before = ''
  try {
    if ([bool]$axis.HasTitle) { $before = [string]$axis.AxisTitle.Text }
  } catch {
    [pscustomobject]@{ ok = $true; status = 'no_axis_title' } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ($before -cne [string]$params.expected_text) {
    [pscustomobject]@{ ok = $true; status = 'selection_changed'; current_text = $before } | ConvertTo-Json -Depth 5
    exit 0
  }
  try {
    if ([bool]$axis.HasTitle) {
      $axis.AxisTitle.Text = ''
      $axis.HasTitle = $false
    }
  } catch {
    [pscustomobject]@{ ok = $true; status = 'no_axis_title' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $doc.Save()
  $readBack = ''
  try {
    if ([bool]$axis.HasTitle) { $readBack = [string]$axis.AxisTitle.Text }
  } catch { }
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'spreadsheets'
    object_kind = 'chart'
    object_name = $objectName
    cells_matched = [string]::IsNullOrEmpty($readBack)
    deleted_text = [string]$params.expected_text
    read_back_text = [string]$readBack
  } | ConvertTo-Json -Depth 5
"""

_SPREADSHEET_SERIES_VALUES_REPLACE_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ([bool]$doc.ReadOnly) {
    [pscustomobject]@{ ok = $true; status = 'read_only' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $window = $null
  try {
    if ([int]$doc.Windows.Count -ge 1) { $window = $doc.Windows.Item(1) }
  } catch { }
  if ($null -eq $window) {
    try {
      $active = $app.ActiveWorkbook
      if ($null -ne $active -and [string]::Equals(
        [System.IO.Path]::GetFullPath([string]$active.FullName),
        [System.IO.Path]::GetFullPath([string]$params.path),
        [System.StringComparison]::OrdinalIgnoreCase
      )) { $window = $app.ActiveWindow }
    } catch { }
  }
  if ($null -eq $window) {
    [pscustomobject]@{ ok = $true; status = 'no_window' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $sel = $null
  try { $sel = $window.Selection } catch { }
  $series = $null
  $objectName = $null
  try {
    try {
      $null = $sel.Values
      $series = $sel
    } catch {
      $null = $sel.Parent.Values
      $series = $sel.Parent
    }
    $chartCom = $null
    try {
      $null = $series.Parent.ChartType
      $chartCom = $series.Parent
    } catch {
      try {
        $null = $series.Parent.Parent.ChartType
        $chartCom = $series.Parent.Parent
      } catch { }
    }
    if ($null -ne $chartCom) {
      try { $objectName = [string]$chartCom.Parent.Name } catch { }
    }
    if ([string]::IsNullOrEmpty($objectName)) {
      try { $objectName = [string]$series.Parent.Parent.Name } catch {
        try { $objectName = [string]$series.Parent.Name } catch { }
      }
    }
  } catch { }
  if ($null -eq $series) {
    [pscustomobject]@{ ok = $true; status = 'not_series_selection' } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ([string]::IsNullOrEmpty($objectName)) { $objectName = [string]$params.expected_object_name }
  if ($objectName -cne [string]$params.expected_object_name) {
    [pscustomobject]@{ ok = $true; status = 'selection_changed'; current_object_name = $objectName } | ConvertTo-Json -Depth 5
    exit 0
  }
  $beforeParts = New-Object System.Collections.Generic.List[string]
  foreach ($value in @($series.Values)) {
    if ($null -eq $value) { [void]$beforeParts.Add('') } else { [void]$beforeParts.Add([string]$value) }
  }
  $before = [string]::Join([char]9, $beforeParts)
  if ($before -cne [string]$params.expected_text) {
    [pscustomobject]@{ ok = $true; status = 'selection_changed'; current_text = $before } | ConvertTo-Json -Depth 5
    exit 0
  }
  $rawParts = @($params.values)
  if ($rawParts.Count -ne $beforeParts.Count) {
    [pscustomobject]@{
      ok = $true
      status = 'series_length_mismatch'
      expected_count = [int]$beforeParts.Count
      provided_count = [int]$rawParts.Count
    } | ConvertTo-Json -Depth 5
    exit 0
  }
  $outValues = New-Object object[] $rawParts.Count
  for ($i = 0; $i -lt $rawParts.Count; $i++) {
    $piece = if ($null -eq $rawParts[$i]) { '' } else { [string]$rawParts[$i] }
    $num = 0.0
    if ([string]::IsNullOrEmpty($piece)) { $outValues[$i] = $null }
    elseif ([double]::TryParse($piece, [ref]$num)) { $outValues[$i] = $num }
    else { $outValues[$i] = $piece }
  }
  try { $series.Values = $outValues }
  catch {
    [pscustomobject]@{ ok = $true; status = 'no_series_values' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $doc.Save()
  $readParts = New-Object System.Collections.Generic.List[string]
  foreach ($value in @($series.Values)) {
    if ($null -eq $value) { [void]$readParts.Add('') } else { [void]$readParts.Add([string]$value) }
  }
  $readBack = [string]::Join([char]9, $readParts)
  $expectedJoined = [string]::Join([char]9, @($params.values | ForEach-Object { if ($null -eq $_) { '' } else { [string]$_ } }))
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'spreadsheets'
    object_kind = 'chart'
    object_name = $objectName
    series_name = $(try { [string]$series.Name } catch { $null })
    cells_matched = ($readBack -ceq $expectedJoined)
    read_back_text = [string]$readBack
  } | ConvertTo-Json -Depth 5
"""

_SPREADSHEET_SERIES_VALUES_DELETE_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ([bool]$doc.ReadOnly) {
    [pscustomobject]@{ ok = $true; status = 'read_only' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $window = $null
  try {
    if ([int]$doc.Windows.Count -ge 1) { $window = $doc.Windows.Item(1) }
  } catch { }
  if ($null -eq $window) {
    try {
      $active = $app.ActiveWorkbook
      if ($null -ne $active -and [string]::Equals(
        [System.IO.Path]::GetFullPath([string]$active.FullName),
        [System.IO.Path]::GetFullPath([string]$params.path),
        [System.StringComparison]::OrdinalIgnoreCase
      )) { $window = $app.ActiveWindow }
    } catch { }
  }
  if ($null -eq $window) {
    [pscustomobject]@{ ok = $true; status = 'no_window' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $sel = $null
  try { $sel = $window.Selection } catch { }
  $series = $null
  $objectName = $null
  try {
    try {
      $null = $sel.Values
      $series = $sel
    } catch {
      $null = $sel.Parent.Values
      $series = $sel.Parent
    }
    $chartCom = $null
    try {
      $null = $series.Parent.ChartType
      $chartCom = $series.Parent
    } catch {
      try {
        $null = $series.Parent.Parent.ChartType
        $chartCom = $series.Parent.Parent
      } catch { }
    }
    if ($null -ne $chartCom) {
      try { $objectName = [string]$chartCom.Parent.Name } catch { }
    }
    if ([string]::IsNullOrEmpty($objectName)) {
      try { $objectName = [string]$series.Parent.Parent.Name } catch {
        try { $objectName = [string]$series.Parent.Name } catch { }
      }
    }
  } catch { }
  if ($null -eq $series) {
    [pscustomobject]@{ ok = $true; status = 'not_series_selection' } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ([string]::IsNullOrEmpty($objectName)) { $objectName = [string]$params.expected_object_name }
  if ($objectName -cne [string]$params.expected_object_name) {
    [pscustomobject]@{ ok = $true; status = 'selection_changed'; current_object_name = $objectName } | ConvertTo-Json -Depth 5
    exit 0
  }
  $beforeParts = New-Object System.Collections.Generic.List[string]
  foreach ($value in @($series.Values)) {
    if ($null -eq $value) { [void]$beforeParts.Add('') } else { [void]$beforeParts.Add([string]$value) }
  }
  $before = [string]::Join("`t", $beforeParts)
  if ($before -cne [string]$params.expected_text) {
    [pscustomobject]@{ ok = $true; status = 'selection_changed'; current_text = $before } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ([string]::IsNullOrEmpty($before)) {
    [pscustomobject]@{ ok = $true; status = 'no_series_values' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $cleared = New-Object object[] $beforeParts.Count
  for ($i = 0; $i -lt $beforeParts.Count; $i++) { $cleared[$i] = $null }
  try { $series.Values = $cleared }
  catch {
    [pscustomobject]@{ ok = $true; status = 'no_series_values' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $doc.Save()
  $readParts = New-Object System.Collections.Generic.List[string]
  foreach ($value in @($series.Values)) {
    if ($null -eq $value) { [void]$readParts.Add('') } else { [void]$readParts.Add([string]$value) }
  }
  $readBack = [string]::Join("`t", $readParts)
  $allEmpty = $true
  foreach ($part in $readParts) { if (-not [string]::IsNullOrEmpty([string]$part)) { $allEmpty = $false; break } }
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'spreadsheets'
    object_kind = 'chart'
    object_name = $objectName
    series_name = $(try { [string]$series.Name } catch { $null })
    cells_matched = [bool]$allEmpty
    deleted_text = [string]$params.expected_text
    read_back_text = [string]$readBack
  } | ConvertTo-Json -Depth 5
"""

_SPREADSHEET_SELECTION_REPLACE_BODY = """
  function Test-CellTextMatch([string]$actual, [string]$expected) {
    if ($actual -ceq $expected) { return $true }
    $parsedActual = 0.0
    $parsedExpected = 0.0
    $culture = [System.Globalization.CultureInfo]::InvariantCulture
    $styles = [System.Globalization.NumberStyles]::Float
    if ([double]::TryParse($actual, $styles, $culture, [ref]$parsedActual) -and [double]::TryParse($expected, $styles, $culture, [ref]$parsedExpected)) {
      return ($parsedActual -eq $parsedExpected)
    }
    return $false
  }
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ([bool]$doc.ReadOnly) {
    [pscustomobject]@{ ok = $true; status = 'read_only' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $window = $null
  try {
    if ([int]$doc.Windows.Count -ge 1) { $window = $doc.Windows.Item(1) }
  } catch { }
  if ($null -eq $window) {
    try {
      $active = $app.ActiveWorkbook
      if ($null -ne $active -and [string]::Equals(
        [System.IO.Path]::GetFullPath([string]$active.FullName),
        [System.IO.Path]::GetFullPath([string]$params.path),
        [System.StringComparison]::OrdinalIgnoreCase
      )) { $window = $app.ActiveWindow }
    } catch { }
  }
  if ($null -eq $window) {
    [pscustomobject]@{ ok = $true; status = 'no_window' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $sel = $null
  try { $sel = $window.Selection } catch { }
  if ($null -eq $sel) {
    try { $sel = $window.RangeSelection } catch { }
  }
  $address = $null
  $cellCount = 0
  $areaCount = 0
  try {
    $address = [string]$sel.Address($true, $true)
    $cellCount = [int]$sel.Cells.Count
    $areaCount = [int]$sel.Areas.Count
  } catch {
    [pscustomobject]@{ ok = $true; status = 'not_cell_selection' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $maxCells = [int]$params.max_cells
  $mode = [string]$params.mode
  if ($areaCount -lt 1 -or $cellCount -lt 1 -or $cellCount -gt $maxCells) {
    [pscustomobject]@{
      ok = $true
      status = 'not_cell_selection'
      cell_count = $cellCount
      area_count = $areaCount
    } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ($address -cne [string]$params.expected_address) {
    [pscustomobject]@{ ok = $true; status = 'selection_changed'; current_address = $address } | ConvertTo-Json -Depth 5
    exit 0
  }
  $parts = New-Object System.Collections.Generic.List[string]
  foreach ($area in $sel.Areas) {
    foreach ($cell in $area.Cells) {
      try { $parts.Add([string]$cell.Text) } catch { $parts.Add('') }
    }
  }
  $before = [string]::Join("`t", $parts)
  if ($before -cne [string]$params.expected_text) {
    [pscustomobject]@{ ok = $true; status = 'selection_changed'; current_text = $before } | ConvertTo-Json -Depth 5
    exit 0
  }
  $rowCount = 0
  $columnCount = 0
  try {
    if ($areaCount -eq 1) {
      $rowCount = [int]$sel.Rows.Count
      $columnCount = [int]$sel.Columns.Count
    }
  } catch { }
  $flatValues = $null
  if ($mode -eq 'matrix') {
    $expectedRows = [int]$params.row_count
    $expectedCols = [int]$params.column_count
    if ($areaCount -eq 1 -and ($rowCount -ne $expectedRows -or $columnCount -ne $expectedCols)) {
      [pscustomobject]@{
        ok = $true
        status = 'selection_changed'
        current_rows = $rowCount
        current_columns = $columnCount
      } | ConvertTo-Json -Depth 5
      exit 0
    }
    $flatValues = New-Object System.Collections.Generic.List[object]
    foreach ($row in $params.values) {
      foreach ($value in $row) { $flatValues.Add($value) }
    }
    if ($flatValues.Count -ne $cellCount) {
      [pscustomobject]@{
        ok = $true
        status = 'selection_changed'
        current_cell_count = $cellCount
        values_cell_count = $flatValues.Count
      } | ConvertTo-Json -Depth 5
      exit 0
    }
    $index = 0
    foreach ($area in $sel.Areas) {
      foreach ($cell in $area.Cells) {
        $value = $flatValues[$index]
        if ($null -eq $value) { $cell.Value2 = $null }
        else { $cell.Value2 = [string]$value }
        $index++
      }
    }
  } else {
    $replacement = [string]$params.text
    foreach ($area in $sel.Areas) {
      $area.Value2 = $replacement
    }
  }
  $doc.Save()
  $allMatch = $true
  $readBack = ''
  $readParts = New-Object System.Collections.Generic.List[string]
  if ($mode -eq 'matrix') {
    $index = 0
    foreach ($area in $sel.Areas) {
      foreach ($cell in $area.Cells) {
        $cellText = ''
        try { $cellText = [string]$cell.Text } catch { }
        if ($index -eq 0) { $readBack = $cellText }
        $expected = $flatValues[$index]
        $expectedText = if ($null -eq $expected) { '' } else { [string]$expected }
        $readParts.Add($cellText)
        if (-not (Test-CellTextMatch $cellText $expectedText)) { $allMatch = $false }
        $index++
      }
    }
  } else {
    $replacement = [string]$params.text
    $index = 0
    foreach ($area in $sel.Areas) {
      foreach ($cell in $area.Cells) {
        $cellText = ''
        try { $cellText = [string]$cell.Text } catch { }
        if ($index -eq 0) { $readBack = $cellText }
        $readParts.Add($cellText)
        if (-not (Test-CellTextMatch $cellText $replacement)) { $allMatch = $false }
        $index++
      }
    }
  }
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'spreadsheets'
    address = $address
    cell_count = $cellCount
    area_count = $areaCount
    row_count = $rowCount
    column_count = $columnCount
    cells_matched = [bool]$allMatch
    read_back_text = [string]$readBack
    read_back_values = $readParts
  } | ConvertTo-Json -Depth 5
"""

_SPREADSHEET_SELECTION_DELETE_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ([bool]$doc.ReadOnly) {
    [pscustomobject]@{ ok = $true; status = 'read_only' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $window = $null
  try {
    if ([int]$doc.Windows.Count -ge 1) { $window = $doc.Windows.Item(1) }
  } catch { }
  if ($null -eq $window) {
    try {
      $active = $app.ActiveWorkbook
      if ($null -ne $active -and [string]::Equals(
        [System.IO.Path]::GetFullPath([string]$active.FullName),
        [System.IO.Path]::GetFullPath([string]$params.path),
        [System.StringComparison]::OrdinalIgnoreCase
      )) { $window = $app.ActiveWindow }
    } catch { }
  }
  if ($null -eq $window) {
    [pscustomobject]@{ ok = $true; status = 'no_window' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $sel = $null
  try { $sel = $window.Selection } catch { }
  if ($null -eq $sel) {
    try { $sel = $window.RangeSelection } catch { }
  }
  $address = $null
  $cellCount = 0
  $areaCount = 0
  try {
    $address = [string]$sel.Address($true, $true)
    $cellCount = [int]$sel.Cells.Count
    $areaCount = [int]$sel.Areas.Count
  } catch {
    [pscustomobject]@{ ok = $true; status = 'not_cell_selection' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $maxCells = [int]$params.max_cells
  if ($areaCount -lt 1 -or $cellCount -lt 1 -or $cellCount -gt $maxCells) {
    [pscustomobject]@{
      ok = $true
      status = 'not_cell_selection'
      cell_count = $cellCount
      area_count = $areaCount
    } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ($address -cne [string]$params.expected_address) {
    [pscustomobject]@{ ok = $true; status = 'selection_changed'; current_address = $address } | ConvertTo-Json -Depth 5
    exit 0
  }
  $parts = New-Object System.Collections.Generic.List[string]
  foreach ($area in $sel.Areas) {
    foreach ($cell in $area.Cells) {
      try { $parts.Add([string]$cell.Text) } catch { $parts.Add('') }
    }
  }
  $before = [string]::Join("`t", $parts)
  if ($before -cne [string]$params.expected_text) {
    [pscustomobject]@{ ok = $true; status = 'selection_changed'; current_text = $before } | ConvertTo-Json -Depth 5
    exit 0
  }
  foreach ($area in $sel.Areas) {
    try { [void]$area.ClearContents() }
    catch {
      foreach ($cell in $area.Cells) { $cell.Value2 = $null }
    }
  }
  $doc.Save()
  $allEmpty = $true
  $readBack = ''
  $readParts = New-Object System.Collections.Generic.List[string]
  $index = 0
  foreach ($area in $sel.Areas) {
    foreach ($cell in $area.Cells) {
      $cellText = ''
      try { $cellText = [string]$cell.Text } catch { }
      if ($index -eq 0) { $readBack = $cellText }
      $readParts.Add($cellText)
      if (-not [string]::IsNullOrEmpty($cellText)) { $allEmpty = $false }
      $index++
    }
  }
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'spreadsheets'
    address = $address
    cell_count = $cellCount
    area_count = $areaCount
    cells_matched = [bool]$allEmpty
    deleted_text = [string]$params.expected_text
    read_back_text = [string]$readBack
    read_back_values = $readParts
  } | ConvertTo-Json -Depth 5
"""
