$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$env:Path = 'C:\Program Files\nodejs;' + $env:Path
Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue

Push-Location "$root\desktop"
try {
  & 'C:\Program Files\nodejs\npm.cmd' install
  & 'C:\Program Files\nodejs\npm.cmd' install --save-dev electron-packager
  & 'C:\Program Files\nodejs\npx.cmd' electron-packager . PokemonRP-Desktop --platform=win32 --arch=x64 --out=..\dist --overwrite
}
finally {
  Pop-Location
}

Write-Host ""
Write-Host "Build done: $root\dist\PokemonRP-Desktop-win32-x64\PokemonRP-Desktop.exe" -ForegroundColor Green
