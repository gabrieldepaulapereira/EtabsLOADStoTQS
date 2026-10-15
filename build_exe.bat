@echo off
rem Gera dist\ExportarPierForces.exe. Na primeira vez precisa de internet (instala o PyInstaller
rem num ambiente separado, build\venv, sem mexer no Python da maquina).
cd /d "%~dp0"
if not exist "build\venv\Scripts\python.exe" (
    py -3 -m venv build\venv 2>nul || python -m venv build\venv || goto erro
)
"build\venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q comtypes pywebview pyinstaller || goto erro
"build\venv\Scripts\python.exe" build_exe.py || goto erro
pause
exit /b 0
:erro
echo.
echo FALHOU - veja as mensagens acima.
pause
exit /b 1
