"""Pieces shared by every component: the script head, the open-document list, untitled Save As and Save."""

from __future__ import annotations

from ..wps_script_snippets import ATTACH_RUNNING_INSTANCE

_SCRIPT_HEAD = """
$ErrorActionPreference = 'Stop'
$params = @'
__PARAMS_JSON__
'@ | ConvertFrom-Json
"""

_LIST_SCRIPT = (
    _SCRIPT_HEAD
    + ATTACH_RUNNING_INSTANCE
    + """
function Get-Safe([scriptblock]$block) { try { return & $block } catch { return $null } }
$instances = @()
$unreachable = @()
foreach ($spec in $params.components) {
  $app = Get-RunningWpsApp @($spec.prog_ids)
  if ($null -eq $app) {
    if ((Get-WpsMissingStatus @($spec.prog_ids)) -eq 'not_automatable') { $unreachable += [string]$spec.component }
    continue
  }
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
      attached_via = $script:WpsAttachedVia
      documents = $documents
    }
  } finally {
    try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) } catch { }
  }
}
[pscustomobject]@{ ok = $true; backend = 'powershell-com'; instances = $instances; not_automatable = @($unreachable) } | ConvertTo-Json -Depth 6
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
    [pscustomobject]@{ ok = $true; status = (Get-WpsMissingStatus @($params.prog_ids)) } | ConvertTo-Json -Depth 5
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

# Close the open document without saving, but only when WPS reports no unsaved changes, so nothing the user
# typed is lost. With do_close false it only reports what it would do.
_CLOSE_UNCHANGED_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved'; saved = $false; closed = $false } | ConvertTo-Json -Depth 5
    exit 0
  }
  if (-not [bool]$params.do_close) {
    [pscustomobject]@{ ok = $true; status = 'open'; saved = $true; closed = $false } | ConvertTo-Json -Depth 5
    exit 0
  }
  switch ([string]$params.component) {
    'writer' { [void]$doc.Close(0) }
    # Close($false) on a workbook reached through the Running Object Table failed with RPC_E_SERVERFAULT on
    # WPS 12.8 (P7-007). The document has no unsaved changes here, so Close() with no argument cannot prompt.
    'spreadsheets' { try { [void]$doc.Close() } catch { [void]$doc.Close($false) } }
    default { [void]$doc.Close() }
  }
  [pscustomobject]@{ ok = $true; status = 'closed'; saved = $true; closed = $true } | ConvertTo-Json -Depth 5
"""
