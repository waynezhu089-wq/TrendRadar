$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_scheduler_common.ps1')

$task = Get-ScheduledTask -TaskName $script:DsihTaskName -ErrorAction SilentlyContinue
$processes = @(Get-DsihSchedulerProcess)
[pscustomobject]@{
    task_exists = [bool]$task
    task_enabled = if ($task) { $task.Settings.Enabled } else { $false }
    task_state = if ($task) { [string]$task.State } else { 'MISSING' }
    scheduler_process_running = $processes.Count -gt 0
    scheduler_pids = @($processes | ForEach-Object { $_.ProcessId })
    log_path = $script:DsihLog
    log_exists = Test-Path -LiteralPath $script:DsihLog -PathType Leaf
} | ConvertTo-Json -Compress
