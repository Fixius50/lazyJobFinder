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

:: 3. Copiar plantillas si no existen y asignar identificador de proyecto único
if not exist ".env" (
    if not exist ".env.example" (
        echo [ERROR] No se encontro la plantilla requerida '.env.example'.
        pause
        exit /b 1
    )
    copy ".env.example" ".env" >nul
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Fallo al copiar '.env.example' a '.env'.
        pause
        exit /b 1
    )
    set "RAND_SUFFIX=%RANDOM%%TIME:~6,2%"
    echo.>>".env"
    echo # Identificador unico de instalacion para aislamiento Docker Compose>>".env"
    echo COMPOSE_PROJECT_NAME=lazyjob_!RAND_SUFFIX!>>".env"
    echo [OK] Archivo de entorno .env creado con proyecto Compose unico (lazyjob_!RAND_SUFFIX!).
) else (
    echo [i] Archivo .env existente detectado. Conservando credenciales e identificador de proyecto previos.
)

:: Validar que .env contenga COMPOSE_PROJECT_NAME
findstr /r /c:"^COMPOSE_PROJECT_NAME=" ".env" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    set "RAND_SUFFIX=%RANDOM%%TIME:~6,2%"
    echo.>>".env"
    echo # Identificador unico de instalacion para aislamiento Docker Compose>>".env"
    echo COMPOSE_PROJECT_NAME=lazyjob_!RAND_SUFFIX!>>".env"
    echo [i] Identificador COMPOSE_PROJECT_NAME añadido a .env.
)

:: Copiar plantillas de configuracion
if not exist "config\settings.yaml" (
    if exist "config-templates\settings.yaml" (
        copy "config-templates\settings.yaml" "config\settings.yaml" >nul
        if %ERRORLEVEL% neq 0 (
            echo [ERROR] Fallo al copiar plantilla settings.yaml.
            pause
            exit /b 1
        )
        echo [OK] Plantilla config\settings.yaml copiada.
    )
)

if not exist "config\profile.yaml" (
    if exist "config-templates\profile.yaml" (
        copy "config-templates\profile.yaml" "config\profile.yaml" >nul
        if %ERRORLEVEL% neq 0 (
            echo [ERROR] Fallo al copiar plantilla profile.yaml.
            pause
            exit /b 1
        )
        echo [OK] Plantilla config\profile.yaml copiada.
    )
)

if not exist "config\shared_constants.json" (
    if exist "config-templates\shared_constants.json" (
        copy "config-templates\shared_constants.json" "config\shared_constants.json" >nul
        if %ERRORLEVEL% neq 0 (
            echo [ERROR] Fallo al copiar plantilla shared_constants.json.
            pause
            exit /b 1
        )
        echo [OK] Plantilla config\shared_constants.json copiada.
    )
)

:: 4. Comprobacion de componentes de distribucion completa
set "IS_LIGHT=0"
if exist ".light_release" set "IS_LIGHT=1"

if "!IS_LIGHT!"=="0" (
    if not exist "images.tar" (
        echo [ERROR] Falta el componente obligatorio 'images.tar' en esta distribucion completa.
        echo         Para distribucion ligera sin imagenes, añade el archivo '.light_release'.
        pause
        exit /b 1
    )
    if not exist "ollama_model.tar.gz" (
        echo [ERROR] Falta el componente obligatorio 'ollama_model.tar.gz' en esta distribucion completa.
        echo         Para distribucion ligera sin modelo, añade el archivo '.light_release'.
        pause
        exit /b 1
    )
)

:: 4.1 Importar imagenes de Docker si images.tar esta presente
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
) else (
    echo [i] Distribucion ligera: omision de importacion de images.tar.
)

:: 4.2 Restaurar modelo de Ollama en el volumen persistente si ollama_model.tar.gz esta presente
if exist "ollama_model.tar.gz" (
    echo.
    echo [i] Preparando volumen persistente de Ollama...
    docker compose up --no-start ollama >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Fallo al inicializar el contenedor/volumen de Ollama con docker compose.
        pause
        exit /b 1
    )
    echo [i] Restaurando datos del modelo IA empaquetado en el volumen persistente...
    docker compose run --rm --entrypoint /bin/sh -v "%~dp0":/backup ollama -c "tar xzf /backup/ollama_model.tar.gz -C /root/.ollama"
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] No se pudo restaurar el modelo de IA en el volumen de Ollama.
        pause
        exit /b 1
    )
    echo [OK] Modelo IA precargado en el volumen local de Ollama.
) else (
    echo [i] Distribucion ligera: omision de precarga offline de modelo Ollama.
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
