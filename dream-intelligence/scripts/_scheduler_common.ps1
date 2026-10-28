$script:DsihTaskName = 'Dream Intelligence Scheduler'
$script:DsihProjectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$script:DsihBackend = Join-Path $script:DsihProjectRoot 'backend'
$script:DsihPython = Join-Path $script:DsihBackend '.venv\Scripts\python.exe'
$script:DsihLog = Join-Path $script:DsihProjectRoot 'logs\scheduler.log'

function Get-DsihSchedulerProcess {
    $processes = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'"
    foreach ($process in $processes) {
        if (-not $process.ExecutablePath -or -not $process.CommandLine) { continue }
        if ($process.ExecutablePath -ine $script:DsihPython) { continue }
        if ($process.CommandLine -notmatch '(?i)(?:^|\s)-m\s+app\.commands\.run_scheduler(?:\s|$)') { continue }
        if ($process.CommandLine -match '(?i)(?:^|\s)--once(?:-\w+)?(?:\s|$)') { continue }
        $process
    }
}
