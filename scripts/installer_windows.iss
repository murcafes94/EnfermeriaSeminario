#define MyAppName "Enfermería San Giuseppe Moscati"
#define MyAppVersion "3.6.2"
#define MyAppExeName "EnfermeriaSeminario.exe"

[Setup]
AppId={{BB4425A2-082E-4F01-A125-5F8366EFC152}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Seminario Mayor de Guayaquil
DefaultDirName={localappdata}\Programs\EnfermeriaSeminario
DefaultGroupName={#MyAppName}
OutputDir=..\dist\installer
OutputBaseFilename=EnfermeriaSanGiuseppeMoscati-Setup-3.6.2
SetupIconFile=..\assets\app_icon.ico
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
WizardStyle=modern

[Files]
Source: "..\dist\EnfermeriaSeminario\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Panel rápido de Enfermería"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--panel"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent
