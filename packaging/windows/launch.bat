@echo off
setlocal enabledelayedexpansion
title lazyJobFinder - Produccion Local

cd /d "%~dp0"

echo =====================================================================
echo                lazyJobFinder - Iniciando Aplicacion
echo          Inferencia IA Local y Privada (Sin Coste / Sin Nube)
echo =====================================================================
echo.

:: 1. Comprobar .env y garantizar COMPOSE_PROJECT_NAME
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        set "RAND_SUFFIX=%RANDOM%%TIME:~6,2%"
        echo.>>".env"
        echo # Identificador unico de instalacion para aislamiento Docker Compose>>".env"
        echo COMPOSE_PROJECT_NAME=lazyjob_!RAND_SUFFIX!>>".env"
        echo [i] Archivo .env inicializado con proyecto unico (lazyjob_!RAND_SUFFIX!).
    ) else (
        echo [ERROR] No se encontro el archivo .env ni .env.example.
        pause
        exit /b 1
    )
) else (
    :: Verificar que .env contenga COMPOSE_PROJECT_NAME con valor no vacio
    set "CURRENT_CPN="
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        set "KEY=%%A"
        set "VAL=%%B"
        if /i "!KEY!"=="COMPOSE_PROJECT_NAME" (
            set "CURRENT_CPN=!VAL!"
        )
    )
    if defined CURRENT_CPN (
        set "CURRENT_CPN=!CURRENT_CPN:"=!"
        for /f "tokens=*" %%T in ("!CURRENT_CPN!") do set "CURRENT_CPN=%%T"
    )
    if not defined CURRENT_CPN (
        set "RAND_SUFFIX=%RANDOM%%TIME:~6,2%"
        echo.>>".env"
        echo # Identificador unico de instalacion para aislamiento Docker Compose>>".env"
        echo COMPOSE_PROJECT_NAME=lazyjob_!RAND_SUFFIX!>>".env"
        echo [i] Identificador COMPOSE_PROJECT_NAME asignado a .env (lazyjob_!RAND_SUFFIX!).
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

:: 3. Verificar imagenes en Docker (ollama/ollama:0.5.7 y lazyjobfinder)
set "NEED_LOAD=0"
docker image inspect ollama/ollama:0.5.7 >nul 2>&1
if %ERRORLEVEL% neq 0 (
    docker image inspect ollama/ollama:latest >nul 2>&1
    if !ERRORLEVEL! neq 0 set "NEED_LOAD=1"
)
docker image inspect lazyjobfinder:latest >nul 2>&1
if %ERRORLEVEL% neq 0 set "NEED_LOAD=1"

if "!NEED_LOAD!"=="1" (
    if exist "images.tar" (
        echo [i] Importando imagenes de contenedores empaquetadas (lazyJobFinder y Ollama)...
        docker load -i "images.tar"
        if !ERRORLEVEL! neq 0 (
            echo [ERROR] No se pudieron cargar las imagenes de images.tar.
            pause
            exit /b 1
        )
        echo [OK] Imagenes importadas con exito.
    ) else (
        echo [ERROR] No se encontraron las imagenes requeridas en Docker ni existe 'images.tar'.
        echo         Revisa la instalacion o ejecuta install.bat.
        pause
        exit /b 1
    )
)

:: 4. Arrancar los contenedores en segundo plano
echo.
echo --^> Levantando servicios en Docker...
docker compose up -d
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Fallo al iniciar los contenedores de Docker con Compose.
    pause
    exit /b 1
)

:: 5. Esperar a que el backend unificado responda en http://127.0.0.1:8000
echo.
echo --^> Conectando con la interfaz local...
set /a RETRY_COUNT=0
set "APP_ONLINE=0"

:WAIT_APP
timeout /t 2 /nobreak >nul
curl -s -f --connect-timeout 2 --max-time 3 http://127.0.0.1:8000/api/health >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "APP_ONLINE=1"
    goto :APP_READY
) else (
    set /a RETRY_COUNT+=1
    if !RETRY_COUNT! lss 30 (
        echo     Iniciando motor de busqueda y API... [!RETRY_COUNT!/30]
        goto :WAIT_APP
    )
)

:APP_READY
if "!APP_ONLINE!" neq "1" (
    echo.
    echo [ERROR] La API de lazyJobFinder no respondio tras 60 segundos de espera.
    echo         Los servicios no estan operativos. Revisa los logs con: docker compose logs
    pause
    exit /b 1
)

:: 6. Comprobar si el modelo de IA esta presente en Ollama; si no, descargarlo y verificar
echo --^> Verificando modelo de inferencia IA en Ollama...
docker compose exec -T ollama ollama list 2>nul | findstr /i "qwen2.5:3b-instruct" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo.
    echo [i] Descargando modelo de IA optimizado (qwen2.5:3b-instruct) en Ollama...
    docker compose exec -T ollama ollama pull qwen2.5:3b-instruct
    if !ERRORLEVEL! neq 0 (
        echo.
        echo [ERROR] Fallo critico durante la descarga del modelo en Ollama.
        echo         El sistema no puede operar sin el modelo IA.
        pause
        exit /b 1
    )
)

:: Doble comprobacion final del modelo
docker compose exec -T ollama ollama list 2>nul | findstr /i "qwen2.5:3b-instruct" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] El modelo de IA qwen2.5:3b-instruct no se encuentra disponible en Ollama.
    pause
    exit /b 1
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
