$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host '==> Preparing runtime config'
$ConfigHome = if ($env:HEL_CONFIG_HOME) { $env:HEL_CONFIG_HOME } else { Join-Path $env:APPDATA 'ProjectHel' }
New-Item -ItemType Directory -Force -Path $ConfigHome | Out-Null
if (-not (Test-Path (Join-Path $ConfigHome '.env'))) {
  Copy-Item (Join-Path $Root '.env.example') (Join-Path $ConfigHome '.env')
}

Write-Host '==> Building backend executable'
Set-Location "$Root\backend"
if (-not (Test-Path venv)) {
  python -m venv venv
}
& "$Root\backend\venv\Scripts\python.exe" -m pip install --upgrade pip
& "$Root\backend\venv\Scripts\python.exe" -m pip install -r requirements.txt
& "$Root\backend\venv\Scripts\pyinstaller.exe" --noconfirm --clean --onefile --name hel_backend main.py

if (Test-Path "$Root\backend_dist") {
  Remove-Item "$Root\backend_dist" -Recurse -Force
}
New-Item -ItemType Directory -Path "$Root\backend_dist" | Out-Null
Copy-Item "$Root\backend\dist\hel_backend.exe" "$Root\backend_dist\hel_backend.exe"
Copy-Item "$Root\.env.example" "$Root\backend_dist\.env.example"

Write-Host '==> Building Windows installer'
Set-Location "$Root\frontend"
npm install
npx electron-builder --win nsis

Write-Host 'Installer ready in frontend\dist'
