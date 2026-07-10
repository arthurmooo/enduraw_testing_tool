#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#ifndef SourceRoot
  #define SourceRoot "..\.."
#endif

#define MyAppName "Enduraw Testing Tool"
#define MyAppPublisher "Enduraw"
#define MyAppExeName "EndurawTestingTool.exe"

[Setup]
AppId={{B174386D-3FE2-4B1B-B6E6-FEE9241BC47A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\EndurawTestingTool
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#SourceRoot}\artifacts
OutputBaseFilename=EndurawTestingTool-Setup
SetupIconFile={#SourceRoot}\icon.ico
UninstallDisplayIcon={app}\app\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName}
VersionInfoProductName={#MyAppName}

[InstallDelete]
Type: filesandordirs; Name: "{app}\app"

[Files]
Source: "{#SourceRoot}\dist\EndurawTestingTool\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\app\{#MyAppExeName}"; WorkingDir: "{app}\app"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\app\{#MyAppExeName}"; WorkingDir: "{app}\app"

[Run]
Filename: "{app}\app\{#MyAppExeName}"; Description: "Lancer {#MyAppName}"; Flags: nowait postinstall skipifsilent
