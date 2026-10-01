# Baut eine eigenständige ProtokollGenerator.exe (kein Python auf dem Teststand-PC nötig).
# Ergebnis: dist\ProtokollGenerator.exe
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .venv)) { py -3 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install --quiet -r requirements.txt pyinstaller

.\.venv\Scripts\pyinstaller.exe --noconfirm --onefile --noconsole `
    --name ProtokollGenerator `
    --add-data "protokoll\assets;protokoll\assets" `
    run_protokoll.py

Write-Host "Fertig: $PSScriptRoot\dist\ProtokollGenerator.exe"
