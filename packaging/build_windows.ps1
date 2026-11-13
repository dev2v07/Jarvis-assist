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
    --contents-directory . `
    --name JarvisAssistant `
    --icon "$root\frontend\assets\jarvis.ico" `
    --paths "$root\frontend" --paths "$root\backend" `
    --add-data "$root\frontend\assets;frontend\assets" `
    --add-data "$root\frontend\assets\fonts;frontend\assets\fonts" `
    --add-data "$root\backend\voice_engine\sound;backend\voice_engine\sound" `
    --add-data "$root\backend\voice_engine\commands.yaml;backend\voice_engine\commands.yaml" `
    --hidden-import jarvis_ui `
    --runtime-hook "$root\packaging\pyi_qt_runtime_hook.py" `
    "$root\frontend\launch_jarvis.py"

$guiDir = Join-Path $dist "JarvisAssistant"
$backendDir = Join-Path $dist "JarvisBackend"
$frozenBackendDir = Join-Path $guiDir "backend_runtime"
New-Item -ItemType Directory -Force $frozenBackendDir | Out-Null
Copy-Item (Join-Path $backendDir "*") $frozenBackendDir -Recurse -Force

# PyInstaller can collect ICU DLLs from the bundled Poppler runtime. Those
# copies are incompatible with the ICU symbols expected by Qt6Core and win the
# Windows DLL search before Qt's own runtime. The desktop client does not load
# Poppler directly; keep these libraries out of the GUI bundle. The backend is
# packaged separately and is left untouched.
foreach ($conflictingIcu in @("icuuc.dll", "icudt78.dll")) {
    $conflictingPath = Join-Path $guiDir $conflictingIcu
    if (Test-Path -LiteralPath $conflictingPath) {
        Remove-Item -LiteralPath $conflictingPath -Force
    }
}

$iscc = Get-Command iscc -ErrorAction SilentlyContinue
if (-not $iscc) {
    Write-Warning "Inno Setup compiler (iscc.exe) was not found. The frozen folder was built; install Inno Setup and rerun this script to create Jarvis-Assistant-Setup.exe."
    exit 0
}
& $iscc.Source "$PSScriptRoot\Jarvis-Assistant.iss"
