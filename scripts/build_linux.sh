#!/usr/bin/env bash
set -euo pipefail
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --clean --windowed --name EnfermeriaSeminario \
  --icon "assets/app_icon.png" --add-data "assets:assets" --collect-data reportlab --exclude-module numpy --paths src run.py
cp scripts/install_linux.sh "dist/EnfermeriaSeminario/Instalar_en_menu_de_aplicaciones.sh"
cp scripts/uninstall_linux.sh "dist/EnfermeriaSeminario/Desinstalar_del_menu.sh"
cp scripts/open_linux.sh "dist/EnfermeriaSeminario/Abrir_Enfermeria.sh"
cp assets/app_icon.png "dist/EnfermeriaSeminario/app_icon.png"
chmod +x "dist/EnfermeriaSeminario/EnfermeriaSeminario" \
  "dist/EnfermeriaSeminario/Instalar_en_menu_de_aplicaciones.sh" \
  "dist/EnfermeriaSeminario/Abrir_Enfermeria.sh" \
  "dist/EnfermeriaSeminario/Desinstalar_del_menu.sh"
echo "Aplicación generada en dist/EnfermeriaSeminario"
