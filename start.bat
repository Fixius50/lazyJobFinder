@echo off
setlocal enabledelayedexpansion
title lazyJobFinder - Lanzador Principal

cd /d "%~dp0"

if not defined PYTHONPYCACHEPREFIX set "PYTHONPYCACHEPREFIX=%~dp0src\__pycache__"

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

:: 0. Limpieza de archivos temporales residuales y unificacion de pycache en src\__pycache__
if exist "%~dp0data\uploaded_cvs\.extracted_*" del /f /q "%~dp0data\uploaded_cvs\.extracted_*" >nul 2>&1
python -c "import os, shutil; [shutil.rmtree(os.path.join(r, d)) for r, dirs, _ in os.walk('src') for d in dirs if d == '__pycache__' and os.path.abspath(r) != os.path.abspath('src')]" >nul 2>&1

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
    call :FIND_DOCKER_EXE

    if defined DOCKER_EXE (
        echo   [i] Iniciando Docker Desktop automaticamente en segundo plano...
        start "" "!DOCKER_EXE!"
        echo   [i] Esperando a que el motor Docker responda...
        set /a DOCKER_RETRY=0
        :WAIT_DOCKER
        ping -n 4 127.0.0.1 >nul 2>&1
        docker info >nul 2>&1
        if !ERRORLEVEL! neq 0 (
            set /a DOCKER_RETRY+=1
            if !DOCKER_RETRY! lss 35 (
                echo       Esperando a que el motor Docker Desktop termine de iniciar... [!DOCKER_RETRY!/35]
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
        echo.
        echo   [ERROR] No se encontro Docker Desktop instalado en las rutas habituales.
        echo           lazyJobFinder ejecuta la IA y el backend dentro de Docker para que no
        echo           tengas que configurar Python ni dependencias complejas en tu equipo.
        echo           Por favor, instala Docker Desktop desde: https://www.docker.com/products/docker-desktop/
        echo.
        exit /b 1
    )
) else (
    echo   [OK] Motor de Docker operativo.
)

:: 3. Verificacion y compilacion automatica del panel web estatico
set "NEED_BUILD=0"
if not exist "%~dp0web\out\index.html" set "NEED_BUILD=1"
if not exist "%~dp0web\out\_next" set "NEED_BUILD=1"

if "!NEED_BUILD!"=="0" call :CHECK_WEB_FRESHNESS

if "!NEED_BUILD!"=="1" (
    echo   [i] Actualizando panel web estatico unificado - Next.js...
    if not exist "%~dp0web\node_modules" (
        pushd "%~dp0web"
        call npm install
        popd
    )
    pushd "%~dp0web"
    call npm run build
    popd
    if !ERRORLEVEL! equ 0 (
        echo   [OK] Panel web compilado y sincronizado correctamente.
    ) else (
        echo   [!] Advertencia en la compilacion web. Se intentara continuar.
    )
) else (
    echo   [OK] Panel web estatico sincronizado y verificado en web\out.
)

goto :CHECK_DONE

:FIND_DOCKER_EXE
set "DOCKER_EXE="
if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" set "DOCKER_EXE=C:\Program Files\Docker\Docker\Docker Desktop.exe"
if not defined DOCKER_EXE if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" set "DOCKER_EXE=%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
if not defined DOCKER_EXE if exist "%ProgramFiles(x86)%\Docker\Docker\Docker Desktop.exe" set "DOCKER_EXE=%ProgramFiles(x86)%\Docker\Docker\Docker Desktop.exe"
if not defined DOCKER_EXE if exist "%LOCALAPPDATA%\Programs\Docker Desktop\Docker Desktop.exe" set "DOCKER_EXE=%LOCALAPPDATA%\Programs\Docker Desktop\Docker Desktop.exe"
exit /b 0

:CHECK_WEB_FRESHNESS
powershell -NoProfile -Command "$src = (Get-ChildItem -Path '%~dp0web\src' -Recurse | Measure-Object -Property LastWriteTime -Maximum).Maximum; $out = (Get-Item '%~dp0web\out\index.html').LastWriteTime; if ($src -gt $out) { exit 1 } else { exit 0 }" >nul 2>&1
if errorlevel 1 set "NEED_BUILD=1"
exit /b 0

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
echo --^> Comprobando capacidades de aceleracion por hardware en Docker...
set "DOCKER_COMPOSE_ARGS="
set "DETECTED_GPU="

:: 1. Comprobar si Ollama ya esta corriendo en el sistema host de Windows (maxima aceleracion GPU nativa)
curl -s -f --connect-timeout 1 http://127.0.0.1:11434/api/tags >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo   [OK] Servidor Ollama local detectado en Windows [http://127.0.0.1:11434].
    echo        lazyJobFinder conectara directamente con el host para aprovechar la aceleracion GPU.
)

:: 2. Comprobar si Docker dispone de nodos de kernel AMD ROCm nativos (/dev/kfd y /dev/dri de Linux)
docker run --rm --device /dev/kfd hello-world >nul 2>&1
if %ERRORLEVEL% equ 0 (
    if exist "docker-compose.rocm.yml" (
        echo   [OK] Dispositivos AMD ROCm [/dev/kfd] detectados en Docker. Activando ollama/ollama:rocm...
        set "DOCKER_COMPOSE_ARGS=-f docker-compose.yml -f docker-compose.rocm.yml"
    )
)

:: 3. Comprobar si Docker dispone de aceleracion GPU NVIDIA (nvidia-container-toolkit)
if not defined DOCKER_COMPOSE_ARGS (
    where nvidia-smi >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        docker run --rm --gpus all hello-world >nul 2>&1
        if !ERRORLEVEL! equ 0 (
            if exist "docker-compose.gpu.yml" (
                echo   [OK] Aceleracion GPU NVIDIA detectada y activa para Docker.
                set "DOCKER_COMPOSE_ARGS=-f docker-compose.yml -f docker-compose.gpu.yml"
            )
        )
    )
)

:: 4. Comprobar GPU AMD en Windows (WSL2 con ROCDXG /dev/dxg para tarjetas RDNA 3 o forzadas en .env)
if not defined DOCKER_COMPOSE_ARGS (
    for /f "tokens=*" %%G in ('powershell -NoProfile -Command "(Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name) -join '; '" 2^>nul') do set "DETECTED_GPU=%%G"
    
    if defined DETECTED_GPU (
        echo !DETECTED_GPU! | findstr /i "Radeon AMD" >nul 2>&1
        if !ERRORLEVEL! equ 0 (
            :: Deteccion de arquitectura para HSA_OVERRIDE_GFX_VERSION si no esta fijada
            if not defined HSA_OVERRIDE_GFX_VERSION (
                echo !DETECTED_GPU! | findstr /i "7900 7800 7700 7600 W7900 W7800" >nul 2>&1
                if !ERRORLEVEL! equ 0 set "HSA_OVERRIDE_GFX_VERSION=11.0.0"
                echo !DETECTED_GPU! | findstr /i "6900 6800 6700 6600" >nul 2>&1
                if !ERRORLEVEL! equ 0 set "HSA_OVERRIDE_GFX_VERSION=10.3.0"
                echo !DETECTED_GPU! | findstr /i "5700 5600" >nul 2>&1
                if !ERRORLEVEL! equ 0 set "HSA_OVERRIDE_GFX_VERSION=10.1.0"
            )

            set "USE_WSL_ROCM=0"
            if "!USE_ROCM_WSL!"=="1" set "USE_WSL_ROCM=1"
            echo !DETECTED_GPU! | findstr /i "7900 7800 7700 7600 W7900 W7800" >nul 2>&1
            if !ERRORLEVEL! equ 0 set "USE_WSL_ROCM=1"

            if "!USE_WSL_ROCM!"=="1" (
                if exist "docker-compose.rocm-wsl.yml" (
                    echo   [OK] GPU AMD compatible con WSL2 detectada [!DETECTED_GPU!].
                    echo        Activando puente ROCm WSL2 [/dev/dxg + ROCDXG, HSA=!HSA_OVERRIDE_GFX_VERSION!]...
                    set "DOCKER_COMPOSE_ARGS=-f docker-compose.yml -f docker-compose.rocm-wsl.yml"
                )
            ) else (
                echo   [i] GPU AMD detectada en Windows: !DETECTED_GPU!
                echo   [i] Nota: WSL2 no expone ROCm para esta generacion [requiere Linux nativo o Ollama Windows].
            )
        )
    )
)

:: 5. Si no hay dispositivos de GPU expuestos al daemon Docker (entorno estandar de Windows Desktop)
if not defined DOCKER_COMPOSE_ARGS (
    echo   [OK] Inferencia en contenedor Docker configurada en CPU de alto rendimiento [Flash Attention + Q8 KV-Cache + Multi-slot].
    set "DOCKER_COMPOSE_ARGS=-f docker-compose.yml"
)

echo --^> Levantando servicios Docker Compose...
docker compose !DOCKER_COMPOSE_ARGS! up -d
if %ERRORLEVEL% neq 0 (
    echo   [i] Esperando liberacion de puertos en el sistema... reintentando en 3 segundos...
    timeout /t 3 /nobreak >nul 2>&1
    docker compose !DOCKER_COMPOSE_ARGS! up -d
)
if %ERRORLEVEL% neq 0 (
    echo.
    echo   [ERROR] No se pudieron arrancar los contenedores.
    if "%CLI_INVOKED%"=="1" goto :EXIT
    pause
    goto :MENU
)

:: Comprobar modelo de IA en Ollama previamente antes de descargar
echo --^> Verificando modelo de IA en Ollama...
ping -n 4 127.0.0.1 >nul 2>&1
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

echo --^> Esperando a que el backend y los servicios esten completamente listos en http://127.0.0.1:8000...
set /a API_RETRY=0
:WAIT_API
ping -n 3 127.0.0.1 >nul 2>&1
curl -s -f --connect-timeout 2 --max-time 3 http://127.0.0.1:8000/api/system/status >nul 2>&1
if !ERRORLEVEL! neq 0 (
    set /a API_RETRY+=1
    if !API_RETRY! lss 25 (
        echo       Iniciando servicios del backend y estabilizando interfaz... [!API_RETRY!/25]
        goto :WAIT_API
    ) else (
        echo   [!] El backend tarda en responder. Continuando de todos modos...
    )
) else (
    echo   [OK] Backend y servicios conectados correctamente en http://127.0.0.1:8000
)

:: Margen de estabilizacion para asegurar que la cache de static files y Docker este caliente
ping -n 3 127.0.0.1 >nul 2>&1

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
echo   lazyJobFinder en ejecucion.
echo   - Se detiene ordenadamente al cerrar la terminal o si no hay conexiones al puerto.
echo   - Tambien puedes pulsar Ctrl+C para salir inmediatamente.
echo =====================================================================
echo.
:: -----------------------------------------------------------------------------
:: Supervisor de Ejecucion en Vivo: Mantiene la terminal abierta mientras este activo
:: -----------------------------------------------------------------------------
:SUPERVISOR_LOOP
docker compose logs -f --tail=30 lazyjobfinder

:: Si el stream de logs termino, comprobar si el contenedor sigue vivo
docker inspect -f "{{.State.Running}}" lazyjob_app 2>nul | findstr /i "true" >nul 2>&1
if !ERRORLEVEL! equ 0 (
    :: El contenedor sigue en ejecucion (reinicio por recarga interna o reconexion de logs)
    timeout /t 2 /nobreak >nul 2>&1
    goto :SUPERVISOR_LOOP
)

:: El contenedor se ha detenido (cierre desde el navegador o fin de sesion)
echo.
echo =====================================================================
echo   lazyJobFinder ha finalizado su sesion (cierre detectado).
echo   Deteniendo todos los servicios y liberando puertos...
echo =====================================================================
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
python packaging\build_release.py --skip-docker --skip-model
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

:EXIT
exit /b 0
