@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
set ROOT=%~dp0
set BACKEND=%ROOT%backend
set FRONTEND=%ROOT%frontend
set VENV=%BACKEND%\.venv
set PYTHON_CMD=

echo [Hel] Проверка Python...
where py >nul 2>nul && set PYTHON_CMD=py -3
if not defined PYTHON_CMD (
  where python >nul 2>nul && set PYTHON_CMD=python
)
if not defined PYTHON_CMD (
  echo [Hel] Python не найден. Установите Python 3.11+ и повторите запуск.
  pause
  exit /b 1
)

echo [Hel] Проверка Node.js...
where npm >nul 2>nul
if errorlevel 1 (
  echo [Hel] Node.js / npm не найден. Установите Node.js 20+ и повторите запуск.
  pause
  exit /b 1
)

if not exist "%APPDATA%\ProjectHel" mkdir "%APPDATA%\ProjectHel"
if not exist "%APPDATA%\ProjectHel\.env" copy "%ROOT%\.env.example" "%APPDATA%\ProjectHel\.env" >nul

if not exist "%VENV%\Scripts\python.exe" (
  echo [Hel] Создаю виртуальное окружение...
  call %PYTHON_CMD% -m venv "%VENV%"
  if errorlevel 1 goto :fail
)

echo [Hel] Устанавливаю Python зависимости...
call "%VENV%\Scripts\python.exe" -m pip install --upgrade pip
call "%VENV%\Scripts\python.exe" -m pip install -r "%BACKEND%\requirements.txt"
if errorlevel 1 goto :fail

echo [Hel] Устанавливаю frontend зависимости...
pushd "%FRONTEND%"
call npm install
if errorlevel 1 (
  popd
  goto :fail
)
popd

echo [Hel] Запускаю приложение...
start "Hel Backend" cmd /c "cd /d "%BACKEND%" && "%VENV%\Scripts\python.exe" main.py"
timeout /t 3 >nul
pushd "%FRONTEND%"
call npm start
popd
exit /b 0

:fail
echo [Hel] Не удалось подготовить окружение.
pause
exit /b 1
