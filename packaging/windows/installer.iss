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
; Opción para arrancar la aplicación inmediatamente tras la instalación
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: shellexec postinstall nowait skipifsilent

[UninstallRun]
; Detener contenedores Docker antes de desinstalar
Filename: "cmd.exe"; Parameters: "/c cd /d ""{app}"" && docker compose down"; Flags: runhidden waituntilterminated

[Code]
// Verificación obligatoria de Docker Desktop instalado para la distribución completa
function InitializeSetup(): Boolean;
var
  DockerResult: Integer;
begin
  Result := True;
  if not Exec('cmd.exe', '/c docker --version', '', SW_HIDE, ewWaitUntilTerminated, DockerResult) or (DockerResult <> 0) then
  begin
    MsgBox('ERROR CRÍTICO: Docker Desktop no está instalado o no se encuentra en el PATH del sistema.' + #13#10 + #13#10 +
           'lazyJobFinder requiere Docker Desktop en ejecución para operar localmente y cargar las imágenes.' + #13#10 +
           'Por favor, instala Docker Desktop antes de ejecutar este instalador.',
           mbError, MB_OK);
    Result := False;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  AppDir, EnvPath, CmdLoad, CmdRestore: string;
  ResultCode: Integer;
  RandSuffix: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    AppDir := ExpandConstant('{app}');
    EnvPath := AppDir + '\.env';

    // 1. Inicializar .env con identificador único de proyecto COMPOSE_PROJECT_NAME
    if not FileExists(EnvPath) then
    begin
      FileCopy(AppDir + '\.env.example', EnvPath, False);
      RandSuffix := Random(899999) + 100000;
      SaveStringToFile(EnvPath, #13#10 + '# Identificador único de proyecto Compose para aislamiento de instalación' + #13#10 +
                       'COMPOSE_PROJECT_NAME=lazyjob_' + IntToStr(RandSuffix) + #13#10, True);
    end;

    // 2. Ejecutar docker load -i images.tar con comprobación estricta de código de salida
    if FileExists(AppDir + '\images.tar') then
    begin
      CmdLoad := '/c cd /d "' + AppDir + '" && docker load -i "' + AppDir + '\images.tar"';
      if not Exec('cmd.exe', CmdLoad, AppDir, SW_HIDE, ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
      begin
        MsgBox('ERROR CRÍTICO: Falló la importación de las imágenes de Docker (images.tar). ' +
               'Código de salida: ' + IntToStr(ResultCode) + '.' + #13#10 +
               'Asegúrate de que Docker Desktop esté iniciado y funcionando.', mbError, MB_OK);
        RaiseException('Error al importar images.tar en Docker.');
      end;
    end;

    // 3. Restaurar modelo en el volumen persistente con comprobación estricta de código de salida
    if FileExists(AppDir + '\ollama_model.tar.gz') then
    begin
      CmdRestore := '/c cd /d "' + AppDir + '" && docker compose up --no-start ollama && ' +
                    'docker compose run --rm --entrypoint /bin/sh -v "' + AppDir + '":/backup ollama -c "tar xzf /backup/ollama_model.tar.gz -C /root/.ollama"';
      if not Exec('cmd.exe', CmdRestore, AppDir, SW_HIDE, ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
      begin
        MsgBox('ERROR CRÍTICO: Falló la restauración del modelo de IA en el volumen de Ollama. ' +
               'Código de salida: ' + IntToStr(ResultCode) + '.', mbError, MB_OK);
        RaiseException('Error al restaurar ollama_model.tar.gz.');
      end;
    end;
  end;
end;

