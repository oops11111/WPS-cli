"""Presentation: the attach wrapper, selection read and edit, and exports."""

from __future__ import annotations

from ..wps_script_snippets import ATTACH_RUNNING_INSTANCE
from .common import _SCRIPT_HEAD

_ATTACHED_PRESENTATION_WRAPPER = (
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
