#!/usr/bin/env bash
set -euo pipefail
app_dir="$HOME/.local/share/enfermeria-san-giuseppe-moscati"
desktop_dir="$HOME/.local/share/applications"
icon_dir="$HOME/.local/share/icons/hicolor/256x256/apps"
rm -f "$desktop_dir/enfermeria-san-giuseppe-moscati.desktop"
rm -f "$desktop_dir/enfermeria-panel-rapido.desktop"
rm -f "$HOME/.config/autostart/enfermeria-panel-rapido.desktop"
rm -f "$HOME/.config/autostart/enfermeria-notificaciones.desktop"
rm -f "$icon_dir/enfermeria-san-giuseppe-moscati.png"
rm -rf "$app_dir"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$desktop_dir" || true
echo "La aplicación se quitó del menú. Los datos personales y copias de seguridad se conservaron."
