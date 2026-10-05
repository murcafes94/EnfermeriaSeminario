from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .config import ASSETS_DIR, DATA_DIR, DB_PATH
from .panel_data import PanelSnapshot, read_panel_snapshot


STATE_PATH = DATA_DIR / "notifier_state.json"
LOCK_PATH = DATA_DIR / "notifier.lock"


def notification_signature(snapshot: PanelSnapshot) -> dict[str, object]:
    important = sorted(
        (alert.kind, alert.title, alert.state)
        for alert in snapshot.alerts
        if alert.severity >= 2
    )
    return {
        "expired": snapshot.expired,
        "expiring": snapshot.expiring,
        "low_stock": snapshot.low_stock,
        "overdue_loans": snapshot.overdue_loans,
        "quarantined": snapshot.quarantined,
        "important": important,
    }


def notification_text(snapshot: PanelSnapshot) -> tuple[str, str] | None:
    parts: list[str] = []
    if snapshot.expired: parts.append(f"{snapshot.expired} lote(s) vencido(s)")
    if snapshot.expiring: parts.append(f"{snapshot.expiring} próximo(s) a vencer")
    if snapshot.low_stock: parts.append(f"{snapshot.low_stock} producto(s) con stock bajo")
    if snapshot.overdue_loans: parts.append(f"{snapshot.overdue_loans} préstamo(s) atrasado(s)")
    if snapshot.quarantined: parts.append(f"{snapshot.quarantined} lote(s) en cuarentena")
    if not parts:
        return None
    return "Enfermería requiere atención", " · ".join(parts)


def _load_signature() -> dict[str, object] | None:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None


def _save_signature(signature: dict[str, object]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary = STATE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(signature, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    temporary.replace(STATE_PATH)
    try: STATE_PATH.chmod(0o600)
    except OSError: pass


def send_native_notification(title: str, message: str) -> bool:
    executable = shutil.which("notify-send")
    if not executable:
        return False
    command = [executable, "--app-name=Enfermería San Giuseppe Moscati", "--urgency=normal", "--expire-time=15000"]
    icon = ASSETS_DIR / "app_icon.png"
    if icon.exists(): command.extend(["--icon", str(icon)])
    command.extend([title, message])
    try:
        return subprocess.run(command, timeout=5, check=False).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def check_and_notify(force: bool = False) -> bool:
    snapshot = read_panel_snapshot(DB_PATH)
    signature = notification_signature(snapshot)
    previous = _load_signature()
    text = notification_text(snapshot)
    sent = bool(text and (force or signature != previous) and send_native_notification(*text))
    _save_signature(signature)
    return sent


def main(once: bool = False) -> int:
    if not sys.platform.startswith("linux"):
        return 0
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    lock_file = LOCK_PATH.open("a+")
    try:
        import fcntl
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (ImportError, OSError):
        lock_file.close()
        return 0
    lock_file.seek(0);lock_file.truncate();lock_file.write(str(os.getpid()));lock_file.flush()
    while True:
        try: check_and_notify()
        except Exception: pass
        if once: return 0
        time.sleep(10 * 60)
