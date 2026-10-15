<#
.SYNOPSIS
  Read-only diagnostic of how running WPS processes register for automation (P6-001).

.DESCRIPTION
  Records, as JSON:
  - for every WPS ProgID: whether it is registered and whether GetActiveObject returns a running application,
    with the application's name, version and open documents when it does;
  - every entry in the Running Object Table (ROT): its display name, and for entries that end with a WPS
    document extension, the registered object's application name, path and version and the document's
    FullName, read from the object the ROT already holds;
  - every process whose name starts with wps, et, wpp, ksolaunch or wpscloud: id, session, whether it has a
    main window, the window title and the command line.

  It never opens, closes, saves or activates a document, never starts WPS (GetActiveObject and the ROT only
  return objects that are already registered) and never ends a process.

.PARAMETER Out
  File to write the JSON to. Without it the JSON goes to standard output.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File automation-diagnostic.ps1 -Out $env:TEMP\wps-p6\diag-writer-doubleclick.json
#>
param([string]$Out)

$ErrorActionPreference = 'Stop'

Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
namespace WpsAgentDiagnostic {
  public class RotEntry {
    public string DisplayName;
    public object Value;
    public string Error;
  }
  public static class Probe {
    [DllImport("ole32.dll")]
    private static extern int CLSIDFromProgID([MarshalAs(UnmanagedType.LPWStr)] string progId, out Guid clsid);
    [DllImport("oleaut32.dll")]
    private static extern int GetActiveObject(ref Guid rclsid, IntPtr reserved, [MarshalAs(UnmanagedType.IUnknown)] out object obj);
    [DllImport("ole32.dll")]
    private static extern int GetRunningObjectTable(int reserved, out IRunningObjectTable rot);
    [DllImport("ole32.dll")]
    private static extern int CreateBindCtx(int reserved, out IBindCtx context);

    public static string ClsidOf(string progId) {
      Guid clsid;
      int hr = CLSIDFromProgID(progId, out clsid);
      return hr == 0 ? clsid.ToString("B") : null;
    }
    public static object Active(string progId, out int hresult) {
      Guid clsid;
      hresult = CLSIDFromProgID(progId, out clsid);
      if (hresult != 0) { return null; }
      object obj;
      hresult = GetActiveObject(ref clsid, IntPtr.Zero, out obj);
      return hresult == 0 ? obj : null;
    }
    // Every ROT entry. The object is fetched only for names that end with one of the extensions.
    public static RotEntry[] Entries(string[] extensions) {
      List<RotEntry> entries = new List<RotEntry>();
      IRunningObjectTable rot;
      IBindCtx context;
      int hr = GetRunningObjectTable(0, out rot);
      if (hr != 0) { throw new COMException("GetRunningObjectTable failed", hr); }
      hr = CreateBindCtx(0, out context);
      if (hr != 0) { throw new COMException("CreateBindCtx failed", hr); }
      IEnumMoniker monikers;
      rot.EnumRunning(out monikers);
      IMoniker[] one = new IMoniker[1];
      while (monikers.Next(1, one, IntPtr.Zero) == 0) {
        RotEntry entry = new RotEntry();
        try { one[0].GetDisplayName(context, null, out entry.DisplayName); }
        catch (Exception e) { entry.Error = "GetDisplayName: " + e.Message; entries.Add(entry); continue; }
        foreach (string extension in extensions) {
          if (entry.DisplayName == null || !entry.DisplayName.EndsWith(extension, StringComparison.OrdinalIgnoreCase)) { continue; }
          object value;
          int got = rot.GetObject(one[0], out value);
          if (got == 0) { entry.Value = value; } else { entry.Error = "GetObject HRESULT 0x" + got.ToString("X8"); }
          break;
        }
        entries.Add(entry);
      }
      return entries.ToArray();
    }
  }
}
"@

function Get-Safe([scriptblock]$block) { try { return & $block } catch { return $null } }

$components = [ordered]@{
  writer = @{ prog_ids = @('kwps.Application', 'wps.Application', 'Kingsoft Writer.Application'); collection = 'Documents' }
  spreadsheets = @{ prog_ids = @('ket.Application', 'et.Application', 'Kingsoft Spreadsheets.Application'); collection = 'Workbooks' }
  presentation = @{ prog_ids = @('kwpp.Application', 'wpp.Application', 'Kingsoft Presentation.Application'); collection = 'Presentations' }
}
$extensions = @(
  '.docx', '.doc', '.wps', '.wpt', '.dotx', '.dot', '.rtf', '.docm',
  '.xlsx', '.xls', '.et', '.ett', '.xlsm', '.xltx', '.csv',
  '.pptx', '.ppt', '.dps', '.dpt', '.pptm', '.potx'
)

function Get-DocumentNames($app, [string]$collection) {
  $names = @()
  $items = Get-Safe { $app.$collection }
  if ($null -eq $items) { return $names }
  $count = [int](Get-Safe { $items.Count })
  for ($i = 1; $i -le $count; $i++) {
    $names += Get-Safe { [string]$items.Item($i).FullName }
  }
  return $names
}

$progIds = @()
foreach ($name in $components.Keys) {
  foreach ($progId in $components[$name].prog_ids) {
    $hresult = 0
    $app = $null
    $failure = $null
    try { $app = [WpsAgentDiagnostic.Probe]::Active($progId, [ref]$hresult) } catch { $failure = $_.Exception.Message }
    $progIds += [pscustomobject]@{
      component = $name
      prog_id = $progId
      clsid = Get-Safe { [WpsAgentDiagnostic.Probe]::ClsidOf($progId) }
      active_object = ($null -ne $app)
      hresult = ('0x{0:X8}' -f $hresult)
      error = $failure
      app_name = Get-Safe { [string]$app.Name }
      app_path = Get-Safe { [string]$app.Path }
      version = Get-Safe { [string]$app.Version }
      documents = @(Get-DocumentNames $app $components[$name].collection)
    }
    if ($null -ne $app) { try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) } catch { } }
  }
}

$rot = @()
$rotError = $null
$entries = @()
try { $entries = @([WpsAgentDiagnostic.Probe]::Entries([string[]]$extensions)) } catch { $rotError = $_.Exception.Message }
foreach ($entry in $entries) {
  if ($null -eq $entry) { continue }
  $value = $entry.Value
  $rot += [pscustomobject]@{
    display_name = $entry.DisplayName
    error = $entry.Error
    is_wps_extension = ($null -ne $value -or ($entry.Error -like 'GetObject*'))
    document_full_name = Get-Safe { [string]$value.FullName }
    app_name = Get-Safe { [string]$value.Application.Name }
    app_path = Get-Safe { [string]$value.Application.Path }
    app_version = Get-Safe { [string]$value.Application.Version }
  }
}

$processes = @()
$mySession = [System.Diagnostics.Process]::GetCurrentProcess().SessionId
$commandLines = @{}
try {
  foreach ($row in @(Get-CimInstance Win32_Process -ErrorAction Stop)) { $commandLines[[int]$row.ProcessId] = [string]$row.CommandLine }
} catch { }
foreach ($process in @(Get-Process | Where-Object { $_.ProcessName -match '^(wps|et|wpp|ksolaunch|wpscloud)' })) {
  $processes += [pscustomobject]@{
    name = $process.ProcessName
    id = $process.Id
    session = $process.SessionId
    same_session = ($process.SessionId -eq $mySession)
    has_main_window = ([int64]$process.MainWindowHandle -ne 0)
    window_title = Get-Safe { [string]$process.MainWindowTitle }
    command_line = $commandLines[[int]$process.Id]
  }
}

$report = [pscustomobject]@{
  tool = 'automation-diagnostic'
  generated_at = (Get-Date).ToUniversalTime().ToString('o')
  platform = [string][System.Environment]::OSVersion.Platform
  os_version = [string][System.Environment]::OSVersion.VersionString
  powershell = $PSVersionTable.PSVersion.ToString()
  prog_ids = $progIds
  running_object_table = [pscustomobject]@{ error = $rotError; entries = $rot }
  processes = $processes
}
$json = $report | ConvertTo-Json -Depth 6
if ($Out) {
  $directory = Split-Path -Parent $Out
  if ($directory) { New-Item -ItemType Directory -Force $directory | Out-Null }
  Set-Content -Path $Out -Value $json -Encoding UTF8
  Write-Output "written: $Out"
} else {
  Write-Output $json
}
