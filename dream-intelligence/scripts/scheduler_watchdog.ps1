$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_scheduler_common.ps1')

$watchdogLog = Join-Path $script:DsihProjectRoot 'logs\scheduler-watchdog.log'
New-Item -ItemType Directory -Path (Split-Path $watchdogLog) -Force | Out-Null

function Write-WatchdogStatus([string]$status, [int]$processId = 0) {
    if ((Test-Path -LiteralPath $watchdogLog) -and
        (Get-Item -LiteralPath $watchdogLog).Length -gt 1MB) {
        try { Move-Item -LiteralPath $watchdogLog -Destination "$watchdogLog.1" -Force -ErrorAction Stop }
        catch { }
    }
    Add-Content -LiteralPath $watchdogLog -Value "$(Get-Date -Format o) status=$status pid=$processId" -Encoding utf8
    Write-Output $status
}

$task = Get-ScheduledTask -TaskName $script:DsihTaskName -ErrorAction SilentlyContinue
if (-not $task) { Write-WatchdogStatus 'RECOVERY_FAILED'; return }
if (-not $task.Settings.Enabled) { Write-WatchdogStatus 'NOOP_DISABLED'; return }

$processes = @(Get-DsihSchedulerProcess)
if ($processes.Count -eq 1) {
    Write-WatchdogStatus 'NOOP_RUNNING' $processes[0].ProcessId
    return
}
if ($processes.Count -gt 1) { Write-WatchdogStatus 'RECOVERY_FAILED'; return }

# Re-check manual-stop intent immediately before asking Task Scheduler to start.
$task = Get-ScheduledTask -TaskName $script:DsihTaskName -ErrorAction SilentlyContinue
if (-not $task) { Write-WatchdogStatus 'RECOVERY_FAILED'; return }
if (-not $task.Settings.Enabled) { Write-WatchdogStatus 'NOOP_DISABLED'; return }
try { Start-ScheduledTask -TaskName $script:DsihTaskName -ErrorAction Stop }
catch { Write-WatchdogStatus 'RECOVERY_FAILED'; return }

for ($attempt = 0; $attempt -lt 15; $attempt++) {
    Start-Sleep -Seconds 2
    $processes = @(Get-DsihSchedulerProcess)
    if ($processes.Count -eq 1) {
        Write-WatchdogStatus 'RECOVERED' $processes[0].ProcessId
        return
    }
    if ($processes.Count -gt 1) { break }
}
Write-WatchdogStatus 'RECOVERY_FAILED'
