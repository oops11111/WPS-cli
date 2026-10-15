"""Undo a saved selection write inside WPS (P7-001).

A write to a document that WPS has open is saved by WPS, and WPS holds the file, so a failed write cannot be undone
by copying the pre-write backup over it. These bodies undo it in the same WPS instance with the inverse edit: they
put the original text or cells back where the write changed them, read the result back and save.

Each body first checks that the place it is about to change still holds exactly what the write left there. If it
does not, for example because the user edited the document in the meantime, it changes nothing and reports
'revert_mismatch'. The Presentation and Spreadsheets bodies can also tell that the place already holds the
original (the write did not stick) and report 'unchanged'; a Writer range cannot tell that apart from text that
merely looks the same, so the Writer body does not try. If the inverse edit does not read back as the original,
the body does not save and reports 'revert_read_back_failed', so the document is never saved in a state nobody
checked.
"""

from __future__ import annotations

_SELECTION_REVERT_BODY = """
  if ([bool]$doc.ReadOnly) {
    [pscustomobject]@{ ok = $true; status = 'read_only' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $start = [int]$params.start
  $written = [string]$params.written_text
  $original = [string]$params.original_text
  $range = $doc.Range($start, $start + $written.Length)
  $current = [string]$range.Text
  if ($current -cne $written) {
    [pscustomobject]@{ ok = $true; status = 'revert_mismatch'; current_text = $current } | ConvertTo-Json -Depth 5
    exit 0
  }
  $range.Text = $original
  $readBack = [string]$doc.Range($start, $start + $original.Length).Text
  if ($readBack -cne $original) {
    [pscustomobject]@{
      ok = $true
      status = 'revert_read_back_failed'
      read_back_text = $readBack
      saved = [bool]$doc.Saved
    } | ConvertTo-Json -Depth 5
    exit 0
  }
  $doc.Save()
  [pscustomobject]@{
    ok = $true
    status = 'reverted'
    backend = 'powershell-com'
    component = 'writer'
    read_back_text = $readBack
    saved = [bool]$doc.Saved
  } | ConvertTo-Json -Depth 5
"""

_PRESENTATION_SELECTION_REVERT_BODY = """
  if ([bool]$doc.ReadOnly) {
    [pscustomobject]@{ ok = $true; status = 'read_only' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $shape = $null
  try { $shape = $doc.Slides.Item([int]$params.slide_index).Shapes.Item([string]$params.shape_name) } catch { }
  if ($null -eq $shape) {
    [pscustomobject]@{ ok = $true; status = 'revert_target_missing' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $frame = $shape.TextFrame.TextRange
  $current = [string]$frame.Text
  if ($current -ceq [string]$params.frame_restored) {
    [pscustomobject]@{ ok = $true; status = 'unchanged'; read_back_text = $current } | ConvertTo-Json -Depth 5
    exit 0
  }
  if ($current -cne [string]$params.frame_expected) {
    [pscustomobject]@{ ok = $true; status = 'revert_mismatch'; current_text = $current } | ConvertTo-Json -Depth 5
    exit 0
  }
  # TextRange.Characters is 1-based, like TextRange.Start that the write reported.
  $range = $frame.Characters([int]$params.start, ([string]$params.written_text).Length)
  $range.Text = [string]$params.original_text
  $readBack = [string]$shape.TextFrame.TextRange.Text
  if ($readBack -cne [string]$params.frame_restored) {
    [pscustomobject]@{
      ok = $true
      status = 'revert_read_back_failed'
      read_back_text = $readBack
      saved = [bool]$doc.Saved
    } | ConvertTo-Json -Depth 5
    exit 0
  }
  $doc.Save()
  [pscustomobject]@{
    ok = $true
    status = 'reverted'
    backend = 'powershell-com'
    component = 'presentation'
    read_back_text = $readBack
    saved = [bool]$doc.Saved
  } | ConvertTo-Json -Depth 5
"""

_SPREADSHEET_SELECTION_REVERT_BODY = """
  if ([bool]$doc.ReadOnly) {
    [pscustomobject]@{ ok = $true; status = 'read_only' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $sheet = $null
  $target = $null
  try {
    $sheet = $doc.Worksheets.Item([string]$params.sheet_name)
    $target = $sheet.Range([string]$params.address)
  } catch { }
  if ($null -eq $target) {
    [pscustomobject]@{ ok = $true; status = 'revert_target_missing' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $cells = New-Object System.Collections.Generic.List[object]
  foreach ($area in $target.Areas) {
    foreach ($cell in $area.Cells) { $cells.Add($cell) }
  }
  $before = @($params.before_cells)
  $after = @($params.after_formulas)
  if ($cells.Count -ne $before.Count -or $cells.Count -ne $after.Count) {
    [pscustomobject]@{ ok = $true; status = 'revert_mismatch'; cell_count = $cells.Count } | ConvertTo-Json -Depth 5
    exit 0
  }
  $current = New-Object System.Collections.Generic.List[string]
  $unchanged = $true
  for ($i = 0; $i -lt $cells.Count; $i++) {
    $formula = [string]$cells[$i].Formula
    $current.Add($formula)
    if ($formula -cne [string]$after[$i]) { $unchanged = $false }
  }
  if (-not $unchanged) {
    $original = $true
    for ($i = 0; $i -lt $cells.Count; $i++) {
      if ($current[$i] -cne [string]$before[$i].formula) { $original = $false }
    }
    $status = if ($original) { 'unchanged' } else { 'revert_mismatch' }
    [pscustomobject]@{ ok = $true; status = $status; current_formulas = $current } | ConvertTo-Json -Depth 5
    exit 0
  }
  for ($i = 0; $i -lt $cells.Count; $i++) {
    $cell = $cells[$i]
    $original = $before[$i]
    $formula = [string]$original.formula
    if ([bool]$original.text_constant) {
      # Value2 keeps text as text in most cells; text that WPS would read as a number needs the quote prefix.
      $cell.Value2 = $formula
      if (([string]$cell.Formula) -cne $formula) { $cell.Formula = "'" + $formula }
    } elseif ($formula.Length -eq 0) {
      $cell.Value2 = $null
    } else {
      $cell.Formula = $formula
    }
  }
  $readBack = New-Object System.Collections.Generic.List[string]
  $restored = $true
  for ($i = 0; $i -lt $cells.Count; $i++) {
    $formula = [string]$cells[$i].Formula
    $readBack.Add($formula)
    if ($formula -cne [string]$before[$i].formula) { $restored = $false }
  }
  if (-not $restored) {
    [pscustomobject]@{
      ok = $true
      status = 'revert_read_back_failed'
      read_back_formulas = $readBack
      saved = [bool]$doc.Saved
    } | ConvertTo-Json -Depth 5
    exit 0
  }
  $doc.Save()
  [pscustomobject]@{
    ok = $true
    status = 'reverted'
    backend = 'powershell-com'
    component = 'spreadsheets'
    read_back_formulas = $readBack
    saved = [bool]$doc.Saved
  } | ConvertTo-Json -Depth 5
"""

# Collected by the cell write bodies before they write: what each selected cell held, in Areas then Cells order.
SPREADSHEET_CAPTURE_BEFORE_CELLS = """
  $beforeCells = New-Object System.Collections.Generic.List[object]
  $sheetName = $null
  try { $sheetName = [string]$sel.Worksheet.Name } catch { }
  foreach ($area in $sel.Areas) {
    foreach ($cell in $area.Cells) {
      $formula = ''
      $textConstant = $false
      try { $formula = [string]$cell.Formula } catch { }
      try { $textConstant = (-not [bool]$cell.HasFormula) -and ($cell.Value2 -is [string]) } catch { }
      $beforeCells.Add([pscustomobject]@{ formula = $formula; text_constant = [bool]$textConstant })
    }
  }
"""

# Collected after the write is saved: what the write left in each cell, so a revert can check nothing else changed.
SPREADSHEET_CAPTURE_AFTER_FORMULAS = """
  $afterFormulas = New-Object System.Collections.Generic.List[string]
  foreach ($area in $sel.Areas) {
    foreach ($cell in $area.Cells) {
      $formula = ''
      try { $formula = [string]$cell.Formula } catch { }
      $afterFormulas.Add($formula)
    }
  }
"""

# Collected by the presentation write bodies before they write: where the selection is, so a revert can find the
# shape again after WPS has moved the selection (P6-008).
PRESENTATION_CAPTURE_REVERT_TARGET = """
  $revertSlideIndex = $null
  $revertShapeName = $null
  $revertStart = $null
  $revertFrameBefore = $null
  try { $revertSlideIndex = [int]$sel.SlideRange.SlideIndex } catch { }
  if ($null -ne $shape) {
    try { $revertShapeName = [string]$shape.Name } catch { }
    try { $revertFrameBefore = [string]$shape.TextFrame.TextRange.Text } catch { }
  }
  try { $revertStart = [int]$tr.Start } catch { }
"""
