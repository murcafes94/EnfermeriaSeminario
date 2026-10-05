from __future__ import annotations

import os
import shutil
import subprocess
import sys


def is_linux_desktop() -> bool:
    return sys.platform.startswith("linux")


def workspace_support_status() -> tuple[bool, str]:
    if not is_linux_desktop():
        return False, "Disponible únicamente en Linux."
    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session == "wayland":
        return False, "La sesión Wayland no permite mover ventanas de forma fiable."
    if not shutil.which("wmctrl"):
        return False, "Para usar el área de trabajo 2 instala una vez: sudo apt install wmctrl"
    return True, "La app puede abrirse automáticamente en el área de trabajo 2."


def move_window_to_workspace(window_id: int, workspace_index: int = 1) -> bool:
    """Move an X11 window to a zero-based desktop without changing application data."""
    supported, _ = workspace_support_status()
    if not supported:
        return False
    try:
        result = subprocess.run(
            ["wmctrl", "-ir", hex(int(window_id)), "-t", str(max(0, workspace_index))],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False
