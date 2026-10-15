@echo off
setlocal enabledelayedexpansion
title lazyJobFinder - Lanzador Multifuncion Unificado

cd /d "%~dp0"

set "CLI_INVOKED=0"

:: -----------------------------------------------------------------------------
:: Argumentos directos por linea de comandos
:: -----------------------------------------------------------------------------
if "%~1"=="--help" goto :SHOW_HELP
if "%~1"=="-h" goto :SHOW_HELP
if "%~1"=="/?" goto :SHOW_HELP

if "%~1"=="--all" ( set "CLI_INVOKED=1" & goto :START_ALL )
if "%~1"=="-a" ( set "CLI_INVOKED=1" & goto :START_ALL )
if "%~1"=="1" ( set "CLI_INVOKED=1" & goto :START_ALL )

if "%~1"=="--docker" ( set "CLI_INVOKED=1" & goto :START_DOCKER )
if "%~1"=="-d" ( set "CLI_INVOKED=1" & goto :START_DOCKER )
if "%~1"=="2" ( set "CLI_INVOKED=1" & goto :START_DOCKER )

if "%~1"=="--web" ( set "CLI_INVOKED=1" & goto :START_WEB )
if "%~1"=="-w" ( set "CLI_INVOKED=1" & goto :START_WEB )
if "%~1"=="3" ( set "CLI_INVOKED=1" & goto :START_WEB )

if "%~1"=="--status" ( set "CLI_INVOKED=1" & goto :SHOW_STATUS )
if "%~1"=="-s" ( set "CLI_INVOKED=1" & goto :SHOW_STATUS )
if "%~1"=="4" ( set "CLI_INVOKED=1" & goto :SHOW_STATUS )

if "%~1"=="--pull" ( set "CLI_INVOKED=1" & goto :PULL_MODEL )
if "%~1"=="-p" ( set "CLI_INVOKED=1" & goto :PULL_MODEL )
if "%~1"=="5" ( set "CLI_INVOKED=1" & goto :PULL_MODEL )

if "%~1"=="--stop" ( set "CLI_INVOKED=1" & goto :STOP_SERVICES )
if "%~1"=="6" ( set "CLI_INVOKED=1" & goto :STOP_SERVICES )

:: -----------------------------------------------------------------------------
:: Menu Interactivo
:: -----------------------------------------------------------------------------
:MENU
cls
echo =====================================================================
echo              lazyJobFinder - Lanzador Unico Multifuncion
echo        Sistema Local, Autonomo y Gratuito de Busqueda de Empleo
echo =====================================================================
echo.
echo Selecciona que deseas ejecutar:
echo.
echo   [1] Arrancar TODO (Docker + Ollama + API + Web en navegador)
echo   [2] Arrancar solo Docker (Ollama y Backend App en segundo plano)
echo   [3] Arrancar solo el Panel Web Next.js (http://localhost:3000)
echo   [4] Diagnostico de estado y salud de los servicios
echo   [5] Descargar / Actualizar modelo IA en Ollama (qwen2.5:3b-instruct)
echo   [6] Detener todos los servicios ordenadamente
echo   [Q] Salir
echo.
set /p "OPTION=Introduce una opcion (1-6, Q): "

if /i "%OPTION%"=="1" goto :START_ALL
if /i "%OPTION%"=="2" goto :START_DOCKER
if /i "%OPTION%"=="3" goto :START_WEB
if /i "%OPTION%"=="4" goto :SHOW_STATUS
if /i "%OPTION%"=="5" goto :PULL_MODEL
if /i "%OPTION%"=="6" goto :STOP_SERVICES
if /i "%OPTION%"=="q" goto :EXIT
goto :MENU

:: -----------------------------------------------------------------------------
:: Ayuda por Linea de Comandos
:: -----------------------------------------------------------------------------
:SHOW_HELP
echo Uso de start.bat:
echo   start.bat               Modo interactivo con menu visual
echo   start.bat --all         Arrancar todo (Docker, Ollama y panel Web)
echo   start.bat --docker      Arrancar solo los contenedores Docker
echo   start.bat --web         Arrancar solo el servidor web de Next.js
echo   start.bat --status      Mostrar estado de salud y contenedores
echo   start.bat --pull        Descargar modelo de IA en Ollama
echo   start.bat --stop        Detener contenedores Docker ordenadamente
echo   start.bat --help        Mostrar este mensaje de ayuda
goto :EXIT

:: -----------------------------------------------------------------------------
:: Rutina de Verificacion de Requisitos Previos
:: -----------------------------------------------------------------------------
:CHECK_PREREQS
echo.
echo --^> Verificando requisitos del sistema...

:: 1. Archivo .env
if not exist ".env" (
    echo   [i] Archivo .env no encontrado. Creando desde .env.example...
    copy ".env.example" ".env" >nul
    echo   [OK] Archivo .env generado.
) else (
    echo   [OK] Archivo .env presente.
)

:: 2. Docker
docker compose version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   [!] Docker Compose no responde. Asegurate de que Docker Desktop este abierto.
    if "%CLI_INVOKED%"=="0" (
        echo       Pulsa cualquier tecla para continuar de todos modos...
        pause >nul
    )
) else (
    echo   [OK] Docker Compose operativo.
)

:: 3. Node.js y npm
node --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   [!] Node.js no encontrado en PATH. Es necesario para el frontend Next.js.
) else (
    echo   [OK] Node.js detectado.
)

:: 4. Dependencias del frontend
if not exist "web\node_modules" (
    echo   [i] Instalando dependencias del panel web (npm install)...
    cd web
    call npm install
    cd ..
    echo   [OK] Dependencias web instaladas.
) else (
    echo   [OK] Dependencias web instaladas.
)
exit /b 0

:: -----------------------------------------------------------------------------
:: Opcion 1: Arrancar Todo
:: -----------------------------------------------------------------------------
:START_ALL
call :CHECK_PREREQS
echo.
echo --^> Arrancando contenedores Docker Compose...
docker compose up -d

echo --^> Esperando inicializacion de servicios...
timeout /t 3 /nobreak >nul

:: Comprobar si el modelo de Ollama esta descargado
docker exec lazyjob_ollama ollama list 2>nul | findstr /i "qwen2.5:3b-instruct" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo --^> Descargando modelo ligero qwen2.5:3b-instruct en Ollama (primera vez)...
    docker exec lazyjob_ollama ollama pull qwen2.5:3b-instruct
)

echo --^> Abriendo el panel de administracion en tu navegador...
start http://localhost:3000

echo --^> Iniciando servidor Next.js en primer plano...
echo     (Pulsa Ctrl+C para detener el servidor web)
echo.
cd web
call npm run dev
goto :EXIT

:: -----------------------------------------------------------------------------
:: Opcion 2: Solo Docker
:: -----------------------------------------------------------------------------
:START_DOCKER
call :CHECK_PREREQS
echo.
echo --^> Arrancando servicios Docker en segundo plano...
docker compose up -d
echo.
echo   [OK] Ollama activo en: http://localhost:11434
echo   [OK] API FastAPI activa en: http://127.0.0.1:8000/api/docs
echo.
if "%CLI_INVOKED%"=="1" goto :EXIT
pause
goto :MENU

:: -----------------------------------------------------------------------------
:: Opcion 3: Solo Frontend Web
:: -----------------------------------------------------------------------------
:START_WEB
call :CHECK_PREREQS
echo.
echo --^> Abriendo navegador en http://localhost:3000...
start http://localhost:3000
echo.
echo --^> Iniciando servidor Next.js...
cd web
call npm run dev
goto :EXIT

:: -----------------------------------------------------------------------------
:: Opcion 4: Diagnostico de Estado
:: -----------------------------------------------------------------------------
:SHOW_STATUS
echo.
echo =====================================================================
echo                   Diagnostico de lazyJobFinder
echo =====================================================================
echo.
echo --^> Estado de contenedores Docker Compose:
docker compose ps
echo.
echo --^> Salud de Ollama (http://localhost:11434):
curl -s http://localhost:11434/api/tags 2>nul || echo [!] Ollama no responde o no esta corriendo.
echo.
echo.
echo --^> Salud de API lazyJobFinder (http://127.0.0.1:8000/api/health):
curl -s http://127.0.0.1:8000/api/health 2>nul || echo [!] API no responde en puerto 8000.
echo.
echo.
if "%CLI_INVOKED%"=="1" goto :EXIT
pause
goto :MENU

:: -----------------------------------------------------------------------------
:: Opcion 5: Descargar / Actualizar Modelo IA
:: -----------------------------------------------------------------------------
:PULL_MODEL
echo.
echo --^> Descargando modelo qwen2.5:3b-instruct en Ollama...
docker compose exec -T ollama ollama pull qwen2.5:3b-instruct
echo.
if "%CLI_INVOKED%"=="1" goto :EXIT
pause
goto :MENU

:: -----------------------------------------------------------------------------
:: Opcion 6: Detener Servicios
:: -----------------------------------------------------------------------------
:STOP_SERVICES
echo.
echo --^> Deteniendo servicios Docker ordenadamente...
docker compose stop
echo.
echo   [OK] Servicios detenidos. Datos y modelos conservados intactos.
echo.
if "%CLI_INVOKED%"=="1" goto :EXIT
pause
goto :MENU

:EXIT
echo.
echo Finalizado.
