# Richtet eine Windows-Aufgabe ein, die den Protokoll-Generator bei der Anmeldung
# startet und im Hintergrund laufen lässt (kein Fenster).
#
#   .\install_task.ps1                                  # Python-Variante (dieser Ordner, .venv)
#   .\install_task.ps1 -Exe C:\Protokoll\ProtokollGenerator.exe   # Exe-Variante (Teststand-PC)
#   .\install_task.ps1 -Remove                          # Aufgabe entfernen
param(
    [string]$Exe,
    [switch]$Remove
)
$ErrorActionPreference = "Stop"
$TaskName = "ZOPF Protokoll-Generator"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Aufgabe '$TaskName' entfernt."
    return
}

if ($Exe) {
    $Exe = (Resolve-Path $Exe).Path
    $action = New-ScheduledTaskAction -Execute $Exe -Argument "run" -WorkingDirectory (Split-Path $Exe)
} else {
    $pyw = Join-Path $PSScriptRoot ".venv\Scripts\pythonw.exe"
    if (-not (Test-Path $pyw)) { throw "$pyw fehlt - zuerst venv anlegen (siehe README)." }
    $action = New-ScheduledTaskAction -Execute $pyw -Argument "-m protokoll.main run" -WorkingDirectory $PSScriptRoot
}

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
# Bei Absturz automatisch neu starten, nie wegen Laufzeit beenden.
$settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Host "Aufgabe '$TaskName' eingerichtet und gestartet."
