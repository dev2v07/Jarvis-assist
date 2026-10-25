@echo off
set ROOT_DIR=%~dp0
cd /d "%ROOT_DIR%backend"
if not exist venv (
  python -m venv venv
)
call venv\Scripts\activate
pip install -r requirements.txt
start /B python main.py
cd /d "%ROOT_DIR%frontend"
npm install
npm start
