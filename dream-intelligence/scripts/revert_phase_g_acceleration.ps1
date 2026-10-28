param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_scheduler_common.ps1')

$revertTaskName = 'Dream Intelligence Phase G Revert'
$windowPath = Join-Path $script:DsihProjectRoot 'docs\evidence\dsih-g01-window.json'
$statePath = Join-Path $script:DsihProjectRoot 'data\phase_g_acceleration.json'
$resultPath = Join-Path $script:DsihProjectRoot 'docs\evidence\dsih-g01-revert-result.json'

if (-not (Test-Path -LiteralPath $windowPath -PathType Leaf)) { throw 'PHASE_G_WINDOW_MISSING' }
if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) { throw 'PHASE_G_STATE_MISSING' }
$window = Get-Content -LiteralPath $windowPath -Raw | ConvertFrom-Json
$state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
if ($state.start_at -ne $window.PHASE_G_START_AT -or
    $state.end_at -ne $window.PHASE_G_END_AT) { throw 'PHASE_G_WINDOW_MISMATCH' }
if ($CheckOnly) {
    $task = Get-ScheduledTask -TaskName $revertTaskName -ErrorAction Stop
    $expected = [DateTimeOffset]::Parse($window.PHASE_G_END_AT).ToString('yyyy-MM-ddTHH:mm:sszzz')
    if (-not $state.active -or -not $task.Settings.Enabled -or
        $task.Triggers[0].StartBoundary -ne $expected) { throw 'PHASE_G_REVERT_TASK_NOT_READY' }
    Write-Output 'PHASE_G_REVERT_READY'
    return
}

# Change only the temporary schedule selector; no business job is invoked.
$state.active = $false
$state | Add-Member -NotePropertyName reverted_at -NotePropertyValue ([DateTimeOffset]::Now.ToString('o')) -Force
$state | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $statePath -Encoding utf8

& (Join-Path $PSScriptRoot 'stop_scheduler.ps1') | Out-Null
& (Join-Path $PSScriptRoot 'start_scheduler.ps1') | Out-Null

$processes = @()
for ($attempt = 0; $attempt -lt 15; $attempt++) {
    Start-Sleep -Seconds 2
    $processes = @(Get-DsihSchedulerProcess)
    if ($processes.Count -eq 1) { break }
}
if ($processes.Count -ne 1) { throw 'PHASE_G_REVERT_PROCESS_COUNT_INVALID' }

$env:DSIH_FEISHU_BRIEF_TIME = [Environment]::GetEnvironmentVariable('DSIH_FEISHU_BRIEF_TIME', 'User')
$env:DSIH_FEISHU_BRIEF_TIMEZONE = [Environment]::GetEnvironmentVariable('DSIH_FEISHU_BRIEF_TIMEZONE', 'User')
$verification = @'
import json
from app.commands.run_scheduler import create_scheduler, FORMAL_PROFILE, load_schedule_profile
profile = load_schedule_profile()
actual = create_scheduler(profile=profile)
formal = create_scheduler(profile=FORMAL_PROFILE)
jobs = {job.id: job for job in actual.get_jobs()}
expected = {job.id: job for job in formal.get_jobs()}
matching = (profile == FORMAL_PROFILE and len(jobs) == 7 and set(jobs) == set(expected) and
            all(str(jobs[name].trigger) == str(expected[name].trigger) and
                jobs[name].max_instances == expected[name].max_instances and
                jobs[name].coalesce == expected[name].coalesce
                for name in jobs))
print(json.dumps({'formal_profile': matching, 'job_count': len(jobs)}))
'@
Push-Location -LiteralPath $script:DsihBackend
try {
    $raw = $verification | & $script:DsihPython -
    if ($LASTEXITCODE -ne 0) { throw 'PHASE_G_REVERT_VERIFICATION_FAILED' }
    $checked = $raw | ConvertFrom-Json
} finally { Pop-Location }
if (-not $checked.formal_profile) { throw 'PHASE_G_REVERT_VERIFICATION_FAILED' }

$result = [ordered]@{
    reverted_at = [DateTimeOffset]::Now.ToString('o')
    status = 'RESTORED_FORMAL'
    scheduler_pid = $processes[0].ProcessId
    job_count = $checked.job_count
    manual_business_jobs_triggered = $false
}
$result | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $resultPath -Encoding utf8
Disable-ScheduledTask -TaskName $revertTaskName | Out-Null
Write-Output 'PHASE_G_FORMAL_SCHEDULE_RESTORED'
