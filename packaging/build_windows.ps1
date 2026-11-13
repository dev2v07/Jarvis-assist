$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root "dist"
$build = Join-Path $root "build"

python -m PyInstaller --version | Out-Null

New-Item -ItemType Directory -Force $dist | Out-Null
python -m PyInstaller --noconfirm --clean --onedir --name JarvisBackend `
    --paths "$root\backend" `
    "$root\backend\main.py"

python -m PyInstaller --noconfirm --clean --onedir --windowed `
    --name JarvisAssistant `
    --paths "$root\frontend" --paths "$root\backend" `
    --add-data "$root\frontend\assets;frontend\assets" `
    --add-data "$root\frontend\assets\fonts;frontend\assets\fonts" `
    --add-data "$root\backend\voice_engine\sound;backend\voice_engine\sound" `
    --add-data "$root\backend\voice_engine\commands.yaml;backend\voice_engine\commands.yaml" `
    --hidden-import jarvis_ui `
    "$root\frontend\launch_jarvis.py"

$guiDir = Join-Path $dist "JarvisAssistant"
$backendDir = Join-Path $dist "JarvisBackend"
Copy-Item (Join-Path $backendDir "*") $guiDir -Recurse -Force

$iscc = Get-Command iscc -ErrorAction SilentlyContinue
if (-not $iscc) {
    Write-Warning "Inno Setup compiler (iscc.exe) was not found. The frozen folder was built; install Inno Setup and rerun this script to create Jarvis-Assistant-Setup.exe."
    exit 0
}
& $iscc.Source "$PSScriptRoot\Jarvis-Assistant.iss"
