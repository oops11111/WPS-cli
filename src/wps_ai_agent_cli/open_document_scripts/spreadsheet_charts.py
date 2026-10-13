"""Spreadsheet chart selections: chart title, axis title and series values."""

from __future__ import annotations

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
