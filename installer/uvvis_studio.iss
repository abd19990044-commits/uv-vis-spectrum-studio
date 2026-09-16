#define MyAppName "UV-Vis Spectrum Studio"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Abdulsalam S. Hasan"
#define MyAppExeName "UV-Vis Spectrum Studio.exe"

[Setup]
AppId={{7F4E45F1-8D8C-4B3D-A4E0-5D63C5B9D1B8}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\UV-Vis Spectrum Studio
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=..\installer_output
OutputBaseFilename=UVVis_Spectrum_Studio_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\build_assets\app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\UV-Vis Spectrum Studio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
