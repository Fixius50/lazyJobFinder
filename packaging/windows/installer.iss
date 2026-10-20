; =============================================================================
; Inno Setup Script para lazyJobFinder (Windows x64)
; =============================================================================

#define MyAppName "lazyJobFinder"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Roberto (Fixius50)"
#define MyAppURL "https://github.com/Fixius50/lazyJobFinder"
#define MyAppExeName "launch.bat"

[Setup]
AppId={{E6F7A8B9-C0D1-4E2F-A3B4-5C6D7E8F9A0B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=..\..\dist
OutputBaseFilename=lazyJobFinder-{#MyAppVersion}-windows-x64
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
DisableProgramGroupPage=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Archivos principales de la aplicación
Source: "..\staging\docker-compose.yml"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\staging\.env.example"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\staging\launch.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\staging\stop.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\staging\install.bat"; DestDir: "{app}"; Flags: ignoreversion

; Plantillas de configuración (solo si no existen, para no sobreescribir datos del usuario)
Source: "..\staging\config\*"; DestDir: "{app}\config"; Flags: onlyifdoesntexist recursesubdirs createallsubdirs

; Directorios de datos del usuario
Source: "..\staging\data\*"; DestDir: "{app}\data"; Flags: onlyifdoesntexist recursesubdirs createallsubdirs

; Imágenes de contenedores empaquetadas (obligatorias para paquete completo x64)
Source: "..\staging\images.tar"; DestDir: "{app}"; Flags: ignoreversion

; Datos del modelo de IA empaquetado (obligatorio para paquete completo)
Source: "..\staging\ollama_model.tar.gz"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{app}\data"; Permissions: users-full
Name: "{app}\data\uploaded_cvs"; Permissions: users-full
Name: "{app}\data\documents"; Permissions: users-full
Name: "{app}\config"; Permissions: users-full

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Comment: "Iniciar lazyJobFinder"
Name: "{group}\Detener {#MyAppName}"; Filename: "{app}\stop.bat"; WorkingDir: "{app}"; Comment: "Detener servicios de lazyJobFinder"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
; 1. Cargar imágenes Docker en el motor local al terminar la instalación
Filename: "cmd.exe"; Parameters: "/c cd /d ""{app}"" && docker load -i ""{app}\images.tar"""; StatusMsg: "Cargando imágenes de Docker y Ollama en el sistema local..."; Flags: runhidden waituntilterminated

; 2. Restaurar modelo de IA en el volumen de Ollama (usando el contenedor de ollama cargado, sin depender de imágenes externas)
Filename: "cmd.exe"; Parameters: "/c cd /d ""{app}"" && docker compose up --no-start ollama && docker compose run --rm --entrypoint /bin/sh -v ""{app}"":/backup ollama -c ""tar xzf /backup/ollama_model.tar.gz -C /root/.ollama"""; StatusMsg: "Restaurando modelo de IA empaquetado en el volumen de Ollama..."; Flags: runhidden waituntilterminated

; 3. Opción para arrancar la aplicación inmediatamente tras la instalación
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: shellexec postinstall nowait skipifsilent



[UninstallRun]
; Detener contenedores Docker antes de desinstalar
Filename: "cmd.exe"; Parameters: "/c cd /d ""{app}"" && docker compose down"; Flags: runhidden waituntilterminated

[Code]
// Verificación previa de Docker Desktop instalado
function InitializeSetup(): Boolean;
var
  DockerResult: Integer;
begin
  Result := True;
  if not Exec('cmd.exe', '/c docker --version', '', SW_HIDE, ewWaitUntilTerminated, DockerResult) or (DockerResult <> 0) then
  begin
    if MsgBox('Docker Desktop no parece estar instalado o no se encuentra en el PATH del sistema.' + #13#10 + #13#10 +
              'lazyJobFinder requiere Docker Desktop para ejecutar la IA y la aplicación localmente.' + #13#10 + #13#10 +
              '¿Deseas continuar con la instalación de todos modos?' + #13#10 +
              '(Deberás instalar Docker Desktop antes de iniciar la aplicación)',
              mbConfirmation, MB_YESNO) = IDNO then
    begin
      Result := False;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  EnvPath: string;
begin
  if CurStep = ssPostInstall then
  begin
    // Si no existe .env, copiar desde .env.example
    EnvPath := ExpandConstant('{app}\.env');
    if not FileExists(EnvPath) then
    begin
      FileCopy(ExpandConstant('{app}\.env.example'), EnvPath, False);
    end;
  end;
end;
