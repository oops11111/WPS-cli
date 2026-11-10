param([string]$Out, [string]$LogPath)
$ErrorActionPreference = "Stop"
$log = New-Object System.Collections.ArrayList
function L([string]$m) { [void]$log.Add($m); Write-Output $m }
$app = $null; $doc = $null
try {
  $app = New-Object -ComObject kwps.Application
  $app.Visible = $false
  $app.DisplayAlerts = 0
  $doc = $app.Documents.Add()
  $lines = @(
    "关于开展安全检查的通知",
    "一、总体要求",
    "为切实加强安全生产管理，落实各级责任，现就本次安全检查的总体要求作出如下安排：各单位要高度重视，对照检查清单逐项自查，发现问题立即整改，确保不留死角、不走过场，检查结果按要求及时上报。",
    "（一）工作目标",
    "本次工作目标是全面排查重点部位和关键环节，摸清风险底数，建立问题台账，明确整改责任人和完成时限，确保重大隐患整改率达到百分之百。",
    "1. 具体任务",
    "具体任务包括：开展现场巡查、核对台账资料、抽查值班记录，并在检查结束后两个工作日内提交书面报告。"
  )
  for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($i -eq 0) { $p = $doc.Paragraphs.Item(1) } else { $p = $doc.Paragraphs.Add() }
    $p.Range.Text = $lines[$i]
  }
  $targets = @(@(2,"Heading 1",-2,"标题 1"), @(4,"Heading 2",-3,"标题 2"), @(6,"Heading 3",-4,"标题 3"))
  foreach ($t in $targets) {
    $idx = $t[0]
    try { $doc.Paragraphs.Item($idx).Style = $t[2]; L "paragraph $idx style constant $($t[2]) ok" }
    catch {
      try { $doc.Paragraphs.Item($idx).Style = $t[3]; L "paragraph $idx style '$($t[3])' ok (fallback)" }
      catch { L "paragraph $idx style failed: $($_.Exception.Message)" }
    }
  }
  $p8 = $doc.Paragraphs.Add()
  $tbl = $doc.Tables.Add($p8.Range, 2, 2)
  $tbl.Cell(1,1).Range.Text = "任务"
  $tbl.Cell(1,2).Range.Text = "负责人"
  $tbl.Cell(2,1).Range.Text = "现场检查"
  $tbl.Cell(2,2).Range.Text = "张三"
  L "paragraphs: $($doc.Paragraphs.Count); tables: $($doc.Tables.Count)"
  $footer = [string]$doc.Sections.Item(1).Footers.Item(1).Range.Text
  L "footer text: '" + $footer + "' (length $($footer.Length))"
  $doc.SaveAs($Out, 16)
  L "saved: $Out"
  $doc.Close(0)
  $doc = $null
  $app.Quit()
  $app = $null
} catch {
  L "ERROR: $($_.Exception.GetType().FullName): $($_.Exception.Message)"
} finally {
  if ($doc) { try { $doc.Close(0) } catch { } }
  if ($app) { try { $app.Quit() } catch { } }
  $log | Set-Content -Path $LogPath -Encoding UTF8
}