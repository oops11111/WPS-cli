"""Spreadsheets: the attach wrapper, selection read and edit, shape text, and exports."""

from __future__ import annotations

from ..wps_script_snippets import ATTACH_RUNNING_INSTANCE
from .common import _SCRIPT_HEAD

MAX_SPREADSHEET_SELECTION_SAMPLE_CELLS = 100

_ATTACHED_SPREADSHEET_WRAPPER = (
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
