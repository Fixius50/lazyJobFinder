@echo off
title lazyJobFinder - Deteniendo Servicios

cd /d "%~dp0"

echo =====================================================================
echo                lazyJobFinder - Deteniendo Servicios
echo =====================================================================
echo.

docker info >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] No se pudo conectar con el motor de Docker. Los contenedores no pueden ser administrados.
    pause
    exit /b 1
)

docker compose stop
if %ERRORLEVEL% equ 0 (
    echo [OK] Servicios detenidos ordenadamente. Los datos y modelos estan a salvo.
    exit /b 0
) else (
    echo [ERROR] Fallo al detener los servicios con docker compose stop.
    pause
    exit /b 1
)

echo.
timeout /t 2 /nobreak >nul
