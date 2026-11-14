#define MyAppName "Jarvis Assistant"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Jarvis Assist contributors"
#define MyAppPublisherURL "https://tandemarketing.ru"
#define MyAppExeName "JarvisAssistant.exe"

[Setup]
AppId={{6D9C19F4-4EA9-4A99-9D4F-5D2D5A9C2A11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppPublisherURL}
AppSupportURL={#MyAppPublisherURL}
AppUpdatesURL={#MyAppPublisherURL}
SetupIconFile=..\frontend\assets\jarvis.ico
DefaultDirName={autopf}\Jarvis Assistant
DefaultGroupName={#MyAppName}
OutputBaseFilename=Jarvis-Assistant-Setup
OutputDir=..\dist
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
WizardStyle=modern
WizardImageFile=jarvis-preview.bmp
WizardSmallImageFile=jarvis-preview-small.bmp
Uninstallable=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Files]
Source: "..\dist\JarvisAssistant\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "..\frontend\assets\jarvis.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autodesktop}\Jarvis Assistant"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\jarvis.ico"; IconIndex: 0
Name: "{group}\Jarvis Assistant"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\jarvis.ico"; IconIndex: 0

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C reg delete ""HKCU\Software\Microsoft\Windows\CurrentVersion\Run"" /v ""Jarvis Assist"" /f"; Flags: runhidden

[Code]
var
  TandemLink: TNewStaticText;

procedure TandemLinkClick(Sender: TObject);
var
  ErrorCode: Integer;
begin
  ShellExec('open', '{#MyAppPublisherURL}', '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
end;

procedure InitializeWizard;
begin
  TandemLink := TNewStaticText.Create(WizardForm);
  TandemLink.Parent := WizardForm;
  TandemLink.Caption := '© Разработано Tandem Marketing 2026';
  TandemLink.Font.Color := clNavy;
  TandemLink.Font.Style := [fsUnderline];
  TandemLink.Cursor := crHand;
  TandemLink.Left := 20;
  TandemLink.Top := WizardForm.ClientHeight - 34;
  TandemLink.Width := 360;
  TandemLink.Height := 24;
  TandemLink.OnClick := @TandemLinkClick;
end;
