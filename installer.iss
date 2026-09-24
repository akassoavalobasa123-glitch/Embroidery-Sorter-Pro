#define MyAppName "Embroidery Sorter Pro"
#define MyAppVersion "2.3.0"
#define MyAppPublisher "Chomon Tools"
#define MyAppExeName "Embroidery Sorter Pro.exe"
[Setup]
AppId={{A2A3D4D5-8B34-4A20-9F6E-1B2C3D4E5F60}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Embroidery Sorter Pro
DefaultGroupName={#MyAppName}
OutputDir=installer
OutputBaseFilename=Embroidery_Sorter_Pro_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
[Files]
Source: "dist\Embroidery Sorter Pro.exe"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{group}\Embroidery Sorter Pro"; Filename: "{app}\Embroidery Sorter Pro.exe"
Name: "{autodesktop}\Embroidery Sorter Pro"; Filename: "{app}\Embroidery Sorter Pro.exe"
[Run]
Filename: "{app}\Embroidery Sorter Pro.exe"; Description: "Launch Embroidery Sorter Pro"; Flags: nowait postinstall skipifsilent
