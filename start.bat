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

if "%~1"=="--build" ( set "CLI_INVOKED=1" & goto :REBUILD_ALL )
if "%~1"=="-b" ( set "CLI_INVOKED=1" & goto :REBUILD_ALL )
if "%~1"=="7" ( set "CLI_INVOKED=1" & goto :REBUILD_ALL )

:: -----------------------------------------------------------------------------
:: Menu Interactivo
:: -----------------------------------------------------------------------------
:MENU
cd /d "%~dp0"
cls
echo =====================================================================
echo              lazyJobFinder - Lanzador Unico Multifuncion
echo        Sistema Local, Autonomo y Gratuito de Busqueda de Empleo
echo =====================================================================
echo.
echo Selecciona que deseas ejecutar:
echo.
echo   [1] Arrancar TODO unificado (Docker + Ollama + Web en http://localhost:8000)
echo   [2] Arrancar solo Docker (Ollama y Backend App en segundo plano)
echo   [3] Arrancar Panel Web en Modo Desarrollo (Next.js http://localhost:3000)
echo   [4] Diagnostico de estado y salud de los servicios
echo   [5] Descargar / Actualizar modelo IA en Ollama (qwen2.5:3b-instruct)
echo   [6] Detener todos los servicios ordenadamente
echo   [7] Reconstruir y Actualizar TODO (Frontend Next.js + Backend Docker)
echo   [Q] Salir
echo.
choice /c 1234567q /n /m "Introduce una opcion [1-7, Q]: "

if errorlevel 8 goto :EXIT
if errorlevel 7 goto :REBUILD_ALL
if errorlevel 6 goto :STOP_SERVICES
if errorlevel 5 goto :PULL_MODEL
if errorlevel 4 goto :SHOW_STATUS
if errorlevel 3 goto :START_WEB
if errorlevel 2 goto :START_DOCKER
if errorlevel 1 goto :START_ALL
goto :MENU

:: -----------------------------------------------------------------------------
:: Ayuda por Linea de Comandos
:: -----------------------------------------------------------------------------
:SHOW_HELP
echo Uso de start.bat:
echo   start.bat               Modo interactivo con menu visual
echo   start.bat --all         Arrancar todo: Docker, Ollama y panel Web
echo   start.bat --build       Reconstruir y compilar todo (Frontend + Backend Docker)
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
cd /d "%~dp0"
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
docker info >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   [!] El motor de Docker Desktop no esta activo.
    set "DOCKER_EXE="
    if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" set "DOCKER_EXE=C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if not defined DOCKER_EXE if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" set "DOCKER_EXE=%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
    if not defined DOCKER_EXE if exist "%ProgramFiles(x86)%\Docker\Docker\Docker Desktop.exe" set "DOCKER_EXE=%ProgramFiles(x86)%\Docker\Docker\Docker Desktop.exe"
    if not defined DOCKER_EXE if exist "%LOCALAPPDATA%\Programs\Docker Desktop\Docker Desktop.exe" set "DOCKER_EXE=%LOCALAPPDATA%\Programs\Docker Desktop\Docker Desktop.exe"

    if defined DOCKER_EXE (
        echo   [i] Iniciando Docker Desktop automaticamente desde: "!DOCKER_EXE!"
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
        echo   [ERROR] No se encontro la ruta de Docker Desktop. Por favor abrelo manualmente.
        exit /b 1
    )
) else (
    echo   [OK] Docker y motor de contenedores operativos.
)

:: 3. Node.js y npm
node --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   [!] Node.js no encontrado en PATH. Es necesario para el frontend Next.js.
) else (
    echo   [OK] Node.js detectado.
)

:: 4. Dependencias del frontend y compilacion estatica unificada
if not exist "%~dp0web\node_modules" (
    echo   [i] Instalando dependencias del panel web con npm install...
    pushd "%~dp0web"
    call npm install
    popd
    echo   [OK] Dependencias web instaladas.
) else (
    echo   [OK] Dependencias web instaladas.
)

echo   [i] Compilando panel web estatico unificado (Next.js)...
pushd "%~dp0web"
call npm run build
popd
if %ERRORLEVEL% equ 0 (
    echo   [OK] Panel web actualizado y listo para puerto unificado 8000.
) else (
    echo   [!] Advertencia: La compilacion del panel web reporto errores. Se usara la version previa si existe.
)
exit /b 0

:: -----------------------------------------------------------------------------
:: Opcion 1: Arrancar Todo (Puerto Unificado 8000)
:: -----------------------------------------------------------------------------
:START_ALL
call :CHECK_PREREQS
if %ERRORLEVEL% neq 0 goto :EXIT
cd /d "%~dp0"
echo.
echo --^> Arrancando contenedores Docker Compose...
docker compose up -d
if %ERRORLEVEL% neq 0 (
    echo.
    echo   [ERROR] No se pudieron arrancar los contenedores de Docker.
    echo           Asegurate de que Docker Desktop este abierto y operativo.
    echo.
    if "%CLI_INVOKED%"=="1" goto :EXIT
    pause
    goto :MENU
)

echo --^> Esperando a que el backend unificado responda en http://127.0.0.1:8000...
set /a API_RETRY=0
:WAIT_API
timeout /t 2 /nobreak >nul
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

docker exec lazyjob_ollama ollama list 2>nul | findstr /i "qwen2.5:3b-instruct" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo --^> Descargando modelo ligero qwen2.5:3b-instruct en Ollama...
    docker exec lazyjob_ollama ollama pull qwen2.5:3b-instruct
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
if "%CLI_INVOKED%"=="1" goto :EXIT
pause
goto :MENU

:: -----------------------------------------------------------------------------
:: Opcion 2: Solo Docker
:: -----------------------------------------------------------------------------
:START_DOCKER
call :CHECK_PREREQS
cd /d "%~dp0"
echo.
echo --^> Arrancando servicios Docker en segundo plano...
docker compose up -d
if %ERRORLEVEL% neq 0 (
    echo.
    echo   [ERROR] No se pudieron arrancar los contenedores de Docker.
    echo           Asegurate de que Docker Desktop este abierto y operativo.
    echo.
    if "%CLI_INVOKED%"=="1" goto :EXIT
    pause
    goto :MENU
)
echo.
echo   [OK] Ollama activo en: http://localhost:11434
echo   [OK] API y Web unificada en: http://127.0.0.1:8000
echo.
if "%CLI_INVOKED%"=="1" goto :EXIT
pause
goto :MENU

:: -----------------------------------------------------------------------------
:: Opcion 3: Solo Frontend Web (Modo Desarrollo con Hot-Reload)
:: -----------------------------------------------------------------------------
:START_WEB
call :CHECK_PREREQS
cd /d "%~dp0web"
echo.
echo --^> Abriendo navegador en http://localhost:3000 (Modo Desarrollo)...
start http://localhost:3000
echo --^> Iniciando servidor Next.js en primer plano...
echo     (Conectando directamente a la API en http://127.0.0.1:8000/api sin socket hang up)
echo     Pulsa Ctrl+C para detener el servidor web.
echo.
call npm run dev
goto :EXIT

:: -----------------------------------------------------------------------------
:: Opcion 4: Diagnostico de Estado
:: -----------------------------------------------------------------------------
:SHOW_STATUS
cd /d "%~dp0"
echo.
echo =====================================================================
echo                   Diagnostico de lazyJobFinder
echo =====================================================================
echo.
echo --^> Estado de contenedores Docker Compose:
docker compose ps
echo.
echo --^> Salud de Ollama (http://localhost:11434):
curl -s --connect-timeout 2 --max-time 3 http://localhost:11434/api/tags 2>nul || echo [!] Ollama no responde o no esta corriendo.
echo.
echo.
echo --^> Salud de API lazyJobFinder (http://127.0.0.1:8000/api/health):
curl -s --connect-timeout 2 --max-time 3 http://127.0.0.1:8000/api/health 2>nul || echo [!] API no responde en puerto 8000.
echo.
echo.
if "%CLI_INVOKED%"=="1" goto :EXIT
pause
goto :MENU

:: -----------------------------------------------------------------------------
:: Opcion 5: Descargar / Actualizar Modelo IA
:: -----------------------------------------------------------------------------
:PULL_MODEL
cd /d "%~dp0"
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
cd /d "%~dp0"
echo.
echo --^> Deteniendo servicios Docker ordenadamente...
docker compose stop
echo.
echo   [OK] Servicios detenidos. Datos y modelos conservados intactos.
echo.
if "%CLI_INVOKED%"=="1" goto :EXIT
pause
goto :MENU

:: -----------------------------------------------------------------------------
:: Opcion 7: Reconstruir y Actualizar TODO (Frontend + Backend)
:: -----------------------------------------------------------------------------
:REBUILD_ALL
call :CHECK_PREREQS
if %ERRORLEVEL% neq 0 goto :EXIT
cd /d "%~dp0"
echo.
echo =====================================================================
echo   Reconstruyendo y Actualizando lazyJobFinder (Frontend + Backend)
echo =====================================================================
echo.
echo [1/3] Compilando panel web estatico unificado (Next.js)...
pushd "%~dp0web"
call npm run build
if %ERRORLEVEL% neq 0 (
    echo.
    echo   [ERROR] Fallo la compilacion del panel web.
    popd
    if "%CLI_INVOKED%"=="1" goto :EXIT
    pause
    goto :MENU
)
popd
echo   [OK] Panel web compilado correctamente en web\out.
echo.
echo [2/3] Reconstruyendo imagen de contenedor Docker (Backend)...
docker compose build --no-cache lazyjobfinder
if %ERRORLEVEL% neq 0 (
    echo.
    echo   [ERROR] Fallo la reconstruccion del contenedor Docker.
    if "%CLI_INVOKED%"=="1" goto :EXIT
    pause
    goto :MENU
)
echo   [OK] Imagen Docker de lazyjobfinder reconstruida sin cache.
echo.
echo [3/3] Reiniciando contenedores con los nuevos cambios...
docker compose up -d --force-recreate lazyjobfinder
if %ERRORLEVEL% neq 0 (
    echo.
    echo   [ERROR] No se pudo reiniciar el contenedor.
    if "%CLI_INVOKED%"=="1" goto :EXIT
    pause
    goto :MENU
)

echo --^> Esperando a que el backend unificado responda en http://127.0.0.1:8000...
set /a API_RETRY=0
:WAIT_API_REBUILD
timeout /t 2 /nobreak >nul
curl -s -f http://127.0.0.1:8000/api/health >nul 2>&1
if !ERRORLEVEL! neq 0 (
    set /a API_RETRY+=1
    if !API_RETRY! lss 25 (
        echo       Iniciando servicios del backend... [!API_RETRY!/25]
        goto :WAIT_API_REBUILD
    ) else (
        echo   [!] El backend tarda en responder. Continuando de todos modos...
    )
) else (
    echo   [OK] Backend unificado conectado y respondiendo en http://127.0.0.1:8000
)

echo.
echo =====================================================================
echo   [ACTUALIZACION COMPLETADA] Todos los cambios han sido aplicados:
echo     - Panel Web Unificado: http://localhost:8000
echo     - API REST y Docs:     http://127.0.0.1:8000/api/docs
echo =====================================================================
echo.
echo --^> Abriendo el panel de administracion en tu navegador...
start http://localhost:8000
echo.
if "%CLI_INVOKED%"=="1" goto :EXIT
pause
goto :MENU

:EXIT
echo.
echo Finalizado.
