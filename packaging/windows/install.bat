@echo off
setlocal enabledelayedexpansion
title lazyJobFinder - Asistente de Instalacion Windows

cd /d "%~dp0"

echo =====================================================================
echo           lazyJobFinder - Instalador Local para Windows
echo =====================================================================
echo.

:: 1. Comprobacion de Docker Desktop
docker --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] No se ha detectado Docker en el sistema.
    echo         Por favor, instala Docker Desktop desde: https://www.docker.com/products/docker-desktop/
    echo         y vuelve a ejecutar este instalador.
    echo.
    pause
    exit /b 1
)

:: 2. Crear carpetas de usuario necesarias
if not exist "data" mkdir "data"
if not exist "data\uploaded_cvs" mkdir "data\uploaded_cvs"
if not exist "data\documents" mkdir "data\documents"
if not exist "config" mkdir "config"

:: 3. Copiar plantillas si no existen y asignar identificador de proyecto único (sin sobreescribir si ya existe)
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        :: Generar sufijo pseudoaleatorio con fecha y random para aislar redes y volumenes de Docker Compose
        set "RAND_SUFFIX=%RANDOM%%TIME:~6,2%"
        echo.>>".env"
        echo # Identificador unico de instalacion para aislamiento Docker Compose>>".env"
        echo COMPOSE_PROJECT_NAME=lazyjob_!RAND_SUFFIX!>>".env"
        echo [OK] Archivo de entorno .env creado con proyecto Compose unico (lazyjob_!RAND_SUFFIX!).
    )
) else (
    echo [i] Archivo .env existente detectado. Conservando credenciales e identificador de proyecto previos.
)

if not exist "config\settings.yaml" (
    if exist "config-templates\settings.yaml" (
        copy "config-templates\settings.yaml" "config\settings.yaml" >nul
        echo [OK] Plantilla config\settings.yaml copiada.
    )
)

if not exist "config\profile.yaml" (
    if exist "config-templates\profile.yaml" (
        copy "config-templates\profile.yaml" "config\profile.yaml" >nul
        echo [OK] Plantilla config\profile.yaml copiada.
    )
)

if not exist "config\shared_constants.json" (
    if exist "config-templates\shared_constants.json" (
        copy "config-templates\shared_constants.json" "config\shared_constants.json" >nul
        echo [OK] Plantilla config\shared_constants.json copiada.
    )
)

:: 4. Importar imagenes de Docker si images.tar esta presente
if exist "images.tar" (
    echo.
    echo [i] Importando imagenes de contenedores locales (lazyjobfinder y ollama)...
    docker load -i "images.tar"
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Fallo al cargar las imagenes desde images.tar.
        pause
        exit /b 1
    )
    echo [OK] Imagenes de contenedores importadas correctamente.
)

:: 4.1 Restaurar modelo de Ollama en el volumen persistente si ollama_model.tar.gz esta presente
if exist "ollama_model.tar.gz" (
    echo.
    echo [i] Restaurando datos del modelo IA empaquetado en el volumen persistente...
    docker compose up --no-start ollama >nul 2>&1
    docker compose run --rm --entrypoint /bin/sh -v "%~dp0":/backup ollama -c "tar xzf /backup/ollama_model.tar.gz -C /root/.ollama"
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] No se pudo restaurar el modelo de IA en el volumen de Ollama.
        pause
        exit /b 1
    )
    echo [OK] Modelo IA precargado en el volumen local de Ollama.
)

:: 5. Crear acceso directo en el Escritorio con PowerShell
echo.
echo [i] Creando acceso directo en el Escritorio...
set "TARGET_BAT=%~dp0launch.bat"
set "SHORTCUT_PATH=%USERPROFILE%\Desktop\lazyJobFinder.lnk"
powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%SHORTCUT_PATH%'); $Shortcut.TargetPath = '%TARGET_BAT%'; $Shortcut.WorkingDirectory = '%~dp0'; $Shortcut.Description = 'Iniciar lazyJobFinder'; $Shortcut.Save()" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [OK] Acceso directo 'lazyJobFinder' creado en tu Escritorio.
)

echo.
echo =====================================================================
echo                   Instalacion Completada con Exito
echo =====================================================================
echo.
echo Puedes iniciar lazyJobFinder en cualquier momento haciendo doble clic
echo en el acceso directo de tu Escritorio o ejecutando 'launch.bat'.
echo.
set /p START_NOW="¿Deseas iniciar lazyJobFinder ahora mismo? (S/N): "
if /i "%START_NOW%"=="S" (
    start "" "%~dp0launch.bat"
)
exit /b 0
