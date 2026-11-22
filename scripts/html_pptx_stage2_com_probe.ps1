param(
  [Parameter(Mandatory=$true)][string]$Deck,
  [Parameter(Mandatory=$true)][string]$Out
)

$ErrorActionPreference = 'Stop'
$reportOut = $Out
. "$PSScriptRoot/real_wps_verify_p6/automation-diagnostic.ps1" -Out "$reportOut.diagnostic.json" | Out-Null

function Read-Safe([scriptblock]$Block) {
  try { return & $Block } catch { return @{ error = $_.Exception.Message } }
}

$path = (Resolve-Path -LiteralPath $Deck).Path
$entry = @([WpsAgentDiagnostic.Probe]::Entries(@('.pptx')) | Where-Object { $_.DisplayName -eq $path })
$result = [ordered]@{
  generated_at = (Get-Date).ToUniversalTime().ToString('o')
  deck = $path
  rot_matches = $entry.Count
  presentation = $null
  errors = @()
}
if ($entry.Count -ne 1 -or $null -eq $entry[0].Value) {
  $result.errors += 'Expected exactly one loaded disposable deck in ROT.'
} else {
  $doc = $entry[0].Value
  $slides = @()
  $count = Read-Safe { [int]$doc.Slides.Count }
  if ($count -is [int]) {
    for ($slideNumber=1; $slideNumber -le $count; $slideNumber++) {
      $slide = $doc.Slides.Item($slideNumber)
      $effectCount = Read-Safe { [int]$slide.TimeLine.MainSequence.Count }
      $effects = @()
      if ($effectCount -is [int]) {
        for ($effectNumber=1; $effectNumber -le $effectCount; $effectNumber++) {
          $effect = $slide.TimeLine.MainSequence.Item($effectNumber)
          $effects += [ordered]@{
            order = $effectNumber
            effect_type = Read-Safe { [int]$effect.EffectType }
            shape_name = Read-Safe { [string]$effect.Shape.Name }
            trigger_type = Read-Safe { [int]$effect.Timing.TriggerType }
            trigger_delay_seconds = Read-Safe { [double]$effect.Timing.TriggerDelayTime }
            duration_seconds = Read-Safe { [double]$effect.Timing.Duration }
          }
        }
      }
      $slides += [ordered]@{
        number = $slideNumber
        effect_count = $effectCount
        effects = $effects
        transition_entry_effect = Read-Safe { [int]$slide.SlideShowTransition.EntryEffect }
        notes_shape_count = Read-Safe { [int]$slide.NotesPage.Shapes.Count }
      }
    }
  }
  $result.presentation = [ordered]@{
    name = Read-Safe { [string]$doc.Name }
    full_name = Read-Safe { [string]$doc.FullName }
    slide_count = $count
    slideshow_window_count = Read-Safe { [int]$doc.Application.SlideShowWindows.Count }
    slides = $slides
  }
}
$result | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $reportOut -Encoding utf8
