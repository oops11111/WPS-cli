param(
    [string]$Python = "C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe",
    [string]$RunId = (Get-Date -Format "yyyyMMddTHHmmss")
)

$ErrorActionPreference = "Stop"
$env:PYTHONPATH = "src"

New-Item -ItemType Directory -Force -Path "artifacts\local-repro" | Out-Null

$steps = @(
    @{
        Name = "unit-tests"
        Command = @($Python, "-m", "unittest", "discover", "-s", "tests")
    },
    @{
        Name = "cleanup-plan"
        Command = @($Python, "-m", "wps_ai_agent_cli", "cleanup-plan", "--request-id", "local-repro-$RunId-cleanup")
    },
    @{
        Name = "safe-regression"
        Command = @($Python, "-m", "wps_ai_agent_cli", "regression-run", "--profile", "safe", "--artifact-dir", "artifacts\regression\safe", "--request-id", "local-repro-$RunId-safe")
    }
)

$results = @()

foreach ($step in $steps) {
    $started = Get-Date
    Write-Host "==> $($step.Name)"
    $exe = $step.Command[0]
    $args = $step.Command[1..($step.Command.Count - 1)]
    & $exe @args
    $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
    $finished = Get-Date
    $results += [ordered]@{
        name = $step.Name
        exit_code = $exitCode
        started_at = $started.ToString("o")
        finished_at = $finished.ToString("o")
        duration_seconds = [math]::Round(($finished - $started).TotalSeconds, 3)
    }
    if ($exitCode -ne 0) {
        throw "Step failed: $($step.Name) exited with $exitCode"
    }
}

$summary = [ordered]@{
    run_id = $RunId
    workspace = (Get-Location).Path
    python = $Python
    steps = $results
}

$summaryPath = "artifacts\local-repro\local-repro-$RunId.json"
$summary | ConvertTo-Json -Depth 6 | Set-Content -Path $summaryPath -Encoding UTF8
Write-Host "Local reproducibility bundle passed: $summaryPath"
