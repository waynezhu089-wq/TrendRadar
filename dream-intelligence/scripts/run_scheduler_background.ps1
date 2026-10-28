$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_scheduler_common.ps1')

if (-not (Test-Path -LiteralPath $script:DsihPython -PathType Leaf)) {
    throw 'Project virtual environment Python is missing.'
}
New-Item -ItemType Directory -Path (Split-Path $script:DsihLog) -Force | Out-Null
$script:DsihRuntimeLog = Join-Path (Split-Path $script:DsihLog) 'scheduler-runtime.log'
$script:DsihLauncherStartedAt = [DateTimeOffset]::Now.ToString('o')
$script:DsihChildProcessId = $null

function Write-DsihLog([string]$line) {
    if ((Test-Path -LiteralPath $script:DsihLog) -and
        (Get-Item -LiteralPath $script:DsihLog).Length -gt 5MB) {
        try { Move-Item -LiteralPath $script:DsihLog -Destination "$($script:DsihLog).1" -Force -ErrorAction Stop }
        catch { } # An already running scheduler may still have the current log open.
    }
    Add-Content -LiteralPath $script:DsihLog -Value $line -Encoding utf8
}

function Write-DsihRuntimeLog([string]$eventName, $exitCode = $null) {
    $record = [ordered]@{
        event = $eventName
        launcher_started_at = $script:DsihLauncherStartedAt
        child_pid = $script:DsihChildProcessId
        child_exit_at = if ($null -ne $exitCode) { [DateTimeOffset]::Now.ToString('o') } else { $null }
        child_exit_code = $exitCode
    }
    Add-Content -LiteralPath $script:DsihRuntimeLog -Value ($record | ConvertTo-Json -Compress) -Encoding utf8
}

Write-DsihLog "$(Get-Date -Format o) LAUNCHER_STARTED"
Write-DsihRuntimeLog 'LAUNCHER_STARTED'
foreach ($name in @(
    'DSIH_LLM_BASE_URL', 'DSIH_LLM_API_KEY', 'DSIH_LLM_MODEL', 'DSIH_YOUTUBE_API_KEY',
    'DSIH_FEISHU_WEBHOOK_URL', 'DSIH_FEISHU_BRIEF_TIME', 'DSIH_FEISHU_BRIEF_TIMEZONE'
)) {
    $value = [Environment]::GetEnvironmentVariable($name, 'User')
    if ($value) { [Environment]::SetEnvironmentVariable($name, $value, 'Process') }
    else { $value = [Environment]::GetEnvironmentVariable($name, 'Process') }
    $state = if ($value) { 'SET' } else { 'MISSING' }
    Write-DsihLog "$name=$state"
}

Set-Location -LiteralPath $script:DsihBackend
$env:PYTHONUNBUFFERED = '1'
try {
    & $script:DsihPython -u -m app.commands.run_scheduler 2>&1 | ForEach-Object {
        if ($null -eq $script:DsihChildProcessId) {
            try {
                $children = @(Get-DsihSchedulerProcess | Where-Object { $_.ParentProcessId -eq $PID })
                if ($children.Count -eq 1) {
                    $script:DsihChildProcessId = $children[0].ProcessId
                    Write-DsihRuntimeLog 'CHILD_STARTED'
                }
            } catch { } # Runtime diagnostics must not stop the Scheduler.
        }
        Write-DsihLog ([string]$_)
    }
    $code = $LASTEXITCODE
    if ($null -eq $code) { $code = 1 }
    Write-DsihLog "$(Get-Date -Format o) LAUNCHER_EXIT code=$code"
    Write-DsihRuntimeLog 'CHILD_EXITED' $code
    exit $code
}
catch {
    Write-DsihLog "$(Get-Date -Format o) LAUNCHER_FAILED"
    Write-DsihRuntimeLog 'LAUNCHER_FAILED' 1
    exit 1
}
