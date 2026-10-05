@echo off
setlocal
pushd "%~dp0.."
py -m venv .venv
if errorlevel 1 goto :failed
call .venv\Scripts\activate
python -m pip install --upgrade pip
if errorlevel 1 goto :failed
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :failed
python -m PyInstaller --noconfirm --clean --windowed --name EnfermeriaSeminario --icon "assets\app_icon.ico" --version-file "scripts\version_info.txt" --add-data "assets;assets" --collect-data reportlab --exclude-module numpy --paths src run.py
if errorlevel 1 goto :failed
echo Aplicacion generada en dist\EnfermeriaSeminario
if defined SIGNTOOL_CERT_PATH call :sign_file "dist\EnfermeriaSeminario\EnfermeriaSeminario.exe"
where ISCC >nul 2>nul
if %errorlevel%==0 (
  ISCC scripts\installer_windows.iss
  if errorlevel 1 goto :failed
  if defined SIGNTOOL_CERT_PATH call :sign_file "dist\installer\EnfermeriaSanGiuseppeMoscati-Setup-3.6.3.exe"
  echo Instalador generado en dist\installer
) else (
  echo Inno Setup no esta instalado; se genero la aplicacion portable.
)
popd
exit /b 0

:failed
echo No se completo la compilacion. Revisa el mensaje de error anterior.
popd
exit /b 1

:sign_file
where signtool >nul 2>nul
if errorlevel 1 (
  echo ADVERTENCIA: SIGNTOOL_CERT_PATH esta definido, pero signtool no esta disponible.
  exit /b 1
)
if defined SIGNTOOL_CERT_PASSWORD (
  signtool sign /fd SHA256 /td SHA256 /tr http://timestamp.digicert.com /f "%SIGNTOOL_CERT_PATH%" /p "%SIGNTOOL_CERT_PASSWORD%" %1
) else (
  signtool sign /fd SHA256 /td SHA256 /tr http://timestamp.digicert.com /f "%SIGNTOOL_CERT_PATH%" %1
)
if errorlevel 1 exit /b 1
echo Firma digital aplicada a %1
exit /b 0
