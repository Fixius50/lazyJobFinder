@echo off
title lazyJobFinder - Deteniendo Servicios

cd /d "%~dp0"

echo =====================================================================
echo                lazyJobFinder - Deteniendo Servicios
echo =====================================================================
echo.

docker compose stop
if %ERRORLEVEL% equ 0 (
    echo [OK] Servicios detenidos ordenadamente. Los datos y modelos estan a salvo.
) else (
    echo [!] Advertencia al detener los servicios con docker compose stop.
)

echo.
timeout /t 2 /nobreak >nul
