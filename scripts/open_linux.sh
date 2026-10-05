#!/usr/bin/env bash
set -euo pipefail
app_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
log_dir="${XDG_STATE_HOME:-$HOME/.local/state}/EnfermeriaSeminario"
mkdir -p "$log_dir"
log_file="$log_dir/inicio-linux.log"
umask 077
set +e
"$app_root/EnfermeriaSeminario" --main --current-workspace "$@" >"$log_file" 2>&1
status=$?
set -e
if [[ $status -ne 0 ]]; then
  message="Enfermería no pudo abrirse (código $status). El detalle está en: $log_file"
  printf '%s\n' "$message" >&2
  if command -v zenity >/dev/null 2>&1; then
    zenity --error --title="Inicio de Enfermería" --text="$message" || true
  fi
fi
exit "$status"
