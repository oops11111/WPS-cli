param(
  [Parameter(Mandatory=$true)][string]$Baseline,
  [Parameter(Mandatory=$true)][string]$Candidate,
  [Parameter(Mandatory=$true)][string]$Out
)

$ErrorActionPreference = 'Stop'
$reportOut = $Out
. "$PSScriptRoot/real_wps_verify_p6/automation-diagnostic.ps1" -Out "$reportOut.rot.json" | Out-Null

function Read-Safe([scriptblock]$Block) {
  try { return & $Block } catch { return @{ error = $_.Exception.Message } }
}

$entries = [WpsAgentDiagnostic.Probe]::Entries(@('.pptx'))
$records = @()
foreach ($deck in @($Baseline, $Candidate)) {
  $path = (Resolve-Path -LiteralPath $deck).Path
  $matches = @($entries | Where-Object { $_.DisplayName -eq $path })
  $record = [ordered]@{ deck=$path; rot_matches=$matches.Count; slide5_effects=@(); errors=@() }
  if ($matches.Count -ne 1 -or $null -eq $matches[0].Value) {
    $record.errors += 'Deck not uniquely registered in ROT.'
  } else {
    $doc = $matches[0].Value
    $record.slide_count = Read-Safe { [int]$doc.Slides.Count }
    $slide = $doc.Slides.Item(5)
    $count = Read-Safe { [int]$slide.TimeLine.MainSequence.Count }
    $record.slide5_effect_count = $count
    if ($count -is [int]) {
      for ($i=1; $i -le $count; $i++) {
        $effect = $slide.TimeLine.MainSequence.Item($i)
        $record.slide5_effects += [ordered]@{
          order=$i
          effect_type=Read-Safe { [int]$effect.EffectType }
          shape_name=Read-Safe { [string]$effect.Shape.Name }
          shape_text=Read-Safe { [string]$effect.Shape.TextFrame.TextRange.Text }
          text_range_start=Read-Safe { [int]$effect.TextRangeStart }
          text_range_length=Read-Safe { [int]$effect.TextRangeLength }
          paragraph=Read-Safe { [int]$effect.Paragraph }
          trigger_type=Read-Safe { [int]$effect.Timing.TriggerType }
          delay_seconds=Read-Safe { [double]$effect.Timing.TriggerDelayTime }
          duration_seconds=Read-Safe { [double]$effect.Timing.Duration }
        }
      }
    }
  }
  $records += $record
}
@{generated_at_utc=(Get-Date).ToUniversalTime().ToString('o');records=$records} |
  ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $reportOut -Encoding utf8
