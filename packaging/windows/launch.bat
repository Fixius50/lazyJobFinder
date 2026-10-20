@echo off
setlocal enabledelayedexpansion
title lazyJobFinder - Produccion Local

cd /d "%~dp0"

echo =====================================================================
echo                lazyJobFinder - Iniciando Aplicacion
echo          Inferencia IA Local y Privada (Sin Coste / Sin Nube)
echo =====================================================================
echo.

:: 1. Comprobar .env
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo [i] Archivo .env inicializado con exito.
    )
)

:: 2. Comprobar si Docker esta operativo
docker info >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [!] El motor de Docker Desktop no esta activo.
    set "DOCKER_EXE="
    if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" set "DOCKER_EXE=C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if not defined DOCKER_EXE if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" set "DOCKER_EXE=%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
    if not defined DOCKER_EXE if exist "%ProgramFiles(x86)%\Docker\Docker\Docker Desktop.exe" set "DOCKER_EXE=%ProgramFiles(x86)%\Docker\Docker\Docker Desktop.exe"
    if not defined DOCKER_EXE if exist "%LOCALAPPDATA%\Programs\Docker Desktop\Docker Desktop.exe" set "DOCKER_EXE=%LOCALAPPDATA%\Programs\Docker Desktop\Docker Desktop.exe"

    if defined DOCKER_EXE (
        echo [i] Iniciando Docker Desktop en segundo plano...
        start "" "!DOCKER_EXE!"
        echo [i] Esperando a que el motor Docker responda...
        set /a DOCKER_RETRY=0
        :WAIT_DOCKER
        timeout /t 3 /nobreak >nul
        docker info >nul 2>&1
        if !ERRORLEVEL! neq 0 (
            set /a DOCKER_RETRY+=1
            if !DOCKER_RETRY! lss 25 (
                echo     Esperando a Docker Desktop... [!DOCKER_RETRY!/25]
                goto :WAIT_DOCKER
            ) else (
                echo.
                echo [ERROR] Docker Desktop tardo demasiado en arrancar.
                echo         Por favor, abre Docker Desktop manualmente y espera a que el icono este en verde.
                echo.
                pause
                exit /b 1
            )
        ) else (
            echo [OK] Motor Docker conectado y operativo.
        )
    ) else (
        echo.
        echo [ERROR] Docker no esta en ejecucion y no se encontro la ruta de Docker Desktop.
        echo         Por favor, abre Docker Desktop manualmente antes de continuar.
        echo.
        pause
        exit /b 1
    )
)

:: 3. Si existe images.tar y las imagenes no estan cargadas, importarlas
docker image inspect lazyjobfinder:1.0.0 >nul 2>&1
if %ERRORLEVEL% neq 0 (
    if exist "images.tar" (
        echo [i] Importando imagenes de contenedores empaquetadas (lazyJobFinder y Ollama)...
        docker load -i "images.tar"
    )
)

:: 4. Arrancar los contenedores en segundo plano
echo.
echo --^> Levantando servicios en Docker...
docker compose up -d
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Fallo al iniciar los contenedores de Docker.
    pause
    exit /b 1
)

:: 5. Esperar a que el backend unificado responda en http://127.0.0.1:8000
echo.
echo --^> Conectando con la interfaz local...
set /a RETRY_COUNT=0
:WAIT_APP
timeout /t 2 /nobreak >nul
curl -s -f --connect-timeout 2 --max-time 3 http://127.0.0.1:8000/api/health >nul 2>&1
if %ERRORLEVEL% neq 0 (
    set /a RETRY_COUNT+=1
    if !RETRY_COUNT! lss 30 (
        echo     Iniciando motor de busqueda y API... [!RETRY_COUNT!/30]
        goto :WAIT_APP
    )
)

:: 6. Comprobar si el modelo de IA esta presente en Ollama; si no, descargarlo
docker exec lazyjob_ollama ollama list 2>nul | findstr /i "qwen2.5:3b-instruct" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo.
    echo [i] Descargando modelo de IA optimizado (qwen2.5:3b-instruct) en Ollama...
    docker exec lazyjob_ollama ollama pull qwen2.5:3b-instruct
)

echo.
echo =====================================================================
echo   [SISTEMA LISTO] lazyJobFinder esta operativo:
echo     - Panel de Control: http://localhost:8000
echo     - Motor Ollama:     http://localhost:11434
echo =====================================================================
echo.
echo Abriendo el panel en tu navegador...
start http://localhost:8000

echo.
echo Para detener la aplicacion, ejecuta stop.bat o pulsa cualquier tecla en esta ventana.
pause >nul
call "%~dp0stop.bat"
