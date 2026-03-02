$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

python -m pip install pyinstaller
python -m PyInstaller --onefile --name PokemonRP-Start scripts/one_click_launch.py

Write-Host ""
Write-Host "Build done: $root\dist\PokemonRP-Start.exe" -ForegroundColor Green
