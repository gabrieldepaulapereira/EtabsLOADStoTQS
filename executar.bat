@echo off
rem Duplo clique: abre a janela do exportador (use .venv\Scripts\python.exe se existir).
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    set "PY=python"
)
"%PY%" exportar_pier_forces.py %*
if errorlevel 1 pause
