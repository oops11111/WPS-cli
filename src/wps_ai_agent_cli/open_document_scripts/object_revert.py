"""Undo a saved write to a worksheet shape or chart inside WPS (P10-004).

P7-001 undoes cell writes; a write to a shape's text, a chart title, an axis title or a series' values was left as
'unsupported'. These bodies undo it the same way: find the object the write changed, check it still holds what the
write left there, put the original back, read it back and save.

They find the object exactly as the write did, through the current selection, by reusing the opening of the write
body up to where it reads the old value: a selection write in WPS does not move the selection, and the undo runs
right after the write in the same command. If the selection has moved, the opening reports 'selection_changed',
'no_window' or 'not_..._selection', and open_documents treats that as 'revert_target_missing': nothing is changed.

A series is restored through its SERIES formula when the write recorded one, so a series that read its values from
cells reads them from those cells again; otherwise the recorded values are written back.
"""

from __future__ import annotations

from .spreadsheet import _SPREADSHEET_SHAPE_TEXT_REPLACE_BODY
from .spreadsheet_charts import (
    _SPREADSHEET_AXIS_TITLE_REPLACE_BODY,
    _SPREADSHEET_CHART_TITLE_REPLACE_BODY,
    _SPREADSHEET_SERIES_VALUES_REPLACE_BODY,
)


def _opening(body: str, marker: str) -> str:
    """The part of a write body that finds the selected object and checks its name, before it reads the old value."""
    index = body.index(marker)
    opening = body[:index]
    # A write refuses a document with unsaved changes; the undo runs right after the write saved it, and must not be
    # refused when WPS marks the document changed again in between, so it drops that check.
    unsaved = """  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
"""
    return opening.replace(unsaved, "", 1)


def _finish(component_read: str) -> str:
    """Check, put back, read back and save; `component_read` sets $current from the object."""
    return f"""
  $original = [string]$params.original_text
  $written = [string]$params.written_text
{component_read}
  if ($null -eq $current) {{
    [pscustomobject]@{{ ok = $true; status = 'revert_target_missing' }} | ConvertTo-Json -Depth 5
    exit 0
  }}
  if ($current -ceq $original) {{
    [pscustomobject]@{{ ok = $true; status = 'unchanged'; read_back_text = $current }} | ConvertTo-Json -Depth 5
    exit 0
  }}
  # The object holds what the command wrote, or what WPS read back after the write when that differed.
  if ($current -cne $written -and $current -cne [string]$params.read_back_text) {{
    [pscustomobject]@{{ ok = $true; status = 'revert_mismatch'; current_text = $current }} | ConvertTo-Json -Depth 5
    exit 0
  }}
  try {{ Restore-WpsObject }} catch {{ }}
{component_read.replace("$current", "$readBack")}
  if ($readBack -cne $original) {{
    [pscustomobject]@{{
      ok = $true
      status = 'revert_read_back_failed'
      read_back_text = $readBack
      saved = [bool]$doc.Saved
    }} | ConvertTo-Json -Depth 5
    exit 0
  }}
  $doc.Save()
  [pscustomobject]@{{
    ok = $true
    status = 'reverted'
    backend = 'powershell-com'
    component = 'spreadsheets'
    read_back_text = $readBack
    saved = [bool]$doc.Saved
  }} | ConvertTo-Json -Depth 5
"""


_SHAPE_READ = """  $current = $null
  try {
    try { $current = [string]$shape.TextFrame.Characters().Text }
    catch { $current = [string]$shape.TextFrame.Characters.Text }
  } catch { }"""

_SHAPE_RESTORE = """
  function Restore-WpsObject {
    $chars = $null
    try { $chars = $shape.TextFrame.Characters() } catch { $chars = $shape.TextFrame.Characters }
    $chars.Text = [string]$params.original_text
  }
"""

_CHART_TITLE_READ = """  $current = $null
  try {
    if ([bool]$chartCom.HasTitle) { $current = [string]$chartCom.ChartTitle.Text } else { $current = '' }
  } catch { }"""

_CHART_TITLE_RESTORE = """
  function Restore-WpsObject {
    if (-not [bool]$chartCom.HasTitle) { $chartCom.HasTitle = $true }
    $chartCom.ChartTitle.Text = [string]$params.original_text
  }
"""

_AXIS_TITLE_READ = """  $current = $null
  try {
    if ([bool]$axis.HasTitle) { $current = [string]$axis.AxisTitle.Text } else { $current = '' }
  } catch { }"""

_AXIS_TITLE_RESTORE = """
  function Restore-WpsObject {
    if (-not [bool]$axis.HasTitle) { $axis.HasTitle = $true }
    $axis.AxisTitle.Text = [string]$params.original_text
  }
"""

_SERIES_READ = """  $current = $null
  try {
    $parts = New-Object System.Collections.Generic.List[string]
    foreach ($value in @($series.Values)) {
      if ($null -eq $value) { [void]$parts.Add('') } else { [void]$parts.Add([string]$value) }
    }
    $current = [string]::Join([char]9, $parts)
  } catch { }"""

_SERIES_RESTORE = """
  function Restore-WpsObject {
    $formula = [string]$params.original_formula
    if (-not [string]::IsNullOrEmpty($formula)) {
      try { $series.Formula = $formula; return } catch { }
    }
    $pieces = ([string]$params.original_text).Split([char]9)
    $values = New-Object object[] $pieces.Count
    for ($i = 0; $i -lt $pieces.Count; $i++) {
      $num = 0.0
      if ([string]::IsNullOrEmpty($pieces[$i])) { $values[$i] = $null }
      elseif ([double]::TryParse($pieces[$i], [ref]$num)) { $values[$i] = $num }
      else { $values[$i] = $pieces[$i] }
    }
    $series.Values = $values
  }
"""

_SPREADSHEET_SHAPE_TEXT_REVERT_BODY = (
    _opening(_SPREADSHEET_SHAPE_TEXT_REPLACE_BODY, "  $before = ''\n") + _SHAPE_RESTORE + _finish(_SHAPE_READ)
)
_SPREADSHEET_CHART_TITLE_REVERT_BODY = (
    _opening(_SPREADSHEET_CHART_TITLE_REPLACE_BODY, "  $before = ''\n")
    + _CHART_TITLE_RESTORE
    + _finish(_CHART_TITLE_READ)
)
_SPREADSHEET_AXIS_TITLE_REVERT_BODY = (
    _opening(_SPREADSHEET_AXIS_TITLE_REPLACE_BODY, "  $before = ''\n") + _AXIS_TITLE_RESTORE + _finish(_AXIS_TITLE_READ)
)
_SPREADSHEET_SERIES_VALUES_REVERT_BODY = (
    _opening(_SPREADSHEET_SERIES_VALUES_REPLACE_BODY, "  $beforeParts = New-Object")
    + _SERIES_RESTORE
    + _finish(_SERIES_READ)
)

# fill_mode of the write -> the attached-script action that undoes it.
OBJECT_REVERT_ACTIONS = {
    "shape_text": "selection-shape-revert",
    "chart_title": "selection-chart-title-revert",
    "axis_title": "selection-axis-title-revert",
    "series_values": "selection-series-values-revert",
}
