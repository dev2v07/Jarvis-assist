# Jarvis Python LSP

- Serena 2.1.0 uses the project language-server id python for the official Pyright integration.
- Project .serena/project.yml explicitly sets language_backend: LSP, language_servers: [python], pyright_version: 1.1.414, workspace root ., and ignores generated directories plus backend/jarvis_env and backend/device_env.
- Global %USERPROFILE%/.serena/serena_config.yml trusts C:/projects/Jarvis so project LS-specific settings are applied.
- Root pyrightconfig.json includes backend, frontend and core, excludes generated/virtual-environment directories, sets Python 3.11 and venvPath backend with venv jarvis_env.
- Serena manages the language-server package through uvx; the project runtime interpreter is backend/jarvis_env/Scripts/python.exe (Python 3.11.9). Serena's own uvx launcher may use its host Python to execute Pyright; that is separate from the analyzed project environment.
- Fresh Serena health-check log .serena/logs/health-checks/health_check_20261116-221643.log confirmed Pyright 1.1.414 startup, documentSymbolProvider, definitionProvider and referencesProvider, loading pyrightconfig.json, 225 source files, and successful symbols/find_symbol/find_references checks.
- Targeted fresh SerenaAgent LSP checks also passed for backend/main.py document symbols, VoiceRuntime definition/declaration/references, ChatStore definition/declaration/references, frontend/jarvis_ui.py document symbols, and ChatRequestWorker lookup.
- Recovery: restart the Serena MCP/server process, activate C:/projects/Jarvis again, and wait for Pyright initial analysis. If needed, run serena project health-check C:/projects/Jarvis with UTF-8 console output; inspect .serena/logs/health-checks/.
