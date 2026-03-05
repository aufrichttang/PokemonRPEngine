$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "[1/2] Building desktop package..." -ForegroundColor Cyan
powershell -ExecutionPolicy Bypass -File "$root\scripts\build_desktop_exe.ps1"

$distDir = Join-Path $root "dist\PokemonRP-Desktop-win32-x64"
if (-not (Test-Path $distDir)) {
  throw "dist folder not found: $distDir"
}

Write-Host "[2/2] Writing user runtime .env template..." -ForegroundColor Cyan
$envPath = Join-Path $distDir ".env"
@"
# Pokemon RP Desktop user edition
# Launch and play directly without entering account/password.

DESKTOP_AUTO_LOGIN=true
DESKTOP_AUTO_USERNAME=admin
DESKTOP_AUTO_PASSWORD=admin

BOOTSTRAP_DEFAULT_ADMIN=true
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=admin

# Fill if you want real XFYun model calls:
# LLM_PROVIDER=xfyun_http
# XF_MODEL_ID=xopglm5
# XF_BASE_URL_HTTP=https://maas-api.cn-huabei-1.xf-yun.com/v2
# XF_AUTH_MODE=bearer
# XF_APPID=
# XF_API_KEY=
# XF_API_SECRET=
"@ | Set-Content -Path $envPath -Encoding UTF8

Write-Host ""
Write-Host "User edition ready:" -ForegroundColor Green
Write-Host "  $distDir\PokemonRP-Desktop.exe" -ForegroundColor Green
Write-Host "The generated .env already enables no-login direct play." -ForegroundColor Green
