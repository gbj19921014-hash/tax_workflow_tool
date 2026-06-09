#define MyAppName "A1-A3税务工作流"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Local"
#define MyAppExeName "A1-A3税务工作流.exe"
#define RootDir AddBackslash(SourcePath) + "..\.."

[Setup]
AppId={{D6E24D91-41CE-4E96-B4C3-2F2C32B410C8}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir={#RootDir}\dist\installer
OutputBaseFilename=A1-A3税务工作流安装包
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面图标"; GroupDescription: "附加图标："; Flags: checkedonce

[Files]
Source: "{#RootDir}\dist\A1-A3税务工作流\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent
