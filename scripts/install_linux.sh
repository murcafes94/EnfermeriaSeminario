#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "$script_dir/.." && pwd)"
if [[ -f "$script_dir/EnfermeriaSeminario" && -x "$script_dir/EnfermeriaSeminario" ]]; then
  source_dir="$script_dir"
elif [[ -f "$project_dir/dist/EnfermeriaSeminario/EnfermeriaSeminario" && -x "$project_dir/dist/EnfermeriaSeminario/EnfermeriaSeminario" ]]; then
  source_dir="$project_dir/dist/EnfermeriaSeminario"
else
  echo "No se encontró el ejecutable EnfermeriaSeminario junto al instalador ni en dist/."
  exit 1
fi

app_dir="$HOME/.local/share/enfermeria-san-giuseppe-moscati"
desktop_dir="$HOME/.local/share/applications"
icon_dir="$HOME/.local/share/icons/hicolor/256x256/apps"
desktop_file="$desktop_dir/enfermeria-san-giuseppe-moscati.desktop"
panel_desktop_file="$desktop_dir/enfermeria-panel-rapido.desktop"
icon_file="$icon_dir/enfermeria-san-giuseppe-moscati.png"
mkdir -p "$app_dir" "$desktop_dir" "$icon_dir"
cp -a "$source_dir/." "$app_dir/"

if [[ -f "$source_dir/app_icon.png" ]]; then
  cp "$source_dir/app_icon.png" "$icon_file"
elif [[ -f "$source_dir/_internal/assets/app_icon.png" ]]; then
  cp "$source_dir/_internal/assets/app_icon.png" "$icon_file"
elif [[ -f "$project_dir/assets/app_icon.png" ]]; then
  cp "$project_dir/assets/app_icon.png" "$icon_file"
else
  echo "No se encontró el icono de la aplicación."
  exit 1
fi

cat > "$desktop_file" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Enfermería San Giuseppe Moscati
GenericName=Enfermería
Comment=Inventario, expedientes de salud y controles de salud
Exec=$app_dir/EnfermeriaSeminario
Icon=enfermeria-san-giuseppe-moscati
Categories=Office;Utility;
Keywords=enfermería;medicamentos;inventario;salud;
Terminal=false
StartupNotify=true
StartupWMClass=enfermeria-san-giuseppe-moscati
EOF

cat > "$panel_desktop_file" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Panel rápido de Enfermería
GenericName=Resumen de Enfermería
Comment=Vencimientos, stock bajo y equipos prestados
Exec=$app_dir/EnfermeriaSeminario --panel
Icon=enfermeria-san-giuseppe-moscati
Categories=Office;Utility;
Keywords=enfermería;panel;vencimientos;stock;equipos;
Terminal=false
StartupNotify=true
EOF

chmod +x "$desktop_file" "$panel_desktop_file" "$app_dir/EnfermeriaSeminario"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$desktop_dir" || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
echo "Enfermería San Giuseppe Moscati ya aparece en el menú de aplicaciones."
command -v wmctrl >/dev/null 2>&1 || echo "Opcional: instala wmctrl para abrir automáticamente en el área de trabajo 2: sudo apt install wmctrl"
command -v notify-send >/dev/null 2>&1 || echo "Opcional: instala libnotify-bin para recibir alertas: sudo apt install libnotify-bin"
