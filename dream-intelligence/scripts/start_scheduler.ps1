$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_scheduler_common.ps1')

$task = Get-ScheduledTask -TaskName $script:DsihTaskName -ErrorAction Stop
if (-not $task.Settings.Enabled) {
    Enable-ScheduledTask -TaskName $script:DsihTaskName | Out-Null
}
Start-ScheduledTask -TaskName $script:DsihTaskName
Write-Output 'SCHEDULER_TASK_START_REQUESTED'
