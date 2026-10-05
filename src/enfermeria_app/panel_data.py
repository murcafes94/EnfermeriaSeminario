from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .config import DB_PATH, EXPIRY_WARNING_DAYS


@dataclass(frozen=True)
class PanelAlert:
    kind: str
    title: str
    detail: str
    location: str
    due: str
    state: str
    severity: int


@dataclass(frozen=True)
class PanelSnapshot:
    expired: int
    expiring: int
    low_stock: int
    active_loans: int
    overdue_loans: int
    quarantined: int
    alerts: tuple[PanelAlert, ...]
    updated_at: datetime

    @property
    def attention_required(self) -> int:
        return self.expired + self.overdue_loans + self.quarantined


def _connect_read_only(database_path: Path | str) -> sqlite3.Connection:
    path = Path(database_path).resolve()
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=2)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA busy_timeout=2000")
    return connection


def read_panel_snapshot(database_path: Path | str = DB_PATH, warning_days: int = EXPIRY_WARNING_DAYS) -> PanelSnapshot:
    """Read the operational summary without writing to or backing up the active database."""
    path = Path(database_path)
    now = datetime.now()
    if not path.exists():
        return PanelSnapshot(0, 0, 0, 0, 0, 0, (), now)

    today = date.today()
    alerts: list[PanelAlert] = []
    with _connect_read_only(path) as conn:
        counts = conn.execute(
            """SELECT
              (SELECT COUNT(*) FROM lots l JOIN items i ON i.id=l.item_id
                 WHERE i.archived=0 AND l.quantity>0 AND l.quarantined=0
                   AND l.expires_on IS NOT NULL AND date(l.expires_on)<date('now','localtime')) expired,
              (SELECT COUNT(*) FROM lots l JOIN items i ON i.id=l.item_id
                 WHERE i.archived=0 AND l.quantity>0 AND l.quarantined=0
                   AND l.expires_on IS NOT NULL AND date(l.expires_on) BETWEEN date('now','localtime')
                   AND date('now','localtime','+' || ? || ' days')) expiring,
              (SELECT COUNT(*) FROM items i WHERE i.archived=0 AND
                 i.stock-COALESCE((SELECT SUM(l.quantity) FROM lots l WHERE l.item_id=i.id AND l.quantity>0
                 AND (l.quarantined=1 OR (l.expires_on IS NOT NULL AND date(l.expires_on)<date('now','localtime')))),0)
                 <=i.minimum_stock) low_stock,
              (SELECT COUNT(*) FROM equipment_loans WHERE returned_at IS NULL) active_loans,
              (SELECT COUNT(*) FROM equipment_loans WHERE returned_at IS NULL AND expected_return IS NOT NULL
                 AND date(expected_return)<date('now','localtime')) overdue_loans,
              (SELECT COUNT(*) FROM lots WHERE quantity>0 AND quarantined=1) quarantined""",
            (warning_days,),
        ).fetchone()

        for row in conn.execute(
            """SELECT i.name,i.location,l.lot_number,l.expires_on,l.quantity,l.quarantined,l.quarantine_reason
               FROM lots l JOIN items i ON i.id=l.item_id
               WHERE i.archived=0 AND l.quantity>0 AND (
                 l.quarantined=1 OR (l.expires_on IS NOT NULL AND date(l.expires_on)
                 <=date('now','localtime','+' || ? || ' days')))
               ORDER BY l.quarantined DESC,date(l.expires_on),i.name COLLATE NOCASE LIMIT 20""",
            (warning_days,),
        ):
            if row["quarantined"]:
                state = "En cuarentena"
                severity = 3
                due = row["expires_on"] or "Sin fecha"
                detail = row["quarantine_reason"] or f"Lote {row['lot_number'] or 'sin número'}"
            else:
                days = (date.fromisoformat(row["expires_on"]) - today).days
                state = f"Vencido hace {abs(days)} días" if days < 0 else ("Vence hoy" if days == 0 else f"Vence en {days} días")
                severity = 3 if days < 0 else 2
                due = row["expires_on"]
                detail = f"Lote {row['lot_number'] or 'sin número'} · {row['quantity']} unidades"
            alerts.append(PanelAlert("Vencimiento", row["name"], detail, row["location"] or "Por asignar", due, state, severity))

        for row in conn.execute(
            """SELECT i.name,i.location,i.minimum_stock,
                 i.stock-COALESCE((SELECT SUM(l.quantity) FROM lots l WHERE l.item_id=i.id AND l.quantity>0
                   AND (l.quarantined=1 OR (l.expires_on IS NOT NULL AND date(l.expires_on)<date('now','localtime')))),0) usable
               FROM items i WHERE i.archived=0 AND
                 i.stock-COALESCE((SELECT SUM(l.quantity) FROM lots l WHERE l.item_id=i.id AND l.quantity>0
                   AND (l.quarantined=1 OR (l.expires_on IS NOT NULL AND date(l.expires_on)<date('now','localtime')))),0)
                 <=i.minimum_stock
               ORDER BY usable,i.name COLLATE NOCASE LIMIT 15"""
        ):
            usable = max(0, row["usable"])
            state = "Agotado" if usable == 0 else "Stock bajo"
            alerts.append(PanelAlert("Stock", row["name"], f"Disponibles {usable} · mínimo {row['minimum_stock']}", row["location"] or "Por asignar", "—", state, 3 if usable == 0 else 2))

        for row in conn.execute(
            """SELECT i.name,e.quantity,e.expected_return
               FROM equipment_loans e JOIN items i ON i.id=e.item_id
               WHERE e.returned_at IS NULL
               ORDER BY CASE WHEN e.expected_return IS NULL THEN 1 ELSE 0 END,date(e.expected_return),i.name COLLATE NOCASE LIMIT 15"""
        ):
            overdue = bool(row["expected_return"] and date.fromisoformat(row["expected_return"]) < today)
            alerts.append(PanelAlert("Equipo", row["name"], f"{row['quantity']} unidad(es) prestada(s)", "Equipos", row["expected_return"] or "Sin fecha", "Atrasado" if overdue else "Prestado", 3 if overdue else 1))

    alerts.sort(key=lambda item: (-item.severity, item.due == "—", item.due, item.title.casefold()))
    return PanelSnapshot(
        counts["expired"], counts["expiring"], counts["low_stock"], counts["active_loans"],
        counts["overdue_loans"], counts["quarantined"], tuple(alerts), now,
    )
