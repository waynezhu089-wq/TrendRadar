$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_scheduler_common.ps1')

$task = Get-ScheduledTask -TaskName $script:DsihTaskName -ErrorAction SilentlyContinue
if ($task) {
    Disable-ScheduledTask -TaskName $script:DsihTaskName | Out-Null
    if ($task.State -eq 'Running') {
        Stop-ScheduledTask -TaskName $script:DsihTaskName
    }
}
Start-Sleep -Seconds 1
$processes = @(Get-DsihSchedulerProcess)
foreach ($process in $processes) {
    # Re-check the exact executable and module immediately before stopping the PID.
    $verified = @(Get-DsihSchedulerProcess | Where-Object { $_.ProcessId -eq $process.ProcessId })
    if ($verified.Count -eq 1) {
        Stop-Process -Id $process.ProcessId -ErrorAction SilentlyContinue
    }
}
Start-Sleep -Seconds 1
$remaining = @(Get-DsihSchedulerProcess)
if ($remaining.Count -gt 0) { throw 'DSIH_SCHEDULER_STOP_FAILED' }
New-Item -ItemType Directory -Path (Split-Path $script:DsihLog) -Force | Out-Null
Add-Content -LiteralPath $script:DsihLog -Value "$(Get-Date -Format o) SCHEDULER_STOPPED_BY_USER" -Encoding utf8
Write-Output 'SCHEDULER_STOPPED'
