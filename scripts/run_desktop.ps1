$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$env:Path = 'C:\Program Files\nodejs;' + $env:Path
Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue

Push-Location "$root\desktop"
try {
  & 'C:\Program Files\nodejs\npm.cmd' install
  & 'C:\Program Files\nodejs\npm.cmd' run start
}
finally {
  Pop-Location
}
