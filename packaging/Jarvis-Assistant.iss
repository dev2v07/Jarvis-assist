#define MyAppName "Jarvis Assistant"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Jarvis Assist contributors"
#define MyAppExeName "JarvisAssistant.exe"

[Setup]
AppId={{6D9C19F4-4EA9-4A99-9D4F-5D2D5A9C2A11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Jarvis Assistant
DefaultGroupName={#MyAppName}
OutputBaseFilename=Jarvis-Assistant-Setup
OutputDir=..\dist
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
WizardStyle=modern
Uninstallable=yes

[Files]
Source: "..\dist\JarvisAssistant\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autodesktop}\Jarvis Assistant"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Jarvis Assistant"; Filename: "{app}\{#MyAppExeName}"

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C reg delete ""HKCU\Software\Microsoft\Windows\CurrentVersion\Run"" /v ""Jarvis Assist"" /f"; Flags: runhidden
