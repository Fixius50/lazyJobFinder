@echo off
setlocal enabledelayedexpansion
title lazyJobFinder - Lanzador Principal

cd /d "%~dp0"

if not defined PYTHONPYCACHEPREFIX set "PYTHONPYCACHEPREFIX=%~dp0.cache\pycache"

set "CLI_INVOKED=0"

:: -----------------------------------------------------------------------------
:: Argumentos directos por linea de comandos
:: -----------------------------------------------------------------------------
if "%~1"=="--help" goto :SHOW_HELP
if "%~1"=="-h" goto :SHOW_HELP
if "%~1"=="/?" goto :SHOW_HELP

if "%~1"=="--package" ( set "CLI_INVOKED=1" & goto :BUILD_PACKAGE )
if "%~1"=="-k" ( set "CLI_INVOKED=1" & goto :BUILD_PACKAGE )
if "%~1"=="2" ( set "CLI_INVOKED=1" & goto :BUILD_PACKAGE )

if "%~1"=="--all" ( set "CLI_INVOKED=1" & goto :START_ALL )
if "%~1"=="-a" ( set "CLI_INVOKED=1" & goto :START_ALL )
if "%~1"=="1" ( set "CLI_INVOKED=1" & goto :START_ALL )

:: -----------------------------------------------------------------------------
:: Menu Interactivo Unificado
:: -----------------------------------------------------------------------------
:MENU
cd /d "%~dp0"
cls
echo =====================================================================
echo                 lazyJobFinder - Lanzador Principal
echo        Sistema Local, Autonomo y Gratuito de Busqueda de Empleo
echo =====================================================================
echo.
echo Selecciona que deseas ejecutar:
echo.
echo   [1] Arrancar lazyJobFinder (Todo unificado en http://localhost:8000)
echo   [2] Empaquetar Distribucion e Instaladores (Windows y Linux)
echo   [Q] Salir (Detiene los servicios en ejecucion)
echo.
choice /c 12q /n /m "Introduce una opcion [1, 2, Q]: "

if errorlevel 3 goto :STOP_AND_EXIT
if errorlevel 2 goto :BUILD_PACKAGE
if errorlevel 1 goto :START_ALL
goto :MENU

:: -----------------------------------------------------------------------------
:: Ayuda por Linea de Comandos
:: -----------------------------------------------------------------------------
:SHOW_HELP
echo Uso de start.bat:
echo   start.bat               Modo interactivo con menu simplificado
echo   start.bat --all         Arrancar directamente la aplicacion unificada
echo   start.bat --package     Empaquetar instaladores y distribucion (Windows/Linux)
echo   start.bat --help        Mostrar este mensaje de ayuda
goto :EXIT

:: -----------------------------------------------------------------------------
:: Rutina de Verificacion y Actualizacion Automatica
:: -----------------------------------------------------------------------------
:CHECK_PREREQS
cd /d "%~dp0"
echo.
echo --^> Verificando requisitos y entorno del sistema...

:: 1. Archivo .env
if not exist ".env" (
    echo   [i] Archivo .env no encontrado. Creando desde .env.example...
    copy ".env.example" ".env" >nul
    echo   [OK] Archivo .env generado.
) else (
    echo   [OK] Archivo .env presente.
)

:: 2. Docker
docker info >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   [!] El motor de Docker Desktop no esta activo.
    set "DOCKER_EXE="
    if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" set "DOCKER_EXE=C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if not defined DOCKER_EXE if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" set "DOCKER_EXE=%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
    if not defined DOCKER_EXE if exist "%ProgramFiles(x86)%\Docker\Docker\Docker Desktop.exe" set "DOCKER_EXE=%ProgramFiles(x86)%\Docker\Docker\Docker Desktop.exe"
    if not defined DOCKER_EXE if exist "%LOCALAPPDATA%\Programs\Docker Desktop\Docker Desktop.exe" set "DOCKER_EXE=%LOCALAPPDATA%\Programs\Docker Desktop\Docker Desktop.exe"

    if defined DOCKER_EXE (
        echo   [i] Iniciando Docker Desktop automaticamente en segundo plano...
        start "" "!DOCKER_EXE!"
        echo   [i] Esperando a que el motor Docker responda...
        set /a DOCKER_RETRY=0
        :WAIT_DOCKER
        timeout /t 3 /nobreak >nul
        docker info >nul 2>&1
        if !ERRORLEVEL! neq 0 (
            set /a DOCKER_RETRY+=1
            if !DOCKER_RETRY! lss 25 (
                echo       Esperando a Docker Desktop... [!DOCKER_RETRY!/25]
                goto :WAIT_DOCKER
            ) else (
                echo.
                echo   [ERROR] Docker Desktop no respondio a tiempo.
                echo           Por favor, abre Docker Desktop manualmente y espera a que el icono este en verde.
                echo.
                exit /b 1
            )
        ) else (
            echo   [OK] Motor de Docker conectado y listo.
        )
    ) else (
        echo   [ERROR] No se encontro Docker Desktop. Por favor instalalo o inicialo manualmente.
        exit /b 1
    )
) else (
    echo   [OK] Motor de Docker operativo.
)

:: 3. Compilacion automatica del panel web estatico si no existe o hubo cambios
if exist "%~dp0web\out\index.html" goto :WEB_OK
echo   [i] Compilando panel web estatico unificado (Next.js)...
if exist "%~dp0web\node_modules" goto :DO_BUILD
pushd "%~dp0web"
call npm install
popd

:DO_BUILD
pushd "%~dp0web"
call npm run build
popd
if %ERRORLEVEL% equ 0 (
    echo   [OK] Panel web compilado correctamente.
) else (
    echo   [!] Advertencia en la compilacion web. Se intentara continuar.
)
goto :CHECK_DONE

:WEB_OK
echo   [OK] Panel web estatico verificado en web\out.

:CHECK_DONE
exit /b 0

:: -----------------------------------------------------------------------------
:: Opcion 1: Arrancar TODO Unificado
:: -----------------------------------------------------------------------------
:START_ALL
call :CHECK_PREREQS
if %ERRORLEVEL% neq 0 (
    if "%CLI_INVOKED%"=="1" goto :EXIT
    pause
    goto :MENU
)

cd /d "%~dp0"
echo.
echo --^> Levantando servicios Docker Compose...
docker compose up -d
if %ERRORLEVEL% neq 0 (
    echo.
    echo   [ERROR] No se pudieron arrancar los contenedores.
    if "%CLI_INVOKED%"=="1" goto :EXIT
    pause
    goto :MENU
)

:: Comprobar modelo de IA en Ollama previamente antes de descargar
echo --^> Verificando modelo de IA en Ollama...
docker exec lazyjob_ollama ollama list 2>nul | findstr /i "qwen2.5:3b-instruct" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo   [OK] Modelo qwen2.5:3b-instruct verificado y disponible en Ollama.
) else (
    echo   [i] Modelo qwen2.5:3b-instruct no encontrado. Descargando en Ollama por primera vez...
    docker exec lazyjob_ollama ollama pull qwen2.5:3b-instruct
    if !ERRORLEVEL! equ 0 (
        echo   [OK] Modelo qwen2.5:3b-instruct descargado con exito.
    ) else (
        echo   [!] Advertencia al descargar modelo en Ollama.
    )
)

echo --^> Esperando a que el backend unificado responda en http://127.0.0.1:8000...
set /a API_RETRY=0
:WAIT_API
ping -n 3 127.0.0.1 >nul 2>&1
curl -s -f --connect-timeout 2 --max-time 3 http://127.0.0.1:8000/api/health >nul 2>&1
if !ERRORLEVEL! neq 0 (
    set /a API_RETRY+=1
    if !API_RETRY! lss 25 (
        echo       Iniciando servicios del backend... [!API_RETRY!/25]
        goto :WAIT_API
    ) else (
        echo   [!] El backend tarda en responder. Continuando de todos modos...
    )
) else (
    echo   [OK] Backend unificado conectado y respondiendo en http://127.0.0.1:8000
)

echo.
echo =====================================================================
echo   [SISTEMA LISTO] Todos los servicios estan activos y unificados:
echo     - Panel Web Unificado: http://localhost:8000
echo     - API REST y Docs:     http://127.0.0.1:8000/api/docs
echo     - Motor Ollama:        http://localhost:11434
echo =====================================================================
echo.
echo --^> Abriendo el panel de administracion en tu navegador...
start http://localhost:8000
echo.
echo =====================================================================
echo   Mostrando actividad de la IA y el backend en tiempo real:
echo   (Pulsa Ctrl+C para salir y detener los servicios)
echo =====================================================================
echo.
docker compose logs -f lazyjobfinder
goto :STOP_AND_EXIT

:: -----------------------------------------------------------------------------
:: Opcion 2: Empaquetar Distribucion e Instaladores
:: -----------------------------------------------------------------------------
:BUILD_PACKAGE
cd /d "%~dp0"
echo.
echo =====================================================================
echo   Generando Distribucion e Instaladores (Windows y Linux)
echo =====================================================================
echo.
python packaging\build_release.py %*
echo.
if "%CLI_INVOKED%"=="1" goto :EXIT
pause
goto :MENU

:: -----------------------------------------------------------------------------
:: Detener Servicios y Salir Automáticamente
:: -----------------------------------------------------------------------------
:STOP_AND_EXIT
cd /d "%~dp0"
echo.
echo --^> Deteniendo servicios Docker ordenadamente...
docker compose stop >nul 2>&1
echo   [OK] Servicios detenidos. Datos y configuracion conservados intactos.
goto :EXIT

:EXIT
echo.
echo Finalizado.
