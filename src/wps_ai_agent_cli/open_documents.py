from __future__ import annotations

import glob
import json
import re
from pathlib import Path
from typing import Any

from .backups import create_backup, guarded_com_mutation, verify_post_com_source
from .capabilities import WPS_COMPONENTS
from .errors import COM_OPERATION_FAILED, INPUT_FILE_NOT_FOUND
from .mutation_lock import coordinated_mutation, coordinated_request
from .operations import record_operation, replay_operation
from .powershell_runner import run_powershell_script
from .sessions import file_identity, get_document, register_document, stable_document_id
from .wps_script_snippets import ATTACH_RUNNING_INSTANCE


MAX_SELECTION_CHARS = 4096
MAX_SPREADSHEET_SELECTION_SAMPLE_CELLS = 100
HTML_EXPORT_SUFFIXES = {".html", ".htm"}
PDF_EXPORT_SUFFIXES = {".pdf"}
TEXT_EXPORT_SUFFIXES = {".txt"}
SAVE_AS_NATIVE_SUFFIXES = {
    "writer": {".docx"},
    "spreadsheets": {".xlsx"},
    "presentation": {".pptx"},
}

_COMPONENT_COLLECTIONS = {
    "writer": ("Documents", "ActiveDocument"),
    "spreadsheets": ("Workbooks", "ActiveWorkbook"),
    "presentation": ("Presentations", "ActivePresentation"),
}

NO_RUNNING_WPS_INSTANCE = "NO_RUNNING_WPS_INSTANCE"
DOCUMENT_NOT_OPEN = "DOCUMENT_NOT_OPEN"
DOCUMENT_HAS_UNSAVED_CHANGES = "DOCUMENT_HAS_UNSAVED_CHANGES"
DOCUMENT_READ_ONLY = "DOCUMENT_READ_ONLY"
SELECTION_UNAVAILABLE = "SELECTION_UNAVAILABLE"
SELECTION_EMPTY = "SELECTION_EMPTY"
SELECTION_NOT_COLLAPSED = "SELECTION_NOT_COLLAPSED"
SELECTION_MISMATCH = "SELECTION_MISMATCH"
SELECTION_TOO_LARGE = "SELECTION_TOO_LARGE"
SELECTION_SPANS_STRUCTURE = "SELECTION_SPANS_STRUCTURE"
OBJECT_SELECTION_UNSUPPORTED = "OBJECT_SELECTION_UNSUPPORTED"
UNTITLED_DOCUMENT_NOT_FOUND = "UNTITLED_DOCUMENT_NOT_FOUND"
AMBIGUOUS_OPEN_DOCUMENT = "AMBIGUOUS_OPEN_DOCUMENT"
DOCUMENT_ALREADY_PATHED = "DOCUMENT_ALREADY_PATHED"
UNSUPPORTED_OUTPUT_EXTENSION = "UNSUPPORTED_OUTPUT_EXTENSION"
OUTPUT_EXISTS = "OUTPUT_EXISTS"
EXPORT_OUTPUT_MISSING = "EXPORT_OUTPUT_MISSING"
EXPORT_OUTPUT_NOT_HTML = "EXPORT_OUTPUT_NOT_HTML"
EXPORT_OUTPUT_NOT_PDF = "EXPORT_OUTPUT_NOT_PDF"
EXPORT_OUTPUT_NOT_PACKAGE = "EXPORT_OUTPUT_NOT_PACKAGE"
EXPORT_OUTPUT_NOT_TEXT = "EXPORT_OUTPUT_NOT_TEXT"

OOXML_PACKAGE_SUFFIXES = {".docx", ".xlsx", ".pptx"}

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
        if ($cellText -cne $expectedText) { $allMatch = $false }
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
        if ($cellText -cne $replacement) { $allMatch = $false }
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


def _render(script: str, params: dict[str, Any]) -> str:
    return script.replace("__PARAMS_JSON__", json.dumps(params))


def _run_script(script: str, params: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    payload, failure = run_powershell_script(_render(script, params), timeout_seconds=timeout_seconds)
    if failure is not None:
        return failure
    return {"ok": True, "errors": [], "data": payload}


def _writer_prog_ids() -> list[str]:
    return list(WPS_COMPONENTS["writer"])


def _run_open_documents_com(components: list[str]) -> dict[str, Any]:
    specs = [
        {
            "component": name,
            "prog_ids": list(WPS_COMPONENTS[name]),
            "collection": _COMPONENT_COLLECTIONS[name][0],
            "active": _COMPONENT_COLLECTIONS[name][1],
        }
        for name in components
    ]
    return _run_script(_LIST_SCRIPT, {"components": specs}, timeout_seconds=60)


def _run_save_as_untitled_com(component: str, name: str, output: str, *, do_save: bool) -> dict[str, Any]:
    collection, _active = _COMPONENT_COLLECTIONS[component]
    prog_ids = list(WPS_COMPONENTS[component])
    return _run_script(
        _SAVE_AS_UNTITLED_SCRIPT,
        {
            "prog_ids": prog_ids,
            "collection": collection,
            "component": component,
            "name": name,
            "output": output,
            "do_save": do_save,
        },
        timeout_seconds=120,
    )


def _run_writer_attached_com(action: str, params: dict[str, Any]) -> dict[str, Any]:
    body = {
        "selection-read": _SELECTION_READ_BODY,
        "selection-replace": _SELECTION_REPLACE_BODY,
        "selection-insert": _SELECTION_INSERT_BODY,
        "selection-delete": _SELECTION_DELETE_BODY,
        "save": _DOCUMENT_SAVE_BODY,
        "export-html": _EXPORT_HTML_BODY,
        "export-pdf": _EXPORT_PDF_BODY,
        "export-copy": _EXPORT_COPY_BODY,
        "export-text": _EXPORT_TEXT_BODY,
    }[action]
    script = _ATTACHED_WRITER_WRAPPER.replace("__ACTION_BODY__", body)
    return _run_script(script, {"prog_ids": _writer_prog_ids(), **params}, timeout_seconds=120)


def _presentation_prog_ids() -> list[str]:
    return list(WPS_COMPONENTS["presentation"])


def _run_presentation_attached_com(action: str, params: dict[str, Any]) -> dict[str, Any]:
    body = {
        "export-html": _PRESENTATION_EXPORT_HTML_BODY,
        "export-pdf": _PRESENTATION_EXPORT_PDF_BODY,
        "export-copy": _PRESENTATION_EXPORT_COPY_BODY,
        "export-text": _PRESENTATION_EXPORT_TEXT_BODY,
        "selection-read": _PRESENTATION_SELECTION_READ_BODY,
        "selection-replace": _PRESENTATION_SELECTION_REPLACE_BODY,
        "selection-insert": _PRESENTATION_SELECTION_INSERT_BODY,
        "selection-delete": _PRESENTATION_SELECTION_DELETE_BODY,
        "save": _DOCUMENT_SAVE_BODY,
    }[action]
    script = _ATTACHED_PRESENTATION_WRAPPER.replace("__ACTION_BODY__", body)
    return _run_script(script, {"prog_ids": _presentation_prog_ids(), **params}, timeout_seconds=120)


def _spreadsheet_prog_ids() -> list[str]:
    return list(WPS_COMPONENTS["spreadsheets"])


def _run_spreadsheet_attached_com(action: str, params: dict[str, Any]) -> dict[str, Any]:
    body = {
        "selection-read": _SPREADSHEET_SELECTION_READ_BODY,
        "selection-replace": _SPREADSHEET_SELECTION_REPLACE_BODY,
        "selection-delete": _SPREADSHEET_SELECTION_DELETE_BODY,
        "selection-shape-replace": _SPREADSHEET_SHAPE_TEXT_REPLACE_BODY,
        "selection-shape-delete": _SPREADSHEET_SHAPE_TEXT_DELETE_BODY,
        "selection-chart-title-replace": _SPREADSHEET_CHART_TITLE_REPLACE_BODY,
        "selection-chart-title-delete": _SPREADSHEET_CHART_TITLE_DELETE_BODY,
        "selection-axis-title-replace": _SPREADSHEET_AXIS_TITLE_REPLACE_BODY,
        "selection-axis-title-delete": _SPREADSHEET_AXIS_TITLE_DELETE_BODY,
        "selection-series-values-replace": _SPREADSHEET_SERIES_VALUES_REPLACE_BODY,
        "selection-series-values-delete": _SPREADSHEET_SERIES_VALUES_DELETE_BODY,
        "export-html": _SPREADSHEET_EXPORT_HTML_BODY,
        "export-pdf": _SPREADSHEET_EXPORT_PDF_BODY,
        "export-copy": _SPREADSHEET_EXPORT_COPY_BODY,
        "export-text": _SPREADSHEET_EXPORT_TEXT_BODY,
        "save": _DOCUMENT_SAVE_BODY,
    }[action]
    script = _ATTACHED_SPREADSHEET_WRAPPER.replace("__ACTION_BODY__", body)
    return _run_script(script, {"prog_ids": _spreadsheet_prog_ids(), **params}, timeout_seconds=120)


def _run_component_attached_com(component: str, action: str, params: dict[str, Any]) -> dict[str, Any]:
    if component == "writer":
        return _run_writer_attached_com(action, params)
    if component == "presentation":
        return _run_presentation_attached_com(action, params)
    return _run_spreadsheet_attached_com(action, params)


def _status_error(
    status: str | None,
    path: str,
    component: str = "writer",
    *,
    action: str = "modified",
) -> dict[str, str] | None:
    if status == "ok":
        return None
    if status == "unsaved":
        return _unsaved_open_document_error(action)
    label = {
        "writer": "Writer",
        "presentation": "Presentation",
        "spreadsheets": "Spreadsheets",
    }.get(component, component)
    read_only_by_action = {
        "exported": "The open document is read-only, so it cannot be exported through this command.",
        "saved": "The open document is read-only, so it cannot be saved through save-open-document.",
        "replaced": "The open document is read-only, so its selection cannot be replaced.",
        "inserted into": "The open document is read-only, so text cannot be inserted at the selection.",
        "cleared": "The open document is read-only, so its selection cannot be cleared.",
    }
    messages = {
        "no_instance": (
            NO_RUNNING_WPS_INSTANCE,
            f"No running WPS {label} instance was found. Open the document in WPS first; this command never launches WPS or closes a running instance.",
        ),
        "not_open": (
            DOCUMENT_NOT_OPEN,
            f"The registered document is not open in the running WPS {label} instance: {path}",
        ),
        "read_only": (
            DOCUMENT_READ_ONLY,
            read_only_by_action.get(
                action,
                "The open document is read-only, so its selection cannot be replaced.",
            ),
        ),
        "no_window": (SELECTION_UNAVAILABLE, "The open document has no active window, so there is no selection to use."),
        "not_text_selection": (
            SELECTION_SPANS_STRUCTURE,
            "The active selection is not a text range; select plain text inside a shape before replacing.",
        ),
        "not_cell_selection": (
            SELECTION_SPANS_STRUCTURE,
            "Only a cell/range selection of at most 100 cells can be replaced; matrix writes require a single contiguous area.",
        ),
        "selection_changed": (
            SELECTION_MISMATCH,
            "The selection or its text changed between preview and write; no change was made.",
        ),
        "not_collapsed": (
            SELECTION_NOT_COLLAPSED,
            "The selection is not collapsed to a caret; collapse it before inserting, or use writer-selection-replace to replace selected text.",
        ),
        "not_shape_selection": (
            OBJECT_SELECTION_UNSUPPORTED,
            "The active selection is not a worksheet shape with editable text; select a text-bearing shape or worksheet cells.",
        ),
        "no_text_frame": (
            OBJECT_SELECTION_UNSUPPORTED,
            "The selected shape has no editable TextFrame; chart/shape geometry mutation is not supported.",
        ),
        "not_chart_selection": (
            OBJECT_SELECTION_UNSUPPORTED,
            "The active selection is not a worksheet chart; select a chart with an accessible title or worksheet cells.",
        ),
        "no_chart_title": (
            OBJECT_SELECTION_UNSUPPORTED,
            "The selected chart has no editable ChartTitle; series-value mutation is not supported.",
        ),
        "not_axis_title_selection": (
            OBJECT_SELECTION_UNSUPPORTED,
            "The active selection is not a chart AxisTitle; select an axis title, chart title, or worksheet cells.",
        ),
        "no_axis_title": (
            OBJECT_SELECTION_UNSUPPORTED,
            "The selected axis has no editable AxisTitle; select a title, series, or worksheet cells.",
        ),
        "not_series_selection": (
            OBJECT_SELECTION_UNSUPPORTED,
            "The active selection is not a chart Series; select a series, chart/axis title, or worksheet cells.",
        ),
        "no_series_values": (
            OBJECT_SELECTION_UNSUPPORTED,
            "The selected series has no editable Values; geometry mutation is not supported.",
        ),
        "series_length_mismatch": (
            "RANGE_SHAPE_MISMATCH",
            "Series replacement value count must match the selected series point count (TAB-joined).",
        ),
    }
    code, message = messages.get(str(status), (COM_OPERATION_FAILED, f"Unexpected attach status: {status}"))
    return {"code": code, "message": message}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _validate_text(text: str, label: str) -> dict[str, str] | None:
    if len(text) > MAX_SELECTION_CHARS or any(ord(char) < 32 or ord(char) == 127 for char in text):
        return {
            "code": "INVALID_ARGUMENT",
            "message": f"{label} must be at most {MAX_SELECTION_CHARS} characters on one line without control characters.",
        }
    return None


FORMULA_PREFIXES = ("=", "+", "-", "@")
_PLAIN_NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")


def _formula_prefix_error(text: str, label: str) -> dict[str, str] | None:
    """Cell text starting with a formula trigger would be evaluated by WPS; formulas need their own command.

    Plain signed numbers such as -5 or +0.5 are data, not formulas.
    """
    if text.startswith(FORMULA_PREFIXES) and not _PLAIN_NUMBER.fullmatch(text):
        return {
            "code": "FORMULA_PREFIX_REJECTED",
            "message": f"{label} starts with {text[0]!r}; use spreadsheet-formula-write for formulas.",
        }
    return None


def _validate_spreadsheet_expected_text(text: str, label: str) -> dict[str, str] | None:
    """Like _validate_text, but TAB is allowed as the multi-cell sample delimiter."""
    if len(text) > MAX_SELECTION_CHARS:
        return {
            "code": "INVALID_ARGUMENT",
            "message": f"{label} must be at most {MAX_SELECTION_CHARS} characters.",
        }
    for char in text:
        if char == "\t":
            continue
        if ord(char) < 32 or ord(char) == 127:
            return {
                "code": "INVALID_ARGUMENT",
                "message": f"{label} must be a single-line value without control characters (TAB allowed only as a multi-cell sample delimiter).",
            }
    return None


def _parse_selection_values_matrix(values: Any) -> tuple[list[list[str | None]] | None, dict[str, str] | None]:
    if not isinstance(values, list) or not values:
        return None, {"code": "INVALID_ARGUMENT", "message": "values_json must be a nonempty rectangular 2D array."}
    width = None
    matrix: list[list[str | None]] = []
    for row_index, row in enumerate(values):
        if not isinstance(row, list) or not row:
            return None, {"code": "INVALID_ARGUMENT", "message": "values_json must be a nonempty rectangular 2D array."}
        if width is None:
            width = len(row)
        elif len(row) != width:
            return None, {"code": "INVALID_ARGUMENT", "message": "values_json must be a rectangular 2D array."}
        normalized_row: list[str | None] = []
        for column_index, value in enumerate(row):
            if value is None:
                normalized_row.append(None)
                continue
            if isinstance(value, bool) or not isinstance(value, (str, int, float)):
                return None, {
                    "code": "INVALID_ARGUMENT",
                    "message": f"values_json cell ({row_index + 1},{column_index + 1}) must be null, string, or finite number.",
                }
            if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
                return None, {
                    "code": "INVALID_ARGUMENT",
                    "message": f"values_json cell ({row_index + 1},{column_index + 1}) must be a finite number.",
                }
            text = str(value)
            invalid = _validate_text(text, f"values_json cell ({row_index + 1},{column_index + 1})")
            if invalid:
                return None, invalid
            prefix_error = _formula_prefix_error(text, f"values_json cell ({row_index + 1},{column_index + 1})")
            if prefix_error:
                return None, prefix_error
            normalized_row.append(text)
        matrix.append(normalized_row)
    return matrix, None


def _registered_document(
    document_id: str,
    workspace: str | Path,
    *,
    allowed_components: set[str],
) -> tuple[dict[str, Any] | None, dict[str, Any], list[dict[str, str]]]:
    document = get_document(document_id, workspace)
    if not document:
        return None, {}, [{"code": "DOCUMENT_NOT_FOUND", "message": f"Document not registered: {document_id}"}]
    if document["component"] not in allowed_components:
        allowed = ", ".join(sorted(allowed_components))
        return None, {"document": document}, [
            {
                "code": "UNSUPPORTED_COMPONENT",
                "message": f"This command requires a registered document in: {allowed}.",
            }
        ]
    if not Path(document["path"]).exists():
        return None, {"document": document}, [
            {"code": INPUT_FILE_NOT_FOUND, "message": f"Input file not found: {document['path']}"}
        ]
    return document, {}, []


def _writer_document(document_id: str, workspace: str | Path) -> tuple[dict[str, Any] | None, dict[str, Any], list[dict[str, str]]]:
    return _registered_document(document_id, workspace, allowed_components={"writer"})


def list_open_documents(
    component: str | None = None,
    register: bool = False,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    if component is not None and component not in WPS_COMPONENTS:
        return False, {}, [{"code": "UNSUPPORTED_COMPONENT", "message": f"Unsupported component: {component}"}]
    components = [component] if component else list(WPS_COMPONENTS)

    result = _run_open_documents_com(components)
    if not result["ok"]:
        return False, {"probed_components": components, **result["data"]}, result["errors"]
    payload = result["data"] or {}
    if payload.get("ok") is False:
        return False, {"probed_components": components, "diagnostic": payload}, [
            {"code": COM_OPERATION_FAILED, "message": str(payload.get("error_message") or "Attach failed.")}
        ]

    instances = []
    documents: list[dict[str, Any]] = []
    for instance in _as_list(payload.get("instances")):
        name = instance.get("component")
        entries = []
        for item in _as_list(instance.get("documents")):
            full_name = item.get("full_name") or ""
            path_exists = bool(full_name) and Path(full_name).is_file()
            entry = {
                "component": name,
                "name": item.get("name"),
                "full_name": full_name,
                "saved": item.get("saved"),
                "read_only": item.get("read_only"),
                "active": bool(item.get("active")),
                "path_exists": path_exists,
                "document_id": None,
                "registered": False,
            }
            if path_exists:
                known = get_document(stable_document_id(name, full_name), workspace)
                if known is None and register:
                    ok, record, errors = register_document(name, full_name, workspace)
                    entry["register_errors"] = errors if not ok else []
                    known = record if ok else None
                if known is not None:
                    entry["document_id"] = known["document_id"]
                    entry["registered"] = True
            entries.append(entry)
        instances.append({"component": name, "version": instance.get("version"), "document_count": len(entries)})
        documents.extend(entries)

    data = {
        "probed_components": components,
        "instances": instances,
        "documents": documents,
        "attached_without_launching": True,
        "note": (
            "Documents are matched by path; unsaved or untitled documents have no stable document_id "
            "until saved with save-as-open-document. Use document_id for pathed documents; "
            "use save-as-open-document with --component/--name/--output for untitled documents."
        ),
    }
    if not instances:
        return False, data, [
            {"code": NO_RUNNING_WPS_INSTANCE, "message": "No running WPS instance was found for the probed components; nothing was launched."}
        ]
    return True, data, []


def read_writer_selection(
    document_id: str,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    document, data, errors = _writer_document(document_id, workspace)
    if document is None:
        return False, data, errors
    path = str(Path(document["path"]).resolve())
    result = _run_writer_attached_com("selection-read", {"path": path})
    if not result["ok"]:
        return False, {"document_id": document_id, "path": path, **result["data"]}, result["errors"]
    payload = result["data"] or {}
    if payload.get("ok") is False:
        return False, {"document_id": document_id, "path": path, "diagnostic": payload}, [
            {"code": COM_OPERATION_FAILED, "message": str(payload.get("error_message") or "Selection read failed.")}
        ]
    error = _status_error(payload.get("status"), path)
    if error:
        return False, {"document_id": document_id, "path": path}, [error]

    text = str(payload.get("selection_text") or "")
    start, end = int(payload["start"]), int(payload["end"])
    return True, {
        "document_id": document_id,
        "component": "writer",
        "path": path,
        "saved": payload.get("saved"),
        "read_only": bool(payload.get("read_only")),
        "start": start,
        "end": end,
        "collapsed": start == end,
        "selection_length": end - start,
        "selection_text": text[:MAX_SELECTION_CHARS],
        "selection_text_truncated": len(text) > MAX_SELECTION_CHARS,
        "paragraph_index": payload.get("paragraph_index"),
        "page_number": payload.get("page_number"),
        "page_info_verified": False,
        "page_note": "Page is not a first-class object; page_number comes from the selection's active end and is unverified on this WPS version. Target content (selection, paragraph, bookmark, keyword) rather than page numbers.",
    }, []


def read_presentation_selection(
    document_id: str,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    document, data, errors = _registered_document(
        document_id, workspace, allowed_components={"presentation"},
    )
    if document is None:
        return False, data, errors
    path = str(Path(document["path"]).resolve())
    result = _run_presentation_attached_com("selection-read", {"path": path})
    if not result["ok"]:
        return False, {"document_id": document_id, "path": path, **result["data"]}, result["errors"]
    payload = result["data"] or {}
    if payload.get("ok") is False:
        return False, {"document_id": document_id, "path": path, "diagnostic": payload}, [
            {"code": COM_OPERATION_FAILED, "message": str(payload.get("error_message") or "Selection read failed.")}
        ]
    error = _status_error(payload.get("status"), path, component="presentation")
    if error:
        return False, {"document_id": document_id, "path": path}, [error]

    text = str(payload.get("selection_text") or "")
    text_range_length = payload.get("text_range_length")
    if text_range_length is not None:
        try:
            text_range_length = int(text_range_length)
        except (TypeError, ValueError):
            text_range_length = None
    text_range_start = payload.get("text_range_start")
    if text_range_start is not None:
        try:
            text_range_start = int(text_range_start)
        except (TypeError, ValueError):
            text_range_start = None
    kind = payload.get("selection_kind") or "unknown"
    collapsed = bool(payload.get("collapsed"))
    if kind == "text" and text_range_length is not None:
        collapsed = text_range_length == 0
    return True, {
        "document_id": document_id,
        "component": "presentation",
        "path": path,
        "saved": payload.get("saved"),
        "read_only": bool(payload.get("read_only")),
        "selection_kind": kind,
        "selection_type": payload.get("selection_type"),
        "selection_text": text[:MAX_SELECTION_CHARS],
        "selection_text_truncated": len(text) > MAX_SELECTION_CHARS,
        "text_range_start": text_range_start,
        "text_range_length": text_range_length,
        "collapsed": collapsed,
        "slide_index": payload.get("slide_index"),
        "shape_name": payload.get("shape_name"),
        "shape_count": int(payload.get("shape_count") or 0),
        "slide_info_verified": False,
        "slide_note": "slide_index is best-effort from the active selection and is unverified across layouts, masters, and hidden slides. Prefer shape text or slide-scoped replace rather than slide numbers alone.",
    }, []


def read_spreadsheet_selection(
    document_id: str,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    document, data, errors = _registered_document(
        document_id, workspace, allowed_components={"spreadsheets"},
    )
    if document is None:
        return False, data, errors
    path = str(Path(document["path"]).resolve())
    result = _run_spreadsheet_attached_com("selection-read", {"path": path})
    if not result["ok"]:
        return False, {"document_id": document_id, "path": path, **result["data"]}, result["errors"]
    payload = result["data"] or {}
    if payload.get("ok") is False:
        return False, {"document_id": document_id, "path": path, "diagnostic": payload}, [
            {"code": COM_OPERATION_FAILED, "message": str(payload.get("error_message") or "Selection read failed.")}
        ]
    error = _status_error(payload.get("status"), path, component="spreadsheets")
    if error:
        return False, {"document_id": document_id, "path": path}, [error]

    text = str(payload.get("selection_text") or "")
    sample_truncated = bool(payload.get("sample_truncated"))
    object_kind = payload.get("object_kind")
    object_name = payload.get("object_name")
    if object_kind is not None:
        object_kind = str(object_kind) or None
    if object_name is not None:
        object_name = str(object_name) or None
    return True, {
        "document_id": document_id,
        "component": "spreadsheets",
        "path": path,
        "saved": payload.get("saved"),
        "read_only": bool(payload.get("read_only")),
        "selection_kind": payload.get("selection_kind") or "unknown",
        "address": payload.get("address"),
        "sheet_name": payload.get("sheet_name"),
        "cell_count": int(payload.get("cell_count") or 0),
        "area_count": int(payload.get("area_count") or 0),
        "row_count": int(payload.get("row_count") or 0),
        "column_count": int(payload.get("column_count") or 0),
        "selection_text": text[:MAX_SELECTION_CHARS],
        "selection_text_truncated": len(text) > MAX_SELECTION_CHARS or sample_truncated,
        "formula": payload.get("formula"),
        "object_kind": object_kind,
        "object_name": object_name,
        "has_text_frame": bool(payload.get("has_text_frame")),
        "has_chart_title": bool(payload.get("has_chart_title")),
        "has_axis_title": bool(payload.get("has_axis_title")),
        "has_series_values": bool(payload.get("has_series_values")),
        "series_name": (str(payload.get("series_name")) or None) if payload.get("series_name") is not None else None,
        "object_info_verified": False,
        "object_note": (
            "object_kind/object_name/has_text_frame/has_chart_title/has_axis_title/has_series_values are best-effort for non-range selections. "
            "Worksheet shape TextFrame, chart ChartTitle, AxisTitle, and selected Series Values may be replaced or cleared when those flags are true; "
            "shape geometry mutation remains unsupported. Unverified across WPS versions."
        ),
        "sample_cell_limit": MAX_SPREADSHEET_SELECTION_SAMPLE_CELLS,
        "note": "selection_text samples at most 100 cells for multi-cell ranges; prefer address + spreadsheet-read for full values.",
    }, []


def _check_replaceable_selection(selection: dict[str, Any], expected: str | None) -> dict[str, str] | None:
    text = selection["selection_text"]
    if selection["collapsed"]:
        return {"code": SELECTION_EMPTY, "message": "The selection is empty; select the text to replace first."}
    if selection["selection_length"] > MAX_SELECTION_CHARS or selection["selection_text_truncated"]:
        return {"code": SELECTION_TOO_LARGE, "message": f"The selection is longer than {MAX_SELECTION_CHARS} characters."}
    if any(ord(char) < 32 or ord(char) == 127 for char in text):
        return {
            "code": SELECTION_SPANS_STRUCTURE,
            "message": "The selection includes paragraph, line, table-cell or other control marks; shrink it to plain text within one paragraph.",
        }
    if selection["selection_length"] != len(text):
        return {
            "code": SELECTION_SPANS_STRUCTURE,
            "message": "The selection contains non-text objects such as fields or drawings; shrink it to plain text.",
        }
    if expected is not None and expected != text:
        return {"code": SELECTION_MISMATCH, "message": "The current selection text does not match expected_selection_text."}
    return None


def _check_replaceable_presentation_selection(
    selection: dict[str, Any],
    expected: str | None,
    *,
    operation: str = "replace",
) -> dict[str, str] | None:
    kind = selection.get("selection_kind") or "unknown"
    text = str(selection.get("selection_text") or "")
    if operation == "delete":
        verb_past = "cleared"
        verb_inf = "clear"
    else:
        verb_past = "replaced"
        verb_inf = "replace"
    if kind != "text":
        if kind in {"none", "unknown"} and not text:
            return {
                "code": SELECTION_EMPTY,
                "message": f"The selection is empty; select the text to {verb_inf} first.",
            }
        return {
            "code": SELECTION_SPANS_STRUCTURE,
            "message": (
                f"Only a text selection inside a shape can be {verb_past}; "
                "shrink the selection to plain text."
            ),
        }
    if not text:
        return {
            "code": SELECTION_EMPTY,
            "message": f"The selection is empty; select the text to {verb_inf} first.",
        }
    if selection.get("selection_text_truncated") or len(text) > MAX_SELECTION_CHARS:
        return {"code": SELECTION_TOO_LARGE, "message": f"The selection is longer than {MAX_SELECTION_CHARS} characters."}
    if any(ord(char) < 32 or ord(char) == 127 for char in text):
        return {
            "code": SELECTION_SPANS_STRUCTURE,
            "message": "The selection includes control characters; shrink it to a single plain-text run.",
        }
    if expected is not None and expected != text:
        return {"code": SELECTION_MISMATCH, "message": "The current selection text does not match expected_selection_text."}
    return None


def _check_replaceable_spreadsheet_selection(
    selection: dict[str, Any],
    expected: str | None,
    *,
    operation: str = "replace",
) -> dict[str, str] | None:
    kind = selection.get("selection_kind") or "unknown"
    text = str(selection.get("selection_text") or "")
    cell_count = int(selection.get("cell_count") or 0)
    area_count = int(selection.get("area_count") or 0)
    object_kind = selection.get("object_kind")
    object_name = selection.get("object_name")
    if operation == "delete":
        verb_past = "cleared"
        verb_ing = "clearing"
        verb_inf = "clear"
    else:
        verb_past = "replaced"
        verb_ing = "replacing"
        verb_inf = "replace"
    if kind == "non_range" and object_kind == "chart":
        has_chart_title = bool(selection.get("has_chart_title"))
        has_axis_title = bool(selection.get("has_axis_title"))
        has_series_values = bool(selection.get("has_series_values"))
        if not has_chart_title and not has_axis_title and not has_series_values:
            label = f"chart: {object_name}" if object_name else "chart"
            return {
                "code": OBJECT_SELECTION_UNSUPPORTED,
                "message": (
                    f"Chart selections ({label}) without editable Series Values, ChartTitle, or AxisTitle cannot be {verb_past}; "
                    "select a series, chart/axis title, a text-bearing shape, or worksheet cells. "
                    "Geometry mutation is not supported."
                ),
            }
        if has_series_values:
            point_count = len(text.split("\t")) if text else 0
            if selection.get("selection_text_truncated") or point_count > MAX_SPREADSHEET_SELECTION_SAMPLE_CELLS:
                return {
                    "code": SELECTION_TOO_LARGE,
                    "message": (
                        f"The series has more than {MAX_SPREADSHEET_SELECTION_SAMPLE_CELLS} values; "
                        f"shrink the series or edit source cells instead."
                    ),
                }
            if len(text) > MAX_SELECTION_CHARS:
                return {
                    "code": SELECTION_TOO_LARGE,
                    "message": f"The series values sample is longer than {MAX_SELECTION_CHARS} characters.",
                }
            if expected is not None and expected != text:
                return {
                    "code": SELECTION_MISMATCH,
                    "message": "The current series values do not match expected_selection_text.",
                }
            return None
        title_label = "axis title" if has_axis_title else "chart title"
        if selection.get("selection_text_truncated") or len(text) > MAX_SELECTION_CHARS:
            return {
                "code": SELECTION_TOO_LARGE,
                "message": f"The {title_label} is longer than {MAX_SELECTION_CHARS} characters.",
            }
        if expected is not None and expected != text:
            return {
                "code": SELECTION_MISMATCH,
                "message": f"The current {title_label} does not match expected_selection_text.",
            }
        return None
    if kind == "non_range" and object_kind == "shape":
        if not selection.get("has_text_frame"):
            label = f"shape: {object_name}" if object_name else "shape"
            return {
                "code": OBJECT_SELECTION_UNSUPPORTED,
                "message": (
                    f"Shape selections ({label}) without an editable TextFrame cannot be {verb_past}; "
                    "select a text-bearing shape or worksheet cells. Geometry mutation is not supported."
                ),
            }
        if selection.get("selection_text_truncated") or len(text) > MAX_SELECTION_CHARS:
            return {
                "code": SELECTION_TOO_LARGE,
                "message": f"The shape text is longer than {MAX_SELECTION_CHARS} characters.",
            }
        if expected is not None and expected != text:
            return {
                "code": SELECTION_MISMATCH,
                "message": "The current shape text does not match expected_selection_text.",
            }
        return None
    if kind == "non_range" or object_kind in {"object"}:
        label = str(object_kind or "object")
        if object_name:
            label = f"{label}: {object_name}"
        return {
            "code": OBJECT_SELECTION_UNSUPPORTED,
            "message": (
                f"Non-cell selections ({label}) cannot be {verb_past}; "
                "select worksheet cells or a text-bearing shape instead."
            ),
        }
    if kind not in {"cell", "range", "multi_area"} or area_count < 1 or cell_count < 1:
        if kind in {"none", "unknown"} and not selection.get("address"):
            return {
                "code": SELECTION_EMPTY,
                "message": (
                    f"The selection is empty; select a cell, range, or multi-area selection to {verb_inf} first."
                ),
            }
        return {
            "code": SELECTION_SPANS_STRUCTURE,
            "message": (
                f"Only worksheet cell/range/multi-area selections can be {verb_past}; "
                "non-range selections are rejected."
            ),
        }
    if cell_count > MAX_SPREADSHEET_SELECTION_SAMPLE_CELLS or selection.get("selection_text_truncated"):
        return {
            "code": SELECTION_TOO_LARGE,
            "message": (
                f"The selection covers more than {MAX_SPREADSHEET_SELECTION_SAMPLE_CELLS} cells; "
                f"shrink it before {verb_ing}."
            ),
        }
    if not selection.get("address"):
        return {
            "code": SELECTION_SPANS_STRUCTURE,
            "message": (
                f"The active selection has no cell address; select a worksheet cell or range before {verb_ing}."
            ),
        }
    if len(text) > MAX_SELECTION_CHARS:
        return {"code": SELECTION_TOO_LARGE, "message": f"The selection is longer than {MAX_SELECTION_CHARS} characters."}
    # Multi-cell selection_text uses TAB as a sample delimiter; allow it only as separator.
    for char in text:
        code = ord(char)
        if char == "\t":
            continue
        if code < 32 or code == 127:
            return {
                "code": SELECTION_SPANS_STRUCTURE,
                "message": "The selection includes control characters; shrink it to plain-text cell values.",
            }
    if expected is not None and expected != text:
        return {"code": SELECTION_MISMATCH, "message": "The current selection text does not match expected_selection_text."}
    return None


@coordinated_mutation
def replace_writer_selection(
    document_id: str,
    text: str,
    request_id: str,
    expected_selection_text: str | None = None,
    dry_run: bool = False,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]], bool]:
    replay = replay_operation(
        request_id,
        "writer-selection-replace",
        {
            "document_id": document_id,
            "replacement_text": text,
            "expected_selection_text": expected_selection_text,
            "dry_run": dry_run,
        },
        workspace,
    )
    if replay is not None:
        return replay

    for value, label in ((text, "Replacement text"), (expected_selection_text, "expected_selection_text")):
        if value is not None:
            invalid = _validate_text(value, label)
            if invalid:
                return False, {}, [invalid], False

    ok, selection, errors = read_writer_selection(document_id, workspace)
    if not ok:
        return False, selection, errors, False
    if selection.get("read_only"):
        return False, {"selection": selection}, [{
            "code": DOCUMENT_READ_ONLY,
            "message": "The open document is read-only, so its selection cannot be replaced.",
        }], False
    if selection.get("saved") is False:
        return False, {"selection": selection}, [_unsaved_open_document_error("replaced")], False
    problem = _check_replaceable_selection(selection, expected_selection_text)
    if problem:
        return False, {"selection": selection}, [problem], False

    preview = {
        "document_id": document_id,
        "component": "writer",
        "path": selection["path"],
        "start": selection["start"],
        "end": selection["end"],
        "paragraph_index": selection["paragraph_index"],
        "selection_text": selection["selection_text"],
        "replacement_text": text,
        "expected_selection_text": expected_selection_text,
        "would_modify": selection["selection_text"] != text,
        "dry_run": dry_run,
    }
    if dry_run:
        return True, preview, [], False

    backup_ok, backup_result, backup_errors, backup_replayed = create_backup(
        document_id=document_id,
        request_id=f"{request_id}:backup",
        dry_run=False,
        workspace=workspace,
    )
    if not backup_ok:
        return False, {"preview": preview, "backup": backup_result}, backup_errors, False

    path = Path(selection["path"])
    write_result = guarded_com_mutation(
        path,
        backup_result,
        lambda: _run_writer_attached_com(
            "selection-replace",
            {
                "path": str(path),
                "text": text,
                "expected_start": selection["start"],
                "expected_end": selection["end"],
                "expected_text": selection["selection_text"],
            },
        ),
    )
    if not write_result["ok"]:
        return False, {"preview": preview, "backup": backup_result, "write": write_result["data"]}, write_result["errors"], False
    payload = write_result["data"]
    status_error = _status_error(payload.get("status"), str(path), action="replaced")
    if status_error:
        return False, {"preview": preview, "backup": backup_result, "write": payload}, [status_error], False

    read_back_text = payload.get("read_back_text")
    validation_passed = read_back_text == text
    result = {
        **preview,
        "dry_run": False,
        "backup": backup_result,
        "backup_replayed": backup_replayed,
        "write_backend": payload.get("backend"),
        "read_back_text": read_back_text,
        "validation_passed": validation_passed,
        "selection_preserved": False,
        "formatting_mode": payload.get("formatting_mode") or "uniform_character",
        "formatting_preserved": bool(payload.get("formatting_preserved")),
        "note": (
            "Selection text is replaced in place; uniform character formatting (font name/size/bold/italic/"
            "underline/color) is snapshotted and reapplied when WPS reports defined values. "
            "Mixed runs within the selection and paragraph-level formatting are not reconstructed. "
            "The user's selection in WPS is not restored."
        ),
    }
    post_error = verify_post_com_source(path, write_result)
    if post_error is not None:
        return False, result, [post_error], False
    if not validation_passed:
        return False, result, [
            {"code": "VALIDATION_FAILED", "message": "Selection replacement read-back did not match the replacement text."}
        ], False

    record_operation(request_id, "writer-selection-replace", result, workspace)
    return True, result, [], False


def _check_insertable_selection(selection: dict[str, Any], expected_start: int | None) -> dict[str, str] | None:
    if not selection.get("collapsed"):
        return {
            "code": SELECTION_NOT_COLLAPSED,
            "message": "The selection is not collapsed to a caret; collapse it before inserting, or use writer-selection-replace to replace selected text.",
        }
    if expected_start is not None and int(selection["start"]) != int(expected_start):
        return {
            "code": SELECTION_MISMATCH,
            "message": "The current caret position does not match expected_start.",
        }
    return None


@coordinated_mutation
def insert_writer_selection(
    document_id: str,
    text: str,
    request_id: str,
    expected_start: int | None = None,
    dry_run: bool = False,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]], bool]:
    replay = replay_operation(
        request_id,
        "writer-selection-insert",
        {
            "document_id": document_id,
            "insert_text": text,
            "expected_start": expected_start,
            "dry_run": dry_run,
        },
        workspace,
    )
    if replay is not None:
        return replay

    if not text:
        return False, {}, [{"code": "INVALID_ARGUMENT", "message": "Insert text must not be empty."}], False
    invalid = _validate_text(text, "Insert text")
    if invalid:
        return False, {}, [invalid], False

    ok, selection, errors = read_writer_selection(document_id, workspace)
    if not ok:
        return False, selection, errors, False
    if selection.get("read_only"):
        return False, {"selection": selection}, [{
            "code": DOCUMENT_READ_ONLY,
            "message": "The open document is read-only, so text cannot be inserted at the caret.",
        }], False
    if selection.get("saved") is False:
        return False, {"selection": selection}, [_unsaved_open_document_error("inserted into")], False
    problem = _check_insertable_selection(selection, expected_start)
    if problem:
        return False, {"selection": selection}, [problem], False

    preview = {
        "document_id": document_id,
        "component": "writer",
        "path": selection["path"],
        "start": selection["start"],
        "end": selection["end"],
        "paragraph_index": selection["paragraph_index"],
        "insert_text": text,
        "expected_start": expected_start,
        "would_modify": True,
        "dry_run": dry_run,
    }
    if dry_run:
        return True, preview, [], False

    backup_ok, backup_result, backup_errors, backup_replayed = create_backup(
        document_id=document_id,
        request_id=f"{request_id}:backup",
        dry_run=False,
        workspace=workspace,
    )
    if not backup_ok:
        return False, {"preview": preview, "backup": backup_result}, backup_errors, False

    path = Path(selection["path"])
    write_result = guarded_com_mutation(
        path,
        backup_result,
        lambda: _run_writer_attached_com(
            "selection-insert",
            {
                "path": str(path),
                "text": text,
                "expected_start": selection["start"],
            },
        ),
    )
    if not write_result["ok"]:
        return False, {"preview": preview, "backup": backup_result, "write": write_result["data"]}, write_result["errors"], False
    payload = write_result["data"]
    status_error = _status_error(payload.get("status"), str(path), action="inserted into")
    if status_error:
        return False, {"preview": preview, "backup": backup_result, "write": payload}, [status_error], False

    read_back_text = payload.get("read_back_text")
    validation_passed = read_back_text == text
    result = {
        **preview,
        "dry_run": False,
        "backup": backup_result,
        "backup_replayed": backup_replayed,
        "write_backend": payload.get("backend"),
        "inserted_start": payload.get("start"),
        "inserted_end": payload.get("end"),
        "read_back_text": read_back_text,
        "validation_passed": validation_passed,
        "selection_preserved": False,
        "note": "Text is inserted at the caret by position; the user's selection in WPS is not restored.",
    }
    post_error = verify_post_com_source(path, write_result)
    if post_error is not None:
        return False, result, [post_error], False
    if not validation_passed:
        return False, result, [
            {"code": "VALIDATION_FAILED", "message": "Caret insert read-back did not match the insert text."}
        ], False

    record_operation(request_id, "writer-selection-insert", result, workspace)
    return True, result, [], False


@coordinated_mutation
def delete_writer_selection(
    document_id: str,
    request_id: str,
    expected_selection_text: str | None = None,
    dry_run: bool = False,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]], bool]:
    replay = replay_operation(
        request_id,
        "writer-selection-delete",
        {
            "document_id": document_id,
            "expected_selection_text": expected_selection_text,
            "dry_run": dry_run,
        },
        workspace,
    )
    if replay is not None:
        return replay

    if expected_selection_text is not None:
        invalid = _validate_text(expected_selection_text, "expected_selection_text")
        if invalid:
            return False, {}, [invalid], False

    ok, selection, errors = read_writer_selection(document_id, workspace)
    if not ok:
        return False, selection, errors, False
    if selection.get("read_only"):
        return False, {"selection": selection}, [{
            "code": DOCUMENT_READ_ONLY,
            "message": "The open document is read-only, so its selection cannot be deleted.",
        }], False
    if selection.get("saved") is False:
        return False, {"selection": selection}, [_unsaved_open_document_error("cleared")], False
    problem = _check_replaceable_selection(selection, expected_selection_text)
    if problem:
        return False, {"selection": selection}, [problem], False

    preview = {
        "document_id": document_id,
        "component": "writer",
        "path": selection["path"],
        "start": selection["start"],
        "end": selection["end"],
        "paragraph_index": selection["paragraph_index"],
        "selection_text": selection["selection_text"],
        "expected_selection_text": expected_selection_text,
        "would_modify": True,
        "dry_run": dry_run,
    }
    if dry_run:
        return True, preview, [], False

    backup_ok, backup_result, backup_errors, backup_replayed = create_backup(
        document_id=document_id,
        request_id=f"{request_id}:backup",
        dry_run=False,
        workspace=workspace,
    )
    if not backup_ok:
        return False, {"preview": preview, "backup": backup_result}, backup_errors, False

    path = Path(selection["path"])
    write_result = guarded_com_mutation(
        path,
        backup_result,
        lambda: _run_writer_attached_com(
            "selection-delete",
            {
                "path": str(path),
                "expected_start": selection["start"],
                "expected_end": selection["end"],
                "expected_text": selection["selection_text"],
            },
        ),
    )
    if not write_result["ok"]:
        return False, {"preview": preview, "backup": backup_result, "write": write_result["data"]}, write_result["errors"], False
    payload = write_result["data"]
    status_error = _status_error(payload.get("status"), str(path), action="cleared")
    if status_error:
        return False, {"preview": preview, "backup": backup_result, "write": payload}, [status_error], False

    deleted_text = selection["selection_text"]
    read_back_text = str(payload.get("read_back_text") or "")
    validation_passed = read_back_text != deleted_text
    result = {
        **preview,
        "dry_run": False,
        "backup": backup_result,
        "backup_replayed": backup_replayed,
        "write_backend": payload.get("backend"),
        "deleted_text": payload.get("deleted_text") or deleted_text,
        "read_back_text": read_back_text,
        "validation_passed": validation_passed,
        "selection_preserved": False,
        "note": "The selected range is cleared by position; the user's selection in WPS is not restored.",
    }
    post_error = verify_post_com_source(path, write_result)
    if post_error is not None:
        return False, result, [post_error], False
    if not validation_passed:
        return False, result, [
            {"code": "VALIDATION_FAILED", "message": "Selection delete read-back still matches the deleted text."}
        ], False

    record_operation(request_id, "writer-selection-delete", result, workspace)
    return True, result, [], False


@coordinated_mutation
def replace_presentation_selection(
    document_id: str,
    text: str,
    request_id: str,
    expected_selection_text: str | None = None,
    dry_run: bool = False,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]], bool]:
    replay = replay_operation(
        request_id,
        "presentation-selection-replace",
        {
            "document_id": document_id,
            "replacement_text": text,
            "expected_selection_text": expected_selection_text,
            "dry_run": dry_run,
        },
        workspace,
    )
    if replay is not None:
        return replay

    for value, label in ((text, "Replacement text"), (expected_selection_text, "expected_selection_text")):
        if value is not None:
            invalid = _validate_text(value, label)
            if invalid:
                return False, {}, [invalid], False

    ok, selection, errors = read_presentation_selection(document_id, workspace)
    if not ok:
        return False, selection, errors, False
    if selection.get("read_only"):
        return False, {"selection": selection}, [{
            "code": DOCUMENT_READ_ONLY,
            "message": "The open document is read-only, so its selection cannot be replaced.",
        }], False
    if selection.get("saved") is False:
        return False, {"selection": selection}, [_unsaved_open_document_error("replaced")], False
    problem = _check_replaceable_presentation_selection(selection, expected_selection_text)
    if problem:
        return False, {"selection": selection}, [problem], False

    preview = {
        "document_id": document_id,
        "component": "presentation",
        "path": selection["path"],
        "selection_kind": selection["selection_kind"],
        "slide_index": selection.get("slide_index"),
        "shape_name": selection.get("shape_name"),
        "selection_text": selection["selection_text"],
        "replacement_text": text,
        "expected_selection_text": expected_selection_text,
        "would_modify": selection["selection_text"] != text,
        "dry_run": dry_run,
        "slide_info_verified": False,
    }
    if dry_run:
        return True, preview, [], False

    backup_ok, backup_result, backup_errors, backup_replayed = create_backup(
        document_id=document_id,
        request_id=f"{request_id}:backup",
        dry_run=False,
        workspace=workspace,
    )
    if not backup_ok:
        return False, {"preview": preview, "backup": backup_result}, backup_errors, False

    path = Path(selection["path"])
    write_result = guarded_com_mutation(
        path,
        backup_result,
        lambda: _run_presentation_attached_com(
            "selection-replace",
            {
                "path": str(path),
                "text": text,
                "expected_text": selection["selection_text"],
            },
        ),
    )
    if not write_result["ok"]:
        return False, {"preview": preview, "backup": backup_result, "write": write_result["data"]}, write_result["errors"], False
    payload = write_result["data"]
    status_error = _status_error(payload.get("status"), str(path), component="presentation", action="replaced")
    if status_error:
        return False, {"preview": preview, "backup": backup_result, "write": payload}, [status_error], False

    read_back_text = payload.get("read_back_text")
    validation_passed = read_back_text == text
    result = {
        **preview,
        "dry_run": False,
        "backup": backup_result,
        "backup_replayed": backup_replayed,
        "write_backend": payload.get("backend"),
        "read_back_text": read_back_text,
        "validation_passed": validation_passed,
        "selection_preserved": False,
        "formatting_mode": payload.get("formatting_mode") or "uniform_character",
        "formatting_preserved": bool(payload.get("formatting_preserved")),
        "note": (
            "Selection text is replaced in place; uniform character formatting (font name/size/bold/italic/"
            "underline/color) is snapshotted and reapplied when WPS reports defined values. "
            "Mixed runs within the selection are not reconstructed. "
            "The user's selection in WPS is not restored."
        ),
    }
    post_error = verify_post_com_source(path, write_result)
    if post_error is not None:
        return False, result, [post_error], False
    if not validation_passed:
        return False, result, [
            {"code": "VALIDATION_FAILED", "message": "Selection replacement read-back did not match the replacement text."}
        ], False

    record_operation(request_id, "presentation-selection-replace", result, workspace)
    return True, result, [], False


def _check_insertable_presentation_selection(
    selection: dict[str, Any],
    expected_start: int | None,
) -> dict[str, str] | None:
    kind = selection.get("selection_kind") or "unknown"
    if kind != "text":
        if kind in {"none", "unknown"}:
            return {"code": SELECTION_EMPTY, "message": "The selection is empty; place a text caret inside a shape before inserting."}
        return {
            "code": SELECTION_SPANS_STRUCTURE,
            "message": "Only a collapsed text caret inside a shape can receive inserts; select plain text or collapse the caret.",
        }
    if not selection.get("collapsed"):
        return {
            "code": SELECTION_NOT_COLLAPSED,
            "message": "The selection is not collapsed to a caret; collapse it before inserting, or use presentation-selection-replace to replace selected text.",
        }
    start = selection.get("text_range_start")
    if start is None:
        return {
            "code": SELECTION_UNAVAILABLE,
            "message": "The text caret position could not be determined; click inside a text frame and try again.",
        }
    if expected_start is not None and int(start) != int(expected_start):
        return {
            "code": SELECTION_MISMATCH,
            "message": "The current caret position does not match expected_start.",
        }
    return None


@coordinated_mutation
def insert_presentation_selection(
    document_id: str,
    text: str,
    request_id: str,
    expected_start: int | None = None,
    dry_run: bool = False,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]], bool]:
    replay = replay_operation(
        request_id,
        "presentation-selection-insert",
        {
            "document_id": document_id,
            "insert_text": text,
            "expected_start": expected_start,
            "dry_run": dry_run,
        },
        workspace,
    )
    if replay is not None:
        return replay

    if not text:
        return False, {}, [{"code": "INVALID_ARGUMENT", "message": "Insert text must not be empty."}], False
    invalid = _validate_text(text, "Insert text")
    if invalid:
        return False, {}, [invalid], False

    ok, selection, errors = read_presentation_selection(document_id, workspace)
    if not ok:
        return False, selection, errors, False
    if selection.get("read_only"):
        return False, {"selection": selection}, [{
            "code": DOCUMENT_READ_ONLY,
            "message": "The open document is read-only, so text cannot be inserted at the caret.",
        }], False
    if selection.get("saved") is False:
        return False, {"selection": selection}, [_unsaved_open_document_error("inserted into")], False
    problem = _check_insertable_presentation_selection(selection, expected_start)
    if problem:
        return False, {"selection": selection}, [problem], False

    preview = {
        "document_id": document_id,
        "component": "presentation",
        "path": selection["path"],
        "selection_kind": selection["selection_kind"],
        "slide_index": selection.get("slide_index"),
        "shape_name": selection.get("shape_name"),
        "text_range_start": selection.get("text_range_start"),
        "collapsed": True,
        "insert_text": text,
        "expected_start": expected_start,
        "would_modify": True,
        "dry_run": dry_run,
        "slide_info_verified": False,
    }
    if dry_run:
        return True, preview, [], False

    backup_ok, backup_result, backup_errors, backup_replayed = create_backup(
        document_id=document_id,
        request_id=f"{request_id}:backup",
        dry_run=False,
        workspace=workspace,
    )
    if not backup_ok:
        return False, {"preview": preview, "backup": backup_result}, backup_errors, False

    path = Path(selection["path"])
    write_result = guarded_com_mutation(
        path,
        backup_result,
        lambda: _run_presentation_attached_com(
            "selection-insert",
            {
                "path": str(path),
                "text": text,
                "expected_start": selection["text_range_start"],
            },
        ),
    )
    if not write_result["ok"]:
        return False, {"preview": preview, "backup": backup_result, "write": write_result["data"]}, write_result["errors"], False
    payload = write_result["data"]
    status_error = _status_error(payload.get("status"), str(path), component="presentation", action="inserted into")
    if status_error:
        return False, {"preview": preview, "backup": backup_result, "write": payload}, [status_error], False

    read_back_text = payload.get("read_back_text")
    validation_passed = read_back_text == text
    result = {
        **preview,
        "dry_run": False,
        "backup": backup_result,
        "backup_replayed": backup_replayed,
        "write_backend": payload.get("backend"),
        "inserted_start": payload.get("start"),
        "inserted_end": payload.get("end"),
        "read_back_text": read_back_text,
        "validation_passed": validation_passed,
        "selection_preserved": False,
        "note": "Text is inserted at the caret in the active text frame; the user's selection in WPS is not restored.",
    }
    post_error = verify_post_com_source(path, write_result)
    if post_error is not None:
        return False, result, [post_error], False
    if not validation_passed:
        return False, result, [
            {"code": "VALIDATION_FAILED", "message": "Caret insert read-back did not match the insert text."}
        ], False

    record_operation(request_id, "presentation-selection-insert", result, workspace)
    return True, result, [], False


@coordinated_mutation
def delete_presentation_selection(
    document_id: str,
    request_id: str,
    expected_selection_text: str | None = None,
    dry_run: bool = False,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]], bool]:
    replay = replay_operation(
        request_id,
        "presentation-selection-delete",
        {
            "document_id": document_id,
            "expected_selection_text": expected_selection_text,
            "dry_run": dry_run,
        },
        workspace,
    )
    if replay is not None:
        return replay

    if expected_selection_text is not None:
        invalid = _validate_text(expected_selection_text, "expected_selection_text")
        if invalid:
            return False, {}, [invalid], False

    ok, selection, errors = read_presentation_selection(document_id, workspace)
    if not ok:
        return False, selection, errors, False
    if selection.get("read_only"):
        return False, {"selection": selection}, [{
            "code": DOCUMENT_READ_ONLY,
            "message": "The open document is read-only, so its selection cannot be deleted.",
        }], False
    if selection.get("saved") is False:
        return False, {"selection": selection}, [_unsaved_open_document_error("cleared")], False
    problem = _check_replaceable_presentation_selection(
        selection, expected_selection_text, operation="delete",
    )
    if problem:
        return False, {"selection": selection}, [problem], False

    preview = {
        "document_id": document_id,
        "component": "presentation",
        "path": selection["path"],
        "selection_kind": selection["selection_kind"],
        "slide_index": selection.get("slide_index"),
        "shape_name": selection.get("shape_name"),
        "selection_text": selection["selection_text"],
        "expected_selection_text": expected_selection_text,
        "would_modify": True,
        "dry_run": dry_run,
        "slide_info_verified": False,
    }
    if dry_run:
        return True, preview, [], False

    backup_ok, backup_result, backup_errors, backup_replayed = create_backup(
        document_id=document_id,
        request_id=f"{request_id}:backup",
        dry_run=False,
        workspace=workspace,
    )
    if not backup_ok:
        return False, {"preview": preview, "backup": backup_result}, backup_errors, False

    path = Path(selection["path"])
    write_result = guarded_com_mutation(
        path,
        backup_result,
        lambda: _run_presentation_attached_com(
            "selection-delete",
            {
                "path": str(path),
                "expected_text": selection["selection_text"],
            },
        ),
    )
    if not write_result["ok"]:
        return False, {"preview": preview, "backup": backup_result, "write": write_result["data"]}, write_result["errors"], False
    payload = write_result["data"]
    status_error = _status_error(payload.get("status"), str(path), component="presentation", action="cleared")
    if status_error:
        return False, {"preview": preview, "backup": backup_result, "write": payload}, [status_error], False

    deleted_text = selection["selection_text"]
    read_back_text = str(payload.get("read_back_text") or "")
    validation_passed = read_back_text != deleted_text
    result = {
        **preview,
        "dry_run": False,
        "backup": backup_result,
        "backup_replayed": backup_replayed,
        "write_backend": payload.get("backend"),
        "deleted_text": payload.get("deleted_text") or deleted_text,
        "read_back_text": read_back_text,
        "validation_passed": validation_passed,
        "selection_preserved": False,
        "note": "The selected TextRange is cleared in place; the user's selection in WPS is not restored.",
    }
    post_error = verify_post_com_source(path, write_result)
    if post_error is not None:
        return False, result, [post_error], False
    if not validation_passed:
        return False, result, [
            {"code": "VALIDATION_FAILED", "message": "Selection delete read-back still matches the deleted text."}
        ], False

    record_operation(request_id, "presentation-selection-delete", result, workspace)
    return True, result, [], False


@coordinated_mutation
def replace_spreadsheet_selection(
    document_id: str,
    text: str | None = None,
    request_id: str = "",
    *,
    values: list[list[Any]] | None = None,
    expected_selection_text: str | None = None,
    dry_run: bool = False,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]], bool]:
    if not request_id:
        return False, {}, [{"code": "INVALID_ARGUMENT", "message": "request_id is required."}], False

    has_text = text is not None
    has_values = values is not None
    if has_text == has_values:
        return False, {}, [{
            "code": "INVALID_ARGUMENT",
            "message": "Provide exactly one of text (constant fill) or values_json (per-cell matrix).",
        }], False

    matrix: list[list[str | None]] | None = None
    if has_values:
        matrix, matrix_error = _parse_selection_values_matrix(values)
        if matrix_error:
            return False, {}, [matrix_error], False
        assert matrix is not None
        fill_mode = "matrix"
        row_count = len(matrix)
        column_count = len(matrix[0])
        replacement_text = None
    else:
        assert text is not None
        invalid = _validate_spreadsheet_expected_text(text, "Replacement text")
        if invalid:
            return False, {}, [invalid], False
        fill_mode = "constant"
        row_count = 0
        column_count = 0
        replacement_text = text

    replay = replay_operation(
        request_id,
        "spreadsheet-selection-replace",
        {
            "document_id": document_id,
            "replacement_text": replacement_text,
            "values": matrix,
            "fill_mode": fill_mode,
            "expected_selection_text": expected_selection_text,
            "dry_run": dry_run,
        },
        workspace,
    )
    if replay is not None:
        return replay

    if expected_selection_text is not None:
        invalid = _validate_spreadsheet_expected_text(expected_selection_text, "expected_selection_text")
        if invalid:
            return False, {}, [invalid], False

    ok, selection, errors = read_spreadsheet_selection(document_id, workspace)
    if not ok:
        return False, selection, errors, False
    if selection.get("read_only"):
        return False, {"selection": selection}, [{
            "code": DOCUMENT_READ_ONLY,
            "message": "The open document is read-only, so its selection cannot be replaced.",
        }], False
    if selection.get("saved") is False:
        return False, {"selection": selection}, [_unsaved_open_document_error("replaced")], False
    problem = _check_replaceable_spreadsheet_selection(selection, expected_selection_text)
    if problem:
        return False, {"selection": selection}, [problem], False

    is_shape_text = (
        selection.get("selection_kind") == "non_range"
        and selection.get("object_kind") == "shape"
        and bool(selection.get("has_text_frame"))
    )
    is_series_values = (
        selection.get("selection_kind") == "non_range"
        and selection.get("object_kind") == "chart"
        and bool(selection.get("has_series_values"))
    )
    is_axis_title = (
        selection.get("selection_kind") == "non_range"
        and selection.get("object_kind") == "chart"
        and bool(selection.get("has_axis_title"))
        and not is_series_values
    )
    is_chart_title = (
        selection.get("selection_kind") == "non_range"
        and selection.get("object_kind") == "chart"
        and bool(selection.get("has_chart_title"))
        and not is_axis_title
        and not is_series_values
    )
    if (is_shape_text or is_chart_title or is_axis_title or is_series_values) and fill_mode == "matrix":
        target = (
            "Series Values"
            if is_series_values
            else "AxisTitle"
            if is_axis_title
            else "ChartTitle"
            if is_chart_title
            else "Shape TextFrame"
        )
        return False, {"selection": selection}, [{
            "code": OBJECT_SELECTION_UNSUPPORTED,
            "message": (
                f"{target} write supports only constant --text"
                + (" (TAB-joined values)" if is_series_values else "")
                + "; values_json matrix fill is for worksheet cells."
            ),
        }], False

    if fill_mode == "constant" and not (is_shape_text or is_chart_title or is_axis_title or is_series_values):
        prefix_error = _formula_prefix_error(replacement_text, "Replacement text")
        if prefix_error:
            return False, {"selection": selection}, [prefix_error], False

    if is_series_values:
        assert replacement_text is not None
        expected_points = selection["selection_text"].split("\t")
        provided_points = replacement_text.split("\t")
        if len(provided_points) != len(expected_points):
            return False, {
                "selection": selection,
                "expected_count": len(expected_points),
                "provided_count": len(provided_points),
            }, [{
                "code": "RANGE_SHAPE_MISMATCH",
                "message": (
                    "Series replacement value count must match the selected series point count "
                    f"({len(expected_points)} TAB-joined values)."
                ),
            }], False

    cell_count = int(selection.get("cell_count") or 0)
    selection_rows = int(selection.get("row_count") or 0)
    selection_cols = int(selection.get("column_count") or 0)
    area_count = int(selection.get("area_count") or 0)
    if fill_mode == "matrix":
        assert matrix is not None
        if row_count * column_count != cell_count:
            return False, {
                "selection": selection,
                "values_shape": [row_count, column_count],
                "selection_cell_count": cell_count,
            }, [{
                "code": "RANGE_SHAPE_MISMATCH",
                "message": "values_json cell count must match the selected cells (row-major flatten for multi-area).",
            }], False
        if area_count == 1 and (selection_rows, selection_cols) != (row_count, column_count):
            return False, {
                "selection": selection,
                "values_shape": [row_count, column_count],
                "selection_shape": [selection_rows, selection_cols],
            }, [{
                "code": "RANGE_SHAPE_MISMATCH",
                "message": "values_json shape must match the selected range rows and columns.",
            }], False

    object_text_mode = is_shape_text or is_chart_title or is_axis_title or is_series_values
    preview = {
        "document_id": document_id,
        "component": "spreadsheets",
        "path": selection["path"],
        "selection_kind": selection["selection_kind"],
        "address": selection.get("address"),
        "sheet_name": selection.get("sheet_name"),
        "cell_count": cell_count,
        "area_count": int(selection.get("area_count") or 0),
        "row_count": selection_rows if fill_mode == "constant" else row_count,
        "column_count": selection_cols if fill_mode == "constant" else column_count,
        "selection_text": selection["selection_text"],
        "formula": selection.get("formula"),
        "object_kind": selection.get("object_kind"),
        "object_name": selection.get("object_name"),
        "has_text_frame": bool(selection.get("has_text_frame")),
        "has_chart_title": bool(selection.get("has_chart_title")),
        "has_axis_title": bool(selection.get("has_axis_title")),
        "has_series_values": bool(selection.get("has_series_values")),
        "series_name": selection.get("series_name"),
        "replacement_text": replacement_text,
        "values": matrix,
        "expected_selection_text": expected_selection_text,
        "would_modify": (
            selection["selection_text"] != replacement_text
            if fill_mode == "constant" and (cell_count == 1 or object_text_mode)
            else True
        ),
        "dry_run": dry_run,
        "fill_mode": (
            "series_values"
            if is_series_values
            else "axis_title"
            if is_axis_title
            else "chart_title"
            if is_chart_title
            else "shape_text"
            if is_shape_text
            else fill_mode
        ),
    }
    if dry_run:
        return True, preview, [], False

    backup_ok, backup_result, backup_errors, backup_replayed = create_backup(
        document_id=document_id,
        request_id=f"{request_id}:backup",
        dry_run=False,
        workspace=workspace,
    )
    if not backup_ok:
        return False, {"preview": preview, "backup": backup_result}, backup_errors, False

    path = Path(selection["path"])
    if is_series_values:
        com_params = {
            "path": str(path),
            "values": replacement_text.split("\t"),
            "expected_text": selection["selection_text"],
            "expected_object_name": selection.get("object_name") or "",
        }
        com_action = "selection-series-values-replace"
    elif is_axis_title:
        com_params = {
            "path": str(path),
            "text": replacement_text,
            "expected_text": selection["selection_text"],
            "expected_object_name": selection.get("object_name") or "",
        }
        com_action = "selection-axis-title-replace"
    elif is_chart_title:
        com_params = {
            "path": str(path),
            "text": replacement_text,
            "expected_text": selection["selection_text"],
            "expected_object_name": selection.get("object_name") or "",
        }
        com_action = "selection-chart-title-replace"
    elif is_shape_text:
        com_params = {
            "path": str(path),
            "text": replacement_text,
            "expected_text": selection["selection_text"],
            "expected_object_name": selection.get("object_name") or "",
        }
        com_action = "selection-shape-replace"
    else:
        com_params = {
            "path": str(path),
            "expected_text": selection["selection_text"],
            "expected_address": selection["address"],
            "max_cells": MAX_SPREADSHEET_SELECTION_SAMPLE_CELLS,
            "mode": fill_mode,
        }
        if fill_mode == "matrix":
            com_params.update({
                "values": matrix,
                "row_count": row_count,
                "column_count": column_count,
                "text": "",
            })
        else:
            com_params["text"] = replacement_text
        com_action = "selection-replace"

    write_result = guarded_com_mutation(
        path,
        backup_result,
        lambda: _run_spreadsheet_attached_com(com_action, com_params),
    )
    if not write_result["ok"]:
        return False, {"preview": preview, "backup": backup_result, "write": write_result["data"]}, write_result["errors"], False
    payload = write_result["data"]
    status_error = _status_error(payload.get("status"), str(path), component="spreadsheets", action="replaced")
    if status_error:
        return False, {"preview": preview, "backup": backup_result, "write": payload}, [status_error], False

    read_back_text = str(payload.get("read_back_text") if payload.get("read_back_text") is not None else "")
    if object_text_mode:
        cells_matched = read_back_text == replacement_text
    else:
        cells_matched = bool(payload.get("cells_matched")) if "cells_matched" in payload else (
            fill_mode == "constant" and cell_count == 1 and read_back_text == replacement_text
        )
        if fill_mode == "constant" and cell_count == 1:
            cells_matched = read_back_text == replacement_text
    validation_passed = cells_matched
    if is_series_values:
        note = (
            "Selected worksheet chart Series.Values are overwritten from TAB-joined --text "
            "(point count must match); geometry mutation is not supported; "
            "the user's selection in WPS is not restored."
        )
    elif is_axis_title:
        note = (
            "Selected worksheet chart AxisTitle text is overwritten as plain text; "
            "geometry mutation is not supported; the user's selection in WPS is not restored."
        )
    elif is_chart_title:
        note = (
            "Selected worksheet chart ChartTitle text is overwritten as plain text; "
            "geometry mutation is not supported; the user's selection in WPS is not restored."
        )
    elif is_shape_text:
        note = (
            "Selected worksheet shape TextFrame text is overwritten as plain text; "
            "chart geometry mutation is not supported; the user's selection in WPS is not restored."
        )
    elif fill_mode == "matrix":
        note = (
            "Selected cells are overwritten from values_json in Areas→Cells order "
            "(row-major flatten when multi-area); formulas in the selection are replaced; "
            "the user's selection in WPS is not restored."
        )
    else:
        note = (
            "Selected cells are overwritten with the same constant value (formulas are replaced); "
            "the user's selection in WPS is not restored."
        )
    result = {
        **preview,
        "dry_run": False,
        "backup": backup_result,
        "backup_replayed": backup_replayed,
        "write_backend": payload.get("backend"),
        "read_back_text": read_back_text,
        "read_back_values": payload.get("read_back_values"),
        "cells_matched": cells_matched,
        "validation_passed": validation_passed,
        "selection_preserved": False,
        "note": note,
    }
    post_error = verify_post_com_source(path, write_result)
    if post_error is not None:
        return False, result, [post_error], False
    if not validation_passed:
        return False, result, [
            {"code": "VALIDATION_FAILED", "message": "Selection replacement read-back did not match the replacement values."}
        ], False

    record_operation(request_id, "spreadsheet-selection-replace", result, workspace)
    return True, result, [], False


def _unsaved_open_document_error(action: str = "modified") -> dict[str, str]:
    return {
        "code": DOCUMENT_HAS_UNSAVED_CHANGES,
        "message": (
            f"The open document has unsaved changes; save it with save-open-document first "
            f"so the backup and file-based verification match what is open before it is {action}."
        ),
    }


def _spreadsheet_selection_has_content(selection: dict[str, Any]) -> bool:
    text = str(selection.get("selection_text") or "")
    if any(part for part in text.split("\t")):
        return True
    return bool(selection.get("formula"))


@coordinated_mutation
def delete_spreadsheet_selection(
    document_id: str,
    request_id: str,
    expected_selection_text: str | None = None,
    dry_run: bool = False,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]], bool]:
    replay = replay_operation(
        request_id,
        "spreadsheet-selection-delete",
        {
            "document_id": document_id,
            "expected_selection_text": expected_selection_text,
            "dry_run": dry_run,
        },
        workspace,
    )
    if replay is not None:
        return replay

    if expected_selection_text is not None:
        invalid = _validate_spreadsheet_expected_text(expected_selection_text, "expected_selection_text")
        if invalid:
            return False, {}, [invalid], False

    ok, selection, errors = read_spreadsheet_selection(document_id, workspace)
    if not ok:
        return False, selection, errors, False
    if selection.get("read_only"):
        return False, {"selection": selection}, [{
            "code": DOCUMENT_READ_ONLY,
            "message": "The open document is read-only, so its selection cannot be deleted.",
        }], False
    if selection.get("saved") is False:
        return False, {"selection": selection}, [_unsaved_open_document_error("cleared")], False
    problem = _check_replaceable_spreadsheet_selection(
        selection, expected_selection_text, operation="delete",
    )
    if problem:
        return False, {"selection": selection}, [problem], False
    is_shape_text = (
        selection.get("selection_kind") == "non_range"
        and selection.get("object_kind") == "shape"
        and bool(selection.get("has_text_frame"))
    )
    is_series_values = (
        selection.get("selection_kind") == "non_range"
        and selection.get("object_kind") == "chart"
        and bool(selection.get("has_series_values"))
    )
    is_axis_title = (
        selection.get("selection_kind") == "non_range"
        and selection.get("object_kind") == "chart"
        and bool(selection.get("has_axis_title"))
        and not is_series_values
    )
    is_chart_title = (
        selection.get("selection_kind") == "non_range"
        and selection.get("object_kind") == "chart"
        and bool(selection.get("has_chart_title"))
        and not is_axis_title
        and not is_series_values
    )
    if not _spreadsheet_selection_has_content(selection):
        if is_series_values:
            empty_message = "The series has no values to clear; select a series with Values first."
        elif is_axis_title:
            empty_message = "The axis has no title text to clear; select an axis title first."
        elif is_chart_title:
            empty_message = "The chart has no title text to clear; select a chart with a title first."
        elif is_shape_text:
            empty_message = "The selection has no shape text to clear; select a text-bearing shape first."
        else:
            empty_message = (
                "The selection has no display text or formula to clear; select cells that contain values first."
            )
        return False, {"selection": selection}, [{
            "code": SELECTION_EMPTY,
            "message": empty_message,
        }], False

    preview = {
        "document_id": document_id,
        "component": "spreadsheets",
        "path": selection["path"],
        "selection_kind": selection["selection_kind"],
        "address": selection.get("address"),
        "sheet_name": selection.get("sheet_name"),
        "cell_count": int(selection.get("cell_count") or 0),
        "area_count": int(selection.get("area_count") or 0),
        "selection_text": selection["selection_text"],
        "formula": selection.get("formula"),
        "object_kind": selection.get("object_kind"),
        "object_name": selection.get("object_name"),
        "has_text_frame": bool(selection.get("has_text_frame")),
        "has_chart_title": bool(selection.get("has_chart_title")),
        "has_axis_title": bool(selection.get("has_axis_title")),
        "has_series_values": bool(selection.get("has_series_values")),
        "series_name": selection.get("series_name"),
        "expected_selection_text": expected_selection_text,
        "would_modify": True,
        "dry_run": dry_run,
        "fill_mode": (
            "series_values"
            if is_series_values
            else "axis_title"
            if is_axis_title
            else "chart_title"
            if is_chart_title
            else "shape_text"
            if is_shape_text
            else "clear_cells"
        ),
    }
    if dry_run:
        return True, preview, [], False

    backup_ok, backup_result, backup_errors, backup_replayed = create_backup(
        document_id=document_id,
        request_id=f"{request_id}:backup",
        dry_run=False,
        workspace=workspace,
    )
    if not backup_ok:
        return False, {"preview": preview, "backup": backup_result}, backup_errors, False

    path = Path(selection["path"])
    if is_series_values:
        write_result = guarded_com_mutation(
            path,
            backup_result,
            lambda: _run_spreadsheet_attached_com(
                "selection-series-values-delete",
                {
                    "path": str(path),
                    "expected_text": selection["selection_text"],
                    "expected_object_name": selection.get("object_name") or "",
                },
            ),
        )
    elif is_axis_title:
        write_result = guarded_com_mutation(
            path,
            backup_result,
            lambda: _run_spreadsheet_attached_com(
                "selection-axis-title-delete",
                {
                    "path": str(path),
                    "expected_text": selection["selection_text"],
                    "expected_object_name": selection.get("object_name") or "",
                },
            ),
        )
    elif is_chart_title:
        write_result = guarded_com_mutation(
            path,
            backup_result,
            lambda: _run_spreadsheet_attached_com(
                "selection-chart-title-delete",
                {
                    "path": str(path),
                    "expected_text": selection["selection_text"],
                    "expected_object_name": selection.get("object_name") or "",
                },
            ),
        )
    elif is_shape_text:
        write_result = guarded_com_mutation(
            path,
            backup_result,
            lambda: _run_spreadsheet_attached_com(
                "selection-shape-delete",
                {
                    "path": str(path),
                    "expected_text": selection["selection_text"],
                    "expected_object_name": selection.get("object_name") or "",
                },
            ),
        )
    else:
        write_result = guarded_com_mutation(
            path,
            backup_result,
            lambda: _run_spreadsheet_attached_com(
                "selection-delete",
                {
                    "path": str(path),
                    "expected_text": selection["selection_text"],
                    "expected_address": selection["address"],
                    "max_cells": MAX_SPREADSHEET_SELECTION_SAMPLE_CELLS,
                },
            ),
        )
    if not write_result["ok"]:
        return False, {"preview": preview, "backup": backup_result, "write": write_result["data"]}, write_result["errors"], False
    payload = write_result["data"]
    status_error = _status_error(payload.get("status"), str(path), component="spreadsheets", action="cleared")
    if status_error:
        return False, {"preview": preview, "backup": backup_result, "write": payload}, [status_error], False

    deleted_text = selection["selection_text"]
    read_back_text = str(payload.get("read_back_text") if payload.get("read_back_text") is not None else "")
    read_back_values = payload.get("read_back_values")
    cells_matched = bool(payload.get("cells_matched")) if "cells_matched" in payload else (
        not read_back_text and (not read_back_values or all(not str(value or "") for value in read_back_values))
    )
    if is_shape_text or is_chart_title or is_axis_title:
        cells_matched = not read_back_text
    elif is_series_values:
        cells_matched = bool(payload.get("cells_matched")) if "cells_matched" in payload else (
            not any(part for part in read_back_text.split("\t"))
        )
    validation_passed = cells_matched
    if is_series_values:
        clear_note = (
            "Selected worksheet chart Series.Values are cleared to empty points; "
            "geometry mutation is not supported; the user's selection in WPS is not restored."
        )
    elif is_axis_title:
        clear_note = (
            "Selected worksheet chart AxisTitle is cleared; geometry mutation is not supported; "
            "the user's selection in WPS is not restored."
        )
    elif is_chart_title:
        clear_note = (
            "Selected worksheet chart ChartTitle is cleared; geometry mutation is not supported; "
            "the user's selection in WPS is not restored."
        )
    elif is_shape_text:
        clear_note = (
            "Selected worksheet shape TextFrame text is cleared; chart geometry mutation is not supported; "
            "the user's selection in WPS is not restored."
        )
    else:
        clear_note = (
            "Selected cells are cleared with ClearContents (formulas and values); "
            "the user's selection in WPS is not restored."
        )
    result = {
        **preview,
        "dry_run": False,
        "backup": backup_result,
        "backup_replayed": backup_replayed,
        "write_backend": payload.get("backend"),
        "deleted_text": payload.get("deleted_text") or deleted_text,
        "read_back_text": read_back_text,
        "read_back_values": read_back_values,
        "cells_matched": cells_matched,
        "validation_passed": validation_passed,
        "selection_preserved": False,
        "note": clear_note,
    }
    post_error = verify_post_com_source(path, write_result)
    if post_error is not None:
        return False, result, [post_error], False
    if not validation_passed:
        return False, result, [
            {"code": "VALIDATION_FAILED", "message": "Selection delete read-back still contains cell text."}
        ], False

    record_operation(request_id, "spreadsheet-selection-delete", result, workspace)
    return True, result, [], False


@coordinated_mutation
def save_open_document(
    document_id: str,
    request_id: str,
    dry_run: bool = False,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]], bool]:
    replay = replay_operation(
        request_id,
        "save-open-document",
        {"document_id": document_id, "dry_run": dry_run},
        workspace,
    )
    if replay is not None:
        return replay

    document, data, errors = _registered_document(
        document_id, workspace, allowed_components={"writer", "presentation", "spreadsheets"},
    )
    if document is None:
        return False, data, errors, False
    component = document["component"]
    path = Path(document["path"]).resolve()
    inspect = _run_component_attached_com(component, "save", {"path": str(path), "do_save": False})
    if not inspect["ok"]:
        return False, {"document_id": document_id, "path": str(path), **inspect["data"]}, inspect["errors"], False
    payload = inspect["data"] or {}
    if payload.get("ok") is False:
        return False, {"document_id": document_id, "path": str(path), "diagnostic": payload}, [
            {"code": COM_OPERATION_FAILED, "message": str(payload.get("error_message") or "Open-document save inspect failed.")}
        ], False
    if payload.get("status") == "read_only" or payload.get("read_only"):
        return False, {"document_id": document_id, "path": str(path), "saved": payload.get("saved"), "read_only": True}, [{
            "code": DOCUMENT_READ_ONLY,
            "message": "The open document is read-only, so it cannot be saved over the source file.",
        }], False
    status_error = _status_error(payload.get("status"), str(path), component=component, action="saved")
    if status_error:
        return False, {"document_id": document_id, "path": str(path)}, [status_error], False

    already_saved = bool(payload.get("saved"))
    preview = {
        "document_id": document_id,
        "component": component,
        "path": str(path),
        "saved": already_saved,
        "read_only": False,
        "would_modify": not already_saved,
        "dry_run": dry_run,
        "note": "Explicit Save() of an already-pathed open document; untitled documents without a path cannot be saved this way.",
    }
    if dry_run:
        return True, preview, [], False
    if already_saved:
        result = {
            **preview,
            "dry_run": False,
            "wrote": False,
            "backup": None,
            "source_still_open": True,
            "validation_passed": True,
        }
        record_operation(request_id, "save-open-document", result, workspace)
        return True, result, [], False

    backup_ok, backup_result, backup_errors, backup_replayed = create_backup(
        document_id=document_id,
        request_id=f"{request_id}:backup",
        dry_run=False,
        workspace=workspace,
    )
    if not backup_ok:
        return False, {"preview": preview, "backup": backup_result}, backup_errors, False

    write_result = guarded_com_mutation(
        path,
        backup_result,
        lambda: _run_component_attached_com(component, "save", {"path": str(path), "do_save": True}),
    )
    if not write_result["ok"]:
        return False, {"preview": preview, "backup": backup_result, "write": write_result["data"]}, write_result["errors"], False
    write_payload = write_result["data"] or {}
    if write_payload.get("status") == "read_only" or write_payload.get("read_only"):
        return False, {"preview": preview, "backup": backup_result, "write": write_payload}, [{
            "code": DOCUMENT_READ_ONLY,
            "message": "The open document is read-only, so it cannot be saved over the source file.",
        }], False
    status_error = _status_error(write_payload.get("status"), str(path), component=component, action="saved")
    if status_error:
        return False, {"preview": preview, "backup": backup_result, "write": write_payload}, [status_error], False

    saved_after = bool(write_payload.get("saved"))
    source_still_open = bool(write_payload.get("source_still_open"))
    validation_passed = saved_after and source_still_open
    result = {
        **preview,
        "dry_run": False,
        "saved": saved_after,
        "wrote": bool(write_payload.get("wrote")),
        "backup": backup_result,
        "backup_replayed": backup_replayed,
        "write_backend": write_payload.get("backend"),
        "source_still_open": source_still_open,
        "validation_passed": validation_passed,
    }
    post_error = verify_post_com_source(path, write_result)
    if post_error is not None:
        return False, result, [post_error], False
    if not validation_passed:
        return False, result, [
            {"code": "VALIDATION_FAILED", "message": "Open-document Save() did not leave the document saved and still open."}
        ], False

    record_operation(request_id, "save-open-document", result, workspace)
    return True, result, [], False


@coordinated_request
def save_as_open_document(
    component: str,
    name: str,
    output: str,
    request_id: str,
    dry_run: bool = False,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]], bool]:
    """Save an untitled open document to a new native path via SaveAs, then register it."""
    replay = replay_operation(
        request_id,
        "save-as-open-document",
        {"component": component, "name": name, "output": output, "dry_run": dry_run},
        workspace,
    )
    if replay is not None:
        return replay

    if component not in WPS_COMPONENTS:
        return False, {}, [{"code": "UNSUPPORTED_COMPONENT", "message": f"Unsupported component: {component}"}], False
    display_name = (name or "").strip()
    if not display_name:
        return False, {}, [{"code": "INVALID_ARGUMENT", "message": "Untitled document --name must be non-empty."}], False

    output_path = Path(output)
    try:
        resolved_output = output_path.resolve()
    except OSError as exc:
        return False, {}, [{"code": "INVALID_ARGUMENT", "message": f"Invalid output path: {exc}"}], False
    suffix = resolved_output.suffix.lower()
    allowed = SAVE_AS_NATIVE_SUFFIXES[component]
    if suffix not in allowed:
        allowed_list = ", ".join(sorted(allowed))
        return False, {"component": component, "output": str(resolved_output)}, [{
            "code": UNSUPPORTED_OUTPUT_EXTENSION,
            "message": f"save-as-open-document for {component} requires a native extension ({allowed_list}).",
        }], False
    if resolved_output.exists():
        return False, {"component": component, "name": display_name, "output": str(resolved_output)}, [{
            "code": OUTPUT_EXISTS,
            "message": f"Output already exists and will not be overwritten: {resolved_output}",
        }], False
    if not resolved_output.parent.is_dir():
        return False, {"component": component, "output": str(resolved_output)}, [{
            "code": "OUTPUT_DIRECTORY_MISSING",
            "message": f"Output directory does not exist: {resolved_output.parent}",
        }], False

    inspect = _run_save_as_untitled_com(component, display_name, str(resolved_output), do_save=False)
    if not inspect["ok"]:
        return False, {
            "component": component,
            "name": display_name,
            "output": str(resolved_output),
            **inspect["data"],
        }, inspect["errors"], False
    payload = inspect["data"] or {}
    if payload.get("ok") is False:
        return False, {
            "component": component,
            "name": display_name,
            "output": str(resolved_output),
            "diagnostic": payload,
        }, [{
            "code": COM_OPERATION_FAILED,
            "message": str(payload.get("error_message") or "Untitled SaveAs inspect failed."),
        }], False

    status = payload.get("status")
    if status == "no_instance":
        return False, {"component": component, "name": display_name, "output": str(resolved_output)}, [{
            "code": NO_RUNNING_WPS_INSTANCE,
            "message": f"No running WPS {component} instance was found; nothing was launched.",
        }], False
    if status == "not_found":
        return False, {"component": component, "name": display_name, "output": str(resolved_output)}, [{
            "code": UNTITLED_DOCUMENT_NOT_FOUND,
            "message": (
                f"No untitled open {component} document named {display_name!r} was found. "
                "List candidates with open-documents."
            ),
        }], False
    if status == "ambiguous":
        return False, {
            "component": component,
            "name": display_name,
            "output": str(resolved_output),
            "match_count": payload.get("match_count"),
        }, [{
            "code": AMBIGUOUS_OPEN_DOCUMENT,
            "message": (
                f"Multiple untitled open {component} documents are named {display_name!r}; "
                "rename one in WPS or close extras before save-as-open-document."
            ),
        }], False
    if status == "already_pathed":
        return False, {
            "component": component,
            "name": display_name,
            "output": str(resolved_output),
            "match_count": payload.get("match_count"),
        }, [{
            "code": DOCUMENT_ALREADY_PATHED,
            "message": (
                f"Open {component} document {display_name!r} already has a disk path; "
                "use save-open-document or export-open-document-copy instead."
            ),
        }], False
    if status == "read_only" or payload.get("read_only"):
        return False, {
            "component": component,
            "name": display_name,
            "output": str(resolved_output),
            "read_only": True,
        }, [{
            "code": DOCUMENT_READ_ONLY,
            "message": "The open untitled document is read-only, so it cannot be saved to a new path.",
        }], False
    if status not in (None, "ok"):
        status_error = _status_error(status, str(resolved_output), component=component, action="saved")
        if status_error:
            return False, {"component": component, "name": display_name, "output": str(resolved_output)}, [status_error], False

    preview = {
        "component": component,
        "name": display_name,
        "output": str(resolved_output),
        "saved": bool(payload.get("saved")),
        "read_only": False,
        "would_modify": True,
        "dry_run": dry_run,
        "backup": None,
        "note": (
            "SaveAs of an untitled open document to a new native path; there is no prior on-disk "
            "source to back up. After success the document is registered under a path-based document_id."
        ),
    }
    if dry_run:
        return True, preview, [], False

    write_result = _run_save_as_untitled_com(component, display_name, str(resolved_output), do_save=True)
    if not write_result["ok"]:
        return False, {"preview": preview, "write": write_result["data"]}, write_result["errors"], False
    write_payload = write_result["data"] or {}
    if write_payload.get("ok") is False:
        return False, {"preview": preview, "diagnostic": write_payload}, [{
            "code": COM_OPERATION_FAILED,
            "message": str(write_payload.get("error_message") or "Untitled SaveAs failed."),
        }], False
    write_status = write_payload.get("status")
    if write_status == "read_only" or write_payload.get("read_only"):
        return False, {"preview": preview, "write": write_payload}, [{
            "code": DOCUMENT_READ_ONLY,
            "message": "The open untitled document is read-only, so it cannot be saved to a new path.",
        }], False
    if write_status in {"not_found", "ambiguous", "already_pathed", "no_instance"}:
        # Race: selection changed between inspect and write.
        code = {
            "not_found": UNTITLED_DOCUMENT_NOT_FOUND,
            "ambiguous": AMBIGUOUS_OPEN_DOCUMENT,
            "already_pathed": DOCUMENT_ALREADY_PATHED,
            "no_instance": NO_RUNNING_WPS_INSTANCE,
        }[write_status]
        return False, {"preview": preview, "write": write_payload}, [{
            "code": code,
            "message": f"Untitled SaveAs aborted because open-document state became {write_status}.",
        }], False
    if write_status not in (None, "ok"):
        status_error = _status_error(write_status, str(resolved_output), component=component, action="saved")
        if status_error:
            return False, {"preview": preview, "write": write_payload}, [status_error], False

    output_exists = resolved_output.is_file() and resolved_output.stat().st_size > 0
    saved_after = bool(write_payload.get("saved"))
    source_still_open = bool(write_payload.get("source_still_open"))
    path_matched = bool(write_payload.get("path_matched"))
    validation_passed = output_exists and saved_after and source_still_open and path_matched

    document_id = None
    register_errors: list[dict[str, str]] = []
    if output_exists:
        ok_reg, record, register_errors = register_document(component, str(resolved_output), workspace)
        if ok_reg:
            document_id = record["document_id"]

    result = {
        **preview,
        "dry_run": False,
        "saved": saved_after,
        "wrote": bool(write_payload.get("wrote")),
        "full_name": write_payload.get("full_name"),
        "path_matched": path_matched,
        "output_exists": output_exists,
        "source_still_open": source_still_open,
        "document_id": document_id,
        "registered": document_id is not None,
        "register_errors": register_errors,
        "write_backend": write_payload.get("backend"),
        "validation_passed": validation_passed,
    }
    if not validation_passed:
        return False, result, [{
            "code": "VALIDATION_FAILED",
            "message": (
                "Untitled SaveAs did not leave a nonempty output file with the document saved, "
                "still open, and path-matched."
            ),
        }], False
    if document_id is None:
        return False, result, register_errors or [{
            "code": "DOCUMENT_REGISTER_FAILED",
            "message": "SaveAs wrote the file but registration of the new path failed.",
        }], False

    record_operation(request_id, "save-as-open-document", result, workspace)
    return True, result, [], False


HTML_EXPORT_KNOWN_LOSSES = [
    "HTML export is a lossy, filtered rendition: page layout, headers/footers, some styles, fields and drawing objects may change or be flattened.",
    "Images and styles are written to a companion folder next to the HTML file; keep them together.",
    "On WPS Writer 12.0, heading/paragraph/table cell plain-text markers were retained in one local open-document export (P3-424); layout/CSS fidelity remains host-dependent and unverified across versions.",
]

PRESENTATION_HTML_EXPORT_KNOWN_LOSSES = [
    "Presentation HTML export is lossy: animations, transitions, and some media are flattened or omitted.",
    "Companion folders next to the HTML file may hold images or frames; keep them together.",
    "On WPS Presentation 12.0, open-document SaveCopyAs HTML produced a nonempty artifact with companion files on a disposable pptx (P3-399); animations/media fidelity remains host-dependent and unverified across versions.",
]

SPREADSHEET_HTML_EXPORT_KNOWN_LOSSES = [
    "Spreadsheet HTML export is lossy: formulas become static values or display text, and charts/macros are omitted or flattened.",
    "Companion folders next to the HTML file may hold frames or images; keep them together.",
    "On WPS Spreadsheets 12.0 (P3-403/P3-434), open-document SaveCopyAs+SaveAs HTML retained plain-text cell markers (may be split by display:none spans), formula display values, and x:fmla attributes on one local fixture; charts/macros and cross-version fidelity remain unverified.",
]

WRITER_PDF_EXPORT_KNOWN_LOSSES = [
    "PDF output is not editable as native WPS content.",
    "Interactive Word fields may be flattened.",
    "Result depends on installed WPS PDF export behavior.",
]

PRESENTATION_PDF_EXPORT_KNOWN_LOSSES = [
    "PDF is not an editable presentation.",
    "Animations and transitions are flattened.",
    "Fonts and media fidelity depend on the installed WPS build.",
]

SPREADSHEET_PDF_EXPORT_KNOWN_LOSSES = [
    "PDF is not an editable workbook.",
    "Formulas are flattened to displayed values.",
    "Print area, page setup, and hidden sheets affect which cells appear.",
]


def _looks_like_html(path: Path) -> bool:
    try:
        head = path.read_bytes()[:512]
    except OSError:
        return False
    if not head or head.startswith(b"PK"):
        return False
    sample = head.lstrip().lower()
    return sample.startswith(b"<!doctype") or sample.startswith(b"<html") or b"<html" in sample


def _looks_like_pdf(path: Path) -> bool:
    try:
        head = path.read_bytes()[:8]
    except OSError:
        return False
    return head.lstrip().startswith(b"%PDF")


@coordinated_mutation
def export_open_document_html(
    document_id: str,
    output: str,
    request_id: str,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]], bool]:
    output_path = Path(output)
    replay = replay_operation(
        request_id,
        "export-open-document",
        {"document_id": document_id, "output": str(output_path.resolve())},
        workspace,
    )
    if replay is not None:
        return replay

    document, data, errors = _registered_document(
        document_id, workspace, allowed_components={"writer", "presentation", "spreadsheets"},
    )
    if document is None:
        return False, data, errors, False
    component = document["component"]
    source = Path(document["path"]).resolve()
    resolved_output = output_path.resolve()
    if resolved_output.suffix.lower() not in HTML_EXPORT_SUFFIXES:
        return False, {}, [{"code": "INVALID_ARGUMENT", "message": "Output must end in .html or .htm; only HTML export of open Writer, Presentation, or Spreadsheet documents is supported."}], False
    if resolved_output == source:
        return False, {}, [{"code": "INVALID_ARGUMENT", "message": "Output must differ from the source document."}], False
    if resolved_output.exists():
        return False, {"output": str(resolved_output)}, [{"code": OUTPUT_EXISTS, "message": "Output already exists; choose a new path. Nothing was overwritten."}], False
    if not resolved_output.parent.is_dir():
        return False, {"output": str(resolved_output)}, [{"code": "INVALID_ARGUMENT", "message": "Output directory does not exist."}], False

    try:
        identity_before = file_identity(source)
    except OSError as exc:
        return False, {}, [{"code": "DOCUMENT_IDENTITY_UNAVAILABLE", "message": str(exc)}], False

    if component == "writer":
        result = _run_writer_attached_com("export-html", {"path": str(source), "output": str(resolved_output)})
        known_losses = HTML_EXPORT_KNOWN_LOSSES
    elif component == "presentation":
        result = _run_presentation_attached_com("export-html", {"path": str(source), "output": str(resolved_output)})
        known_losses = PRESENTATION_HTML_EXPORT_KNOWN_LOSSES
    else:
        result = _run_spreadsheet_attached_com("export-html", {"path": str(source), "output": str(resolved_output)})
        known_losses = SPREADSHEET_HTML_EXPORT_KNOWN_LOSSES
    if not result["ok"]:
        return False, {"document_id": document_id, **result["data"]}, result["errors"], False
    payload = result["data"] or {}
    if payload.get("ok") is False:
        return False, {"document_id": document_id, "diagnostic": payload}, [
            {"code": COM_OPERATION_FAILED, "message": str(payload.get("error_message") or "HTML export failed.")}
        ], False
    status_error = _status_error(payload.get("status"), str(source), component=component, action="exported")
    if status_error:
        return False, {"document_id": document_id}, [status_error], False

    exported = resolved_output.is_file() and resolved_output.stat().st_size > 0
    try:
        source_unchanged = file_identity(source) == identity_before
    except OSError:
        source_unchanged = False
    companion = [
        str(item)
        for item in resolved_output.parent.glob(f"{glob.escape(resolved_output.stem)}*")
        if item.is_dir()
    ]
    export_result = {
        "document_id": document_id,
        "component": component,
        "source_path": str(source),
        "output": str(resolved_output),
        "format": "html",
        "output_bytes": resolved_output.stat().st_size if exported else 0,
        "companion_directories": companion,
        "export_method": payload.get("export_method"),
        "source_still_open": payload.get("source_still_open"),
        "source_unchanged": source_unchanged,
        "known_losses": known_losses,
        "validation_passed": bool(exported and source_unchanged and payload.get("source_still_open")),
    }
    if not exported:
        return False, export_result, [{"code": EXPORT_OUTPUT_MISSING, "message": "WPS reported success but no HTML output file was produced."}], False
    if component in {"presentation", "spreadsheets"} and not _looks_like_html(resolved_output):
        return False, export_result, [{
            "code": EXPORT_OUTPUT_NOT_HTML,
            "message": "WPS wrote the output path, but the bytes are not HTML (for example a renamed package). The source document was left open and unchanged.",
        }], False
    if not source_unchanged:
        return False, export_result, [{"code": "DOCUMENT_CHANGED_AFTER_COM", "message": "The source document changed during export; inspect it before continuing."}], False

    record_operation(request_id, "export-open-document", export_result, workspace)
    return True, export_result, [], False


@coordinated_mutation
def export_open_document_pdf(
    document_id: str,
    output: str,
    request_id: str,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]], bool]:
    output_path = Path(output)
    replay = replay_operation(
        request_id,
        "export-open-document-pdf",
        {"document_id": document_id, "output": str(output_path.resolve())},
        workspace,
    )
    if replay is not None:
        return replay

    document, data, errors = _registered_document(
        document_id, workspace, allowed_components={"writer", "presentation", "spreadsheets"},
    )
    if document is None:
        return False, data, errors, False
    component = document["component"]
    source = Path(document["path"]).resolve()
    resolved_output = output_path.resolve()
    if resolved_output.suffix.lower() not in PDF_EXPORT_SUFFIXES:
        return False, {}, [{"code": "INVALID_ARGUMENT", "message": "Output must end in .pdf; only PDF export of open Writer, Presentation, or Spreadsheet documents is supported."}], False
    if resolved_output == source:
        return False, {}, [{"code": "INVALID_ARGUMENT", "message": "Output must differ from the source document."}], False
    if resolved_output.exists():
        return False, {"output": str(resolved_output)}, [{"code": OUTPUT_EXISTS, "message": "Output already exists; choose a new path. Nothing was overwritten."}], False
    if not resolved_output.parent.is_dir():
        return False, {"output": str(resolved_output)}, [{"code": "INVALID_ARGUMENT", "message": "Output directory does not exist."}], False

    try:
        identity_before = file_identity(source)
    except OSError as exc:
        return False, {}, [{"code": "DOCUMENT_IDENTITY_UNAVAILABLE", "message": str(exc)}], False

    if component == "writer":
        result = _run_writer_attached_com("export-pdf", {"path": str(source), "output": str(resolved_output)})
        known_losses = WRITER_PDF_EXPORT_KNOWN_LOSSES
    elif component == "presentation":
        result = _run_presentation_attached_com("export-pdf", {"path": str(source), "output": str(resolved_output)})
        known_losses = PRESENTATION_PDF_EXPORT_KNOWN_LOSSES
    else:
        result = _run_spreadsheet_attached_com("export-pdf", {"path": str(source), "output": str(resolved_output)})
        known_losses = SPREADSHEET_PDF_EXPORT_KNOWN_LOSSES
    if not result["ok"]:
        return False, {"document_id": document_id, **result["data"]}, result["errors"], False
    payload = result["data"] or {}
    if payload.get("ok") is False:
        return False, {"document_id": document_id, "diagnostic": payload}, [
            {"code": COM_OPERATION_FAILED, "message": str(payload.get("error_message") or "PDF export failed.")}
        ], False
    status_error = _status_error(payload.get("status"), str(source), component=component, action="exported")
    if status_error:
        return False, {"document_id": document_id}, [status_error], False

    exported = resolved_output.is_file() and resolved_output.stat().st_size > 0
    try:
        source_unchanged = file_identity(source) == identity_before
    except OSError:
        source_unchanged = False
    export_result = {
        "document_id": document_id,
        "component": component,
        "source_path": str(source),
        "output": str(resolved_output),
        "format": "pdf",
        "output_bytes": resolved_output.stat().st_size if exported else 0,
        "export_method": payload.get("export_method"),
        "source_still_open": payload.get("source_still_open"),
        "source_unchanged": source_unchanged,
        "known_losses": known_losses,
        "validation_passed": bool(
            exported and source_unchanged and payload.get("source_still_open") and _looks_like_pdf(resolved_output)
        ),
    }
    if not exported:
        return False, export_result, [{"code": EXPORT_OUTPUT_MISSING, "message": "WPS reported success but no PDF output file was produced."}], False
    if not _looks_like_pdf(resolved_output):
        return False, export_result, [{
            "code": EXPORT_OUTPUT_NOT_PDF,
            "message": "WPS wrote the output path, but the bytes are not a PDF. The source document was left open and unchanged.",
        }], False
    if not source_unchanged:
        return False, export_result, [{"code": "DOCUMENT_CHANGED_AFTER_COM", "message": "The source document changed during export; inspect it before continuing."}], False

    record_operation(request_id, "export-open-document-pdf", export_result, workspace)
    return True, export_result, [], False


NATIVE_COPY_KNOWN_LOSSES = [
    "The copy reflects the last saved state; unsaved edits are refused before export.",
    "Same-format copy fidelity depends on the installed WPS SaveCopyAs behavior.",
]


def _looks_like_ooxml_package(path: Path) -> bool:
    try:
        head = path.read_bytes()[:4]
    except OSError:
        return False
    return head.startswith(b"PK")


@coordinated_mutation
def export_open_document_copy(
    document_id: str,
    output: str,
    request_id: str,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]], bool]:
    output_path = Path(output)
    replay = replay_operation(
        request_id,
        "export-open-document-copy",
        {"document_id": document_id, "output": str(output_path.resolve())},
        workspace,
    )
    if replay is not None:
        return replay

    document, data, errors = _registered_document(
        document_id, workspace, allowed_components={"writer", "presentation", "spreadsheets"},
    )
    if document is None:
        return False, data, errors, False
    component = document["component"]
    source = Path(document["path"]).resolve()
    resolved_output = output_path.resolve()
    source_suffix = source.suffix.lower()
    if not source_suffix:
        return False, {}, [{"code": "INVALID_ARGUMENT", "message": "Source document has no file extension; cannot choose a same-format copy path."}], False
    if resolved_output.suffix.lower() != source_suffix:
        return False, {}, [{
            "code": "INVALID_ARGUMENT",
            "message": f"Output must use the same extension as the source ({source_suffix}); native format conversion is not supported by this command.",
        }], False
    if resolved_output == source:
        return False, {}, [{"code": "INVALID_ARGUMENT", "message": "Output must differ from the source document."}], False
    if resolved_output.exists():
        return False, {"output": str(resolved_output)}, [{"code": OUTPUT_EXISTS, "message": "Output already exists; choose a new path. Nothing was overwritten."}], False
    if not resolved_output.parent.is_dir():
        return False, {"output": str(resolved_output)}, [{"code": "INVALID_ARGUMENT", "message": "Output directory does not exist."}], False

    try:
        identity_before = file_identity(source)
    except OSError as exc:
        return False, {}, [{"code": "DOCUMENT_IDENTITY_UNAVAILABLE", "message": str(exc)}], False

    if component == "writer":
        result = _run_writer_attached_com("export-copy", {"path": str(source), "output": str(resolved_output)})
    elif component == "presentation":
        result = _run_presentation_attached_com("export-copy", {"path": str(source), "output": str(resolved_output)})
    else:
        result = _run_spreadsheet_attached_com("export-copy", {"path": str(source), "output": str(resolved_output)})
    if not result["ok"]:
        return False, {"document_id": document_id, **result["data"]}, result["errors"], False
    payload = result["data"] or {}
    if payload.get("ok") is False:
        return False, {"document_id": document_id, "diagnostic": payload}, [
            {"code": COM_OPERATION_FAILED, "message": str(payload.get("error_message") or "Native copy export failed.")}
        ], False
    status_error = _status_error(payload.get("status"), str(source), component=component, action="exported")
    if status_error:
        return False, {"document_id": document_id}, [status_error], False

    exported = resolved_output.is_file() and resolved_output.stat().st_size > 0
    try:
        source_unchanged = file_identity(source) == identity_before
    except OSError:
        source_unchanged = False
    package_ok = True
    if source_suffix in OOXML_PACKAGE_SUFFIXES:
        package_ok = _looks_like_ooxml_package(resolved_output)
    export_result = {
        "document_id": document_id,
        "component": component,
        "source_path": str(source),
        "output": str(resolved_output),
        "format": "native-copy",
        "output_bytes": resolved_output.stat().st_size if exported else 0,
        "export_method": payload.get("export_method"),
        "source_still_open": payload.get("source_still_open"),
        "source_unchanged": source_unchanged,
        "known_losses": NATIVE_COPY_KNOWN_LOSSES,
        "validation_passed": bool(
            exported and source_unchanged and payload.get("source_still_open") and package_ok
        ),
    }
    if not exported:
        return False, export_result, [{"code": EXPORT_OUTPUT_MISSING, "message": "WPS reported success but no copy file was produced."}], False
    if not package_ok:
        return False, export_result, [{
            "code": EXPORT_OUTPUT_NOT_PACKAGE,
            "message": "WPS wrote the output path, but the bytes are not a recognizable Office Open XML package. The source document was left open and unchanged.",
        }], False
    if not source_unchanged:
        return False, export_result, [{"code": "DOCUMENT_CHANGED_AFTER_COM", "message": "The source document changed during export; inspect it before continuing."}], False

    record_operation(request_id, "export-open-document-copy", export_result, workspace)
    return True, export_result, [], False


TEXT_EXPORT_KNOWN_LOSSES = [
    "Plain-text export is lossy: formatting, images, charts, and layout are discarded.",
    "Writer uses WPS text SaveAs; Presentation extracts visible shape text per slide; Spreadsheet uses Unicode/Windows text SaveAs on a temporary copy.",
    "Fidelity depends on the installed WPS build and which shapes/sheets contribute text.",
]


def _looks_like_text(path: Path) -> bool:
    try:
        head = path.read_bytes()[:64]
    except OSError:
        return False
    if not head or head.startswith(b"PK") or head.lstrip().startswith(b"%PDF"):
        return False
    if head.startswith((b"\xff\xfe", b"\xfe\xff", b"\xef\xbb\xbf")):
        return True
    try:
        head.decode("utf-8")
        return True
    except UnicodeDecodeError:
        try:
            head.decode("utf-16")
            return True
        except UnicodeDecodeError:
            return False


@coordinated_mutation
def export_open_document_text(
    document_id: str,
    output: str,
    request_id: str,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]], bool]:
    output_path = Path(output)
    replay = replay_operation(
        request_id,
        "export-open-document-text",
        {"document_id": document_id, "output": str(output_path.resolve())},
        workspace,
    )
    if replay is not None:
        return replay

    document, data, errors = _registered_document(
        document_id, workspace, allowed_components={"writer", "presentation", "spreadsheets"},
    )
    if document is None:
        return False, data, errors, False
    component = document["component"]
    source = Path(document["path"]).resolve()
    resolved_output = output_path.resolve()
    if resolved_output.suffix.lower() not in TEXT_EXPORT_SUFFIXES:
        return False, {}, [{"code": "INVALID_ARGUMENT", "message": "Output must end in .txt; only plain-text export of open Writer, Presentation, or Spreadsheet documents is supported."}], False
    if resolved_output == source:
        return False, {}, [{"code": "INVALID_ARGUMENT", "message": "Output must differ from the source document."}], False
    if resolved_output.exists():
        return False, {"output": str(resolved_output)}, [{"code": OUTPUT_EXISTS, "message": "Output already exists; choose a new path. Nothing was overwritten."}], False
    if not resolved_output.parent.is_dir():
        return False, {"output": str(resolved_output)}, [{"code": "INVALID_ARGUMENT", "message": "Output directory does not exist."}], False

    try:
        identity_before = file_identity(source)
    except OSError as exc:
        return False, {}, [{"code": "DOCUMENT_IDENTITY_UNAVAILABLE", "message": str(exc)}], False

    if component == "writer":
        result = _run_writer_attached_com("export-text", {"path": str(source), "output": str(resolved_output)})
    elif component == "presentation":
        result = _run_presentation_attached_com("export-text", {"path": str(source), "output": str(resolved_output)})
    else:
        result = _run_spreadsheet_attached_com("export-text", {"path": str(source), "output": str(resolved_output)})
    if not result["ok"]:
        return False, {"document_id": document_id, **result["data"]}, result["errors"], False
    payload = result["data"] or {}
    if payload.get("ok") is False:
        return False, {"document_id": document_id, "diagnostic": payload}, [
            {"code": COM_OPERATION_FAILED, "message": str(payload.get("error_message") or "Plain-text export failed.")}
        ], False
    status_error = _status_error(payload.get("status"), str(source), component=component, action="exported")
    if status_error:
        return False, {"document_id": document_id}, [status_error], False

    exported = resolved_output.is_file() and resolved_output.stat().st_size > 0
    try:
        source_unchanged = file_identity(source) == identity_before
    except OSError:
        source_unchanged = False
    text_ok = exported and _looks_like_text(resolved_output)
    export_result = {
        "document_id": document_id,
        "component": component,
        "source_path": str(source),
        "output": str(resolved_output),
        "format": "text",
        "output_bytes": resolved_output.stat().st_size if exported else 0,
        "export_method": payload.get("export_method"),
        "source_still_open": payload.get("source_still_open"),
        "source_unchanged": source_unchanged,
        "known_losses": TEXT_EXPORT_KNOWN_LOSSES,
        "validation_passed": bool(
            exported and source_unchanged and payload.get("source_still_open") and text_ok
        ),
    }
    if not exported:
        return False, export_result, [{"code": EXPORT_OUTPUT_MISSING, "message": "WPS reported success but no text output file was produced."}], False
    if not text_ok:
        return False, export_result, [{
            "code": EXPORT_OUTPUT_NOT_TEXT,
            "message": "WPS wrote the output path, but the bytes are not plain text (for example a package or PDF). The source document was left open and unchanged.",
        }], False
    if not source_unchanged:
        return False, export_result, [{"code": "DOCUMENT_CHANGED_AFTER_COM", "message": "The source document changed during export; inspect it before continuing."}], False

    record_operation(request_id, "export-open-document-text", export_result, workspace)
    return True, export_result, [], False
