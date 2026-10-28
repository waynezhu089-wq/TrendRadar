$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_scheduler_common.ps1')

$watchdogTaskName = 'Dream Intelligence Scheduler Watchdog'
$mainTask = Get-ScheduledTask -TaskName $script:DsihTaskName -ErrorAction Stop
$watchdogScript = Join-Path $PSScriptRoot 'scheduler_watchdog.ps1'
if (-not (Test-Path -LiteralPath $watchdogScript -PathType Leaf)) {
    throw 'WATCHDOG_SCRIPT_MISSING'
}

# Clone the already validated interactive-user Task XML, changing only its action,
# execution limit, and logon trigger repetition. No credentials are embedded.
[xml]$xml = Export-ScheduledTask -TaskName $script:DsihTaskName
$namespace = $xml.Task.NamespaceURI
$logonTrigger = $xml.Task.Triggers.LogonTrigger
$repetition = $xml.CreateElement('Repetition', $namespace)
$interval = $xml.CreateElement('Interval', $namespace)
$interval.InnerText = 'PT10M'
[void]$repetition.AppendChild($interval)
[void]$logonTrigger.PrependChild($repetition)
$xml.Task.Actions.Exec.Arguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$watchdogScript`""
$xml.Task.Settings.ExecutionTimeLimit = 'PT2M'
Register-ScheduledTask -TaskName $watchdogTaskName -Xml $xml.OuterXml -Force | Out-Null
Write-Output 'WATCHDOG_TASK_INSTALLED'
