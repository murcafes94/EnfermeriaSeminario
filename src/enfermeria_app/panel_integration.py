from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .config import DATA_DIR, PROJECT_ROOT


PANEL_AUTOSTART_NAME = "enfermeria-panel-rapido"
NOTIFIER_AUTOSTART_NAME = "enfermeria-notificaciones"


def application_command(mode: str | None = None) -> list[str]:
    if getattr(sys, "frozen", False):
        command = [sys.executable]
    else:
        command = [sys.executable, str(PROJECT_ROOT / "run.py")]
    if mode:
        command.append(f"--{mode}")
    return command


def launch_panel() -> bool:
    try:
        subprocess.Popen(application_command("panel"), close_fds=os.name != "nt")
        return True
    except OSError:
        return False


def launch_main_application() -> bool:
    try:
        subprocess.Popen(application_command("main") + ["--current-workspace"], close_fds=os.name != "nt")
        return True
    except OSError:
        return False


def _linux_autostart_path(name: str) -> Path:
    root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "autostart"
    return root / f"{name}.desktop"


def _windows_autostart_path(name: str) -> Path:
    appdata = Path(os.environ.get("APPDATA", Path.home()))
    return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / f"{name}.cmd"


def autostart_path(name: str) -> Path:
    return _windows_autostart_path(name) if os.name == "nt" else _linux_autostart_path(name)


def is_panel_autostart_enabled() -> bool:
    return autostart_path(PANEL_AUTOSTART_NAME).exists()


def set_panel_autostart(enabled: bool) -> None:
    target = autostart_path(PANEL_AUTOSTART_NAME)
    if not enabled:
        target.unlink(missing_ok=True)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    command = application_command("panel")
    if os.name == "nt":
        quoted = subprocess.list2cmdline(command)
        target.write_text(f"@echo off\r\nstart \"\" {quoted}\r\n", encoding="utf-8")
    else:
        quoted = " ".join(_desktop_quote(part) for part in command)
        target.write_text(
            "[Desktop Entry]\nType=Application\nVersion=1.0\n"
            "Name=Panel rápido de Enfermería\nComment=Resumen operativo de Enfermería\n"
            f"Exec={quoted}\nIcon=enfermeria-san-giuseppe-moscati\nTerminal=false\nX-GNOME-Autostart-enabled=true\n",
            encoding="utf-8",
        )


def is_notifier_autostart_enabled() -> bool:
    return autostart_path(NOTIFIER_AUTOSTART_NAME).exists()


def set_notifier_autostart(enabled: bool) -> None:
    if os.name == "nt":
        raise ValueError("Las notificaciones automáticas de esta versión son exclusivas de Linux.")
    target = autostart_path(NOTIFIER_AUTOSTART_NAME)
    if not enabled:
        target.unlink(missing_ok=True)
        stop_notifier()
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    command = " ".join(_desktop_quote(part) for part in application_command("notifier"))
    target.write_text(
        "[Desktop Entry]\nType=Application\nVersion=1.0\n"
        "Name=Alertas de Enfermería\nComment=Avisos de vencimientos, stock y préstamos\n"
        f"Exec={command}\nIcon=enfermeria-san-giuseppe-moscati\nTerminal=false\n"
        "X-GNOME-Autostart-enabled=true\nOnlyShowIn=X-Cinnamon;GNOME;\n",
        encoding="utf-8",
    )
    launch_notifier()


def launch_notifier() -> bool:
    try:
        subprocess.Popen(application_command("notifier"), close_fds=True)
        return True
    except OSError:
        return False


def stop_notifier() -> bool:
    pid_path = DATA_DIR / "notifier.lock"
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
        command_line = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ")
        if b"--notifier" not in command_line:
            return False
        os.kill(pid, 15)
        return True
    except (OSError, ValueError):
        return False


def launch_notifier_once() -> bool:
    try:
        subprocess.Popen(application_command("notifier-once"), close_fds=True)
        return True
    except OSError:
        return False


def _desktop_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$") + '"'
