from __future__ import annotations

import sqlite3
import os
import re
import unicodedata
import hashlib
import hmac
import json
import secrets
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Iterable

from .config import BLOOD_TYPES, DB_PATH, EXPIRY_WARNING_DAYS, FORMATION_STAGES, STOCK_MIN_DEFAULT
from .security import build_transfer_payload, decrypt_bytes, decrypt_file, encrypt_bytes, encrypt_file, extract_transfer_payload


NAME_PARTICLES = {"de", "del", "la", "las", "los", "y", "san", "santa"}
MEDICAL_ACRONYMS = {"IV", "IM", "SC", "SL", "NPH", "UI", "UCI", "ORS", "SR", "XR", "CR"}


def normalize_blood_type(value: Any) -> str:
    """Normalize common blood-group variants without inventing missing data."""
    raw = re.sub(r"\s+", "", "" if value is None else str(value)).upper().replace("−", "-").replace("–", "-")
    if raw in {"NOCONSTA", "NOCONOZCO", "DESCONOCIDO", "DESCONOCIDA", "N/A", "NA"}:
        return ""
    raw = raw.replace("POSITIVO", "+").replace("POSITIVE", "+").replace("POS", "+")
    raw = raw.replace("NEGATIVO", "-").replace("NEGATIVE", "-").replace("NEG", "-")
    raw = raw.replace("0", "O")
    return raw if raw in BLOOD_TYPES else raw


def normalize_formation_stage(value: Any) -> str:
    """Map recognizable formation-stage spellings to the app's canonical labels."""
    raw = re.sub(r"\s+", " ", "" if value is None else str(value)).strip()
    if not raw:
        return ""
    key = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode().lower()
    key = re.sub(r"[^a-z0-9]+", " ", key).strip()
    if "propedeut" in key:
        return FORMATION_STAGES[0]
    match = re.search(r"\b([1-4])\b", key)
    if match and "filosof" in key and match.group(1) in {"1", "2"}:
        return f"{match.group(1)}° Filosofía"
    if match and "teolog" in key:
        return f"{match.group(1)}° Teología"
    return raw


def sentence_case(value: Any) -> str:
    """Trim text and uppercase its first letter without damaging the rest."""
    text = "" if value is None else str(value).strip()
    for index, char in enumerate(text):
        if char.isalpha():
            return text[:index] + char.upper() + text[index + 1:]
    return text


def normalized_label(value: Any) -> str:
    """Normalize product-style labels, including text typed in upper/mixed case."""
    text = re.sub(r"\s+", " ", "" if value is None else str(value)).strip().lower()
    if not text:
        return ""
    text = sentence_case(text)
    def restore_acronym(match):
        word = match.group(0); upper = word.upper()
        return upper if upper in MEDICAL_ACRONYMS else word
    return re.sub(r"\b[^\W\d_]+\b", restore_acronym, text, flags=re.UNICODE)


def proper_name(value: Any) -> str:
    """Format personal and place names while keeping Spanish particles natural."""
    text = re.sub(r"\s+", " ", "" if value is None else str(value)).strip().lower()
    if not text:
        return ""
    words = text.split(" "); result = []
    for index, word in enumerate(words):
        parts = re.split(r"([-'])", word)
        rendered = "".join(part if part in {"-", "'"} else part[:1].upper() + part[1:] for part in parts)
        if index and word in NAME_PARTICLES: rendered = word
        result.append(rendered)
    return " ".join(result)


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS items (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL DEFAULT 'medicine',
 generic_name TEXT DEFAULT '', concentration TEXT DEFAULT '', presentation TEXT DEFAULT '',
 category TEXT DEFAULT '', location TEXT DEFAULT 'Por asignar', unit TEXT DEFAULT 'unidad',
 minimum_stock INTEGER NOT NULL DEFAULT 5 CHECK(minimum_stock >= 0),
 stock INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0), notes TEXT DEFAULT '',
 archived INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 usage TEXT DEFAULT '', source TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS lots (
 id INTEGER PRIMARY KEY, item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE RESTRICT,
 lot_number TEXT DEFAULT '', expires_on TEXT, quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0),
 quarantined INTEGER NOT NULL DEFAULT 0, quarantine_reason TEXT DEFAULT '', quarantined_at TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS seminarians (
 id INTEGER PRIMARY KEY, external_id TEXT UNIQUE, first_name TEXT NOT NULL, last_name TEXT NOT NULL,
 birth_date TEXT, birth_city TEXT DEFAULT '', birth_country TEXT DEFAULT '', nationality TEXT DEFAULT '',
 diocese TEXT DEFAULT '', parish TEXT DEFAULT '', address TEXT DEFAULT '', neighborhood TEXT DEFAULT '',
 city TEXT DEFAULT '', province TEXT DEFAULT '', country TEXT DEFAULT '', personal_phone TEXT DEFAULT '', email TEXT DEFAULT '',
 formation_year TEXT DEFAULT '', room TEXT DEFAULT '', blood_type TEXT DEFAULT '',
 allergies TEXT DEFAULT '', important_conditions TEXT DEFAULT '', permanent_medicines TEXT DEFAULT '',
 emergency_contact TEXT DEFAULT '', emergency_relation TEXT DEFAULT '', emergency_phone TEXT DEFAULT '',
 health_center TEXT DEFAULT '', insurance TEXT DEFAULT '', dietary_restrictions TEXT DEFAULT '',
 notes TEXT DEFAULT '', photo BLOB, consent INTEGER NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS movements (
 id INTEGER PRIMARY KEY, item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE RESTRICT,
 seminarian_id INTEGER REFERENCES seminarians(id) ON DELETE SET NULL,
 type TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity > 0), dose TEXT DEFAULT '',
 reason TEXT DEFAULT '', occurred_at TEXT NOT NULL, lot_id INTEGER REFERENCES lots(id) ON DELETE SET NULL,
 voided_at TEXT, void_reason TEXT DEFAULT '', reverses_movement_id INTEGER REFERENCES movements(id),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS equipment_loans (
 id INTEGER PRIMARY KEY, item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE RESTRICT,
 seminarian_id INTEGER REFERENCES seminarians(id) ON DELETE SET NULL,
 quantity INTEGER NOT NULL DEFAULT 1 CHECK(quantity > 0), lent_at TEXT NOT NULL,
 expected_return TEXT, returned_at TEXT, notes TEXT DEFAULT '', movement_id INTEGER REFERENCES movements(id),
 return_movement_id INTEGER REFERENCES movements(id)
);
CREATE TABLE IF NOT EXISTS movement_lot_allocations (
 id INTEGER PRIMARY KEY, movement_id INTEGER NOT NULL REFERENCES movements(id) ON DELETE RESTRICT,
 lot_id INTEGER NOT NULL REFERENCES lots(id) ON DELETE RESTRICT,
 quantity INTEGER NOT NULL CHECK(quantity > 0)
);
CREATE TABLE IF NOT EXISTS settings (
 key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS audit_log (
 id INTEGER PRIMARY KEY, occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 action TEXT NOT NULL, entity_type TEXT NOT NULL DEFAULT '', entity_id INTEGER,
 details TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS medical_controls (
 id INTEGER PRIMARY KEY,
 seminarian_id INTEGER NOT NULL REFERENCES seminarians(id) ON DELETE RESTRICT,
 measured_at TEXT NOT NULL,
 weight_kg REAL, height_cm REAL, bmi REAL,
 systolic INTEGER, diastolic INTEGER, pulse INTEGER,
 glucose_mg_dl REAL, glucose_context TEXT DEFAULT '',
 oxygen_saturation REAL, temperature_c REAL,
 notes TEXT DEFAULT '', referral TEXT DEFAULT '', recorded_by TEXT DEFAULT '',
 voided_at TEXT, void_reason TEXT DEFAULT '',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_items_name ON items(name);
CREATE INDEX IF NOT EXISTS idx_lots_expiry ON lots(expires_on);
CREATE INDEX IF NOT EXISTS idx_movements_date ON movements(occurred_at);
CREATE INDEX IF NOT EXISTS idx_seminarians_name ON seminarians(last_name, first_name);
CREATE INDEX IF NOT EXISTS idx_audit_date ON audit_log(occurred_at);
CREATE INDEX IF NOT EXISTS idx_medical_controls_sem_date ON medical_controls(seminarian_id, measured_at);
"""


class Database:
    def __init__(self, path: Path | str = DB_PATH):
        self.path = str(path)
        if Path(self.path).exists():
            self.backup()
        self.initialize()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self):
        parent = Path(self.path).parent
        parent.mkdir(parents=True, exist_ok=True)
        self._chmod(parent, 0o700)
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            self._migrate_legacy(conn)
            defaults = {
                "institution_name": "Seminario Mayor de Guayaquil",
                "clinic_name": "Enfermería San Giuseppe Moscati",
                "manager_name": "",
                "recovery_supervisor_name": "",
                "expiry_warning_days": str(EXPIRY_WARNING_DAYS),
            }
            for key, value in defaults.items():
                conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (key,value))
            conn.execute("UPDATE settings SET value=? WHERE key='clinic_name' AND value=?",
                         ("Enfermería San Giuseppe Moscati","Enfermería del Seminario"))
            conn.execute("UPDATE items SET location='CU' WHERE location='QR'")
        self._chmod(Path(self.path), 0o600)

    @staticmethod
    def _chmod(path: Path, mode: int):
        try:
            os.chmod(path, mode)
        except OSError:
            pass

    def backup(self) -> Path | None:
        source = Path(self.path)
        if not source.exists() or source.stat().st_size == 0:
            return None
        backup_dir = source.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        self._chmod(backup_dir, 0o700)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        target = backup_dir / f"enfermeria-{stamp}.db"
        src = sqlite3.connect(source)
        dst = sqlite3.connect(target)
        try:
            src.backup(dst)
        finally:
            dst.close(); src.close()
        self._chmod(target, 0o600)
        for old in sorted(backup_dir.glob("enfermeria-*.db"), reverse=True)[10:]:
            old.unlink(missing_ok=True)
        return target

    def create_backup(self, destination: Path | str | None = None) -> Path:
        source = Path(self.path)
        if destination is None:
            backup_dir = source.parent / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True); self._chmod(backup_dir,0o700)
            destination = backup_dir / f"manual-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        src = sqlite3.connect(source); dst = sqlite3.connect(target)
        try: src.backup(dst)
        finally: dst.close(); src.close()
        self._chmod(target,0o600)
        self.log_action("backup_created","database",None,target.name)
        return target

    def create_encrypted_backup(self, destination: Path | str, password: str) -> Path:
        """Create an AES-256-GCM backup without exposing a plaintext copy to the user."""
        destination=Path(destination)
        with TemporaryDirectory() as folder:
            snapshot=self.snapshot_to(Path(folder)/"enfermeria.db")
            target=encrypt_file(snapshot,destination,password,"backup")
        self.log_action("encrypted_backup_created","database",None,target.name)
        return target

    def restore_encrypted_backup(self, source: Path | str, password: str):
        with TemporaryDirectory() as folder:
            restored=decrypt_file(source,Path(folder)/"enfermeria.db",password,"backup")
            self.restore_backup(restored)
        self.log_action("encrypted_backup_restored","database",None,Path(source).name)

    def export_transfer_package(self, destination: Path | str, password: str, version: str) -> Path:
        destination=Path(destination)
        with TemporaryDirectory() as folder:
            snapshot=self.snapshot_to(Path(folder)/"enfermeria.db")
            settings={r["key"]:r["value"] for r in self.query("SELECT key,value FROM settings")}
            payload=build_transfer_payload(snapshot,settings,version)
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_bytes(encrypt_bytes(payload,password,"transfer"));self._chmod(destination,0o600)
        self.log_action("transfer_exported","database",None,destination.name)
        return destination

    def import_transfer_package(self, source: Path | str, password: str):
        payload,_=decrypt_bytes(Path(source).read_bytes(),password,"transfer")
        with TemporaryDirectory() as folder:
            database_path,manifest=extract_transfer_payload(payload,folder)
            self.restore_backup(database_path)
        self.log_action("transfer_imported","database",None,{"file":Path(source).name,"source_version":manifest.get("app_version","")})
        return manifest

    def snapshot_to(self, destination: Path | str) -> Path:
        target=Path(destination); target.parent.mkdir(parents=True,exist_ok=True)
        src=sqlite3.connect(self.path); dst=sqlite3.connect(target)
        try:src.backup(dst)
        finally:dst.close();src.close()
        return target

    def restore_backup(self, source: Path | str):
        source = Path(source)
        if not source.exists(): raise ValueError("La copia seleccionada no existe.")
        check = sqlite3.connect(source)
        try:
            result = check.execute("PRAGMA quick_check").fetchone()[0]
            tables = {r[0] for r in check.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally: check.close()
        if result != "ok" or not {"items","seminarians","movements"}.issubset(tables):
            raise ValueError("El archivo no es una copia válida de Enfermería.")
        self.backup()
        src = sqlite3.connect(source); dst = sqlite3.connect(self.path)
        try: src.backup(dst)
        finally: dst.close(); src.close()
        self.initialize()
        self.log_action("backup_restored","database",None,source.name)

    def list_backups(self) -> list[Path]:
        folder = Path(self.path).parent / "backups"
        return sorted(folder.glob("*.db"), key=lambda p:p.stat().st_mtime, reverse=True) if folder.exists() else []

    def purge_all_data(self, delete_local_backups: bool = True):
        """Permanently remove operational data while preserving settings and the access PIN."""
        with self.connect() as conn:
            conn.execute("PRAGMA secure_delete=ON")
            for table in ("movement_lot_allocations","equipment_loans","medical_controls","movements",
                          "lots","items","seminarians","audit_log"):
                conn.execute(f"DELETE FROM {table}")
            if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'").fetchone():
                conn.execute("DELETE FROM sqlite_sequence WHERE name IN (?,?,?,?,?,?,?,?)",
                             ("movement_lot_allocations","equipment_loans","medical_controls","movements",
                              "lots","items","seminarians","audit_log"))
        # Rebuild the file so deleted test data is not left in reusable SQLite pages.
        with self.connect() as conn: conn.execute("VACUUM")
        if delete_local_backups:
            for backup_file in self.list_backups(): backup_file.unlink(missing_ok=True)
        self._chmod(Path(self.path),0o600)

    @staticmethod
    def _columns(conn, table: str) -> set[str]:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}

    def _migrate_legacy(self, conn):
        migrations = {
            "lots": {"quarantined":"INTEGER NOT NULL DEFAULT 0",
                     "quarantine_reason":"TEXT DEFAULT ''","quarantined_at":"TEXT"},
            "seminarians": {
                "external_id": "TEXT", "emergency_relation": "TEXT DEFAULT ''",
                "insurance": "TEXT DEFAULT ''", "dietary_restrictions": "TEXT DEFAULT ''",
                "birth_city": "TEXT DEFAULT ''", "birth_country": "TEXT DEFAULT ''", "nationality": "TEXT DEFAULT ''",
                "diocese": "TEXT DEFAULT ''", "parish": "TEXT DEFAULT ''", "address": "TEXT DEFAULT ''",
                "neighborhood": "TEXT DEFAULT ''", "city": "TEXT DEFAULT ''", "province": "TEXT DEFAULT ''",
                "country": "TEXT DEFAULT ''", "personal_phone": "TEXT DEFAULT ''", "email": "TEXT DEFAULT ''",
                "photo": "BLOB",
                "consent": "INTEGER NOT NULL DEFAULT 0", "archived": "INTEGER NOT NULL DEFAULT 0",
                "created_at": "TEXT", "updated_at": "TEXT",
            },
            "movements": {"lot_id": "INTEGER", "created_at": "TEXT", "voided_at": "TEXT",
                          "void_reason": "TEXT DEFAULT ''", "reverses_movement_id": "INTEGER"},
            "equipment_loans": {"movement_id": "INTEGER", "return_movement_id": "INTEGER"},
        }
        for table, cols in migrations.items():
            current = self._columns(conn, table)
            for name, definition in cols.items():
                if name not in current:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(sql, tuple(params)).fetchall()

    def execute(self, sql: str, params: Iterable[Any] = ()) -> int:
        with self.connect() as conn:
            cur = conn.execute(sql, tuple(params))
            return int(cur.lastrowid or 0)

    @staticmethod
    def _audit(conn, action: str, entity_type: str = "", entity_id: int | None = None, details: Any = ""):
        if not isinstance(details,str): details=json.dumps(details,ensure_ascii=False,default=str)
        conn.execute("INSERT INTO audit_log(action,entity_type,entity_id,details) VALUES(?,?,?,?)",
                     (action,entity_type,entity_id,details[:2000]))

    def log_action(self, action: str, entity_type: str = "", entity_id: int | None = None, details: Any = ""):
        with self.connect() as conn: self._audit(conn,action,entity_type,entity_id,details)

    def get_setting(self, key: str, default: str = "") -> str:
        rows=self.query("SELECT value FROM settings WHERE key=?",(key,))
        return rows[0]["value"] if rows else default

    def set_setting(self, key: str, value: Any):
        with self.connect() as conn:
            conn.execute("""INSERT INTO settings(key,value,updated_at) VALUES(?,?,CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=CURRENT_TIMESTAMP""",(key,str(value)))
            self._audit(conn,"setting_updated","setting",None,key)

    def has_pin(self) -> bool:
        return bool(self.get_setting("admin_pin_hash"))

    @staticmethod
    def _secret_hash(secret: str) -> str:
        salt=secrets.token_bytes(16);digest=hashlib.pbkdf2_hmac("sha256",secret.encode(),salt,240000)
        return f"{salt.hex()}:{digest.hex()}"

    @staticmethod
    def _verify_secret(secret: str, stored: str) -> bool:
        try:salt_hex,digest_hex=stored.split(":",1)
        except ValueError:return False
        digest=hashlib.pbkdf2_hmac("sha256",secret.encode(),bytes.fromhex(salt_hex),240000)
        return hmac.compare_digest(digest.hex(),digest_hex)

    def set_pin(self, pin: str) -> str:
        if not re.fullmatch(r"\d{4,8}",pin): raise ValueError("El PIN debe tener entre 4 y 8 números.")
        self.set_setting("admin_pin_hash",self._secret_hash(pin))
        raw=secrets.token_hex(6).upper();recovery=f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"
        self.set_setting("admin_recovery_hash",self._secret_hash(recovery))
        self.log_action("pin_changed","security")
        return recovery

    def verify_pin(self, pin: str) -> bool:
        stored=self.get_setting("admin_pin_hash")
        if not stored:return True
        return self._verify_secret(pin,stored)

    def reset_pin_with_recovery(self, recovery_code: str, supervisor_name: str, new_pin: str) -> str:
        expected=proper_name(self.get_setting("recovery_supervisor_name"))
        if not expected:raise ValueError("Primero debe registrarse un responsable de recuperación en Configuración.")
        if proper_name(supervisor_name)!=expected:raise ValueError("El nombre del responsable no coincide con el registrado.")
        stored=self.get_setting("admin_recovery_hash")
        if not stored or not self._verify_secret(recovery_code.strip().upper(),stored):raise ValueError("El código institucional de recuperación no es válido.")
        new_code=self.set_pin(new_pin)
        self.log_action("pin_recovered","security",None,{"supervisor":expected})
        return new_code

    def remove_pin(self):
        self.set_setting("admin_pin_hash","");self.set_setting("admin_recovery_hash",""); self.log_action("pin_removed","security")

    def stats(self) -> dict[str, int]:
        with self.connect() as conn:
            return {
                "total": conn.execute("SELECT COUNT(*) FROM items WHERE archived=0").fetchone()[0],
                "low": conn.execute("""SELECT COUNT(*) FROM items i WHERE i.archived=0 AND
                    i.stock-COALESCE((SELECT SUM(l.quantity) FROM lots l WHERE l.item_id=i.id AND l.quantity>0
                    AND (l.quarantined=1 OR (l.expires_on IS NOT NULL AND date(l.expires_on)<date('now','localtime')))),0)<=i.minimum_stock""").fetchone()[0],
                "expiring": conn.execute("""SELECT COUNT(*) FROM lots l JOIN items i ON i.id=l.item_id
                    WHERE i.archived=0 AND l.quantity>0 AND l.quarantined=0 AND l.expires_on IS NOT NULL
                    AND date(l.expires_on) BETWEEN date('now','localtime')
                    AND date('now','localtime', '+' || ? || ' days')""", (EXPIRY_WARNING_DAYS,)).fetchone()[0],
                "expired": conn.execute("""SELECT COUNT(*) FROM lots l JOIN items i ON i.id=l.item_id
                    WHERE i.archived=0 AND l.quantity>0 AND l.quarantined=0 AND l.expires_on IS NOT NULL
                    AND date(l.expires_on)<date('now','localtime')""").fetchone()[0],
                "seminarians": conn.execute("SELECT COUNT(*) FROM seminarians WHERE archived=0").fetchone()[0],
                "loans": conn.execute("SELECT COUNT(*) FROM equipment_loans WHERE returned_at IS NULL").fetchone()[0],
                "quarantined": conn.execute("SELECT COUNT(*) FROM lots WHERE quantity>0 AND quarantined=1").fetchone()[0],
                "no_expiry": conn.execute("""SELECT COUNT(*) FROM items i WHERE i.archived=0
                    AND i.type IN ('medicine','supply') AND i.stock>0 AND (
                      EXISTS(SELECT 1 FROM lots l WHERE l.item_id=i.id AND l.quantity>0 AND l.expires_on IS NULL)
                      OR i.stock>COALESCE((SELECT SUM(l.quantity) FROM lots l WHERE l.item_id=i.id),0)
                    )""").fetchone()[0],
            }

    def inventory(self, search: str = "", include_archived: bool = False):
        where = "1=1" if include_archived else "i.archived=0"
        params: list[Any] = []
        if search:
            where += " AND (i.name LIKE ? OR i.generic_name LIKE ? OR i.category LIKE ? OR i.location LIKE ? OR EXISTS(SELECT 1 FROM lots q WHERE q.item_id=i.id AND q.lot_number LIKE ?))"
            params.extend([f"%{search}%"] * 5)
        return self.query(f"""SELECT i.*, MIN(CASE WHEN l.quantity>0 AND l.quarantined=0 THEN l.expires_on END) earliest_expiry,
            COUNT(CASE WHEN l.quantity>0 THEN 1 END) active_lots,
            COALESCE(SUM(CASE WHEN l.quantity>0 AND l.quarantined=1 THEN l.quantity ELSE 0 END),0) quarantined_stock
            FROM items i LEFT JOIN lots l ON l.item_id=i.id WHERE {where}
            GROUP BY i.id ORDER BY i.name COLLATE NOCASE""", params)

    def save_item(self, data: dict[str, Any], item_id: int | None = None) -> int:
        values = self._item_values(data)
        with self.connect() as conn:
            if item_id:
                conn.execute("""UPDATE items SET name=?,type=?,generic_name=?,concentration=?,presentation=?,
                    category=?,location=?,unit=?,minimum_stock=?,usage=?,source=?,notes=? WHERE id=?""", values + (item_id,))
                self._audit(conn,"item_updated","item",item_id,values[0]); return item_id
            cur = conn.execute("""INSERT INTO items(name,type,generic_name,concentration,presentation,category,
                location,unit,minimum_stock,usage,source,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", values)
            self._audit(conn,"item_created","item",cur.lastrowid,values[0]); return cur.lastrowid

    def _item_values(self, data: dict[str, Any]) -> tuple[Any, ...]:
        raw_minimum = data.get("minimum_stock")
        minimum = max(0, int(STOCK_MIN_DEFAULT if raw_minimum in (None, "") else raw_minimum))
        return (
            normalized_label(data["name"]), data.get("type", "medicine"), normalized_label(data.get("generic_name", "")),
            self._text(data.get("concentration", "")), sentence_case(data.get("presentation", "")),
            sentence_case(data.get("category", "")), data.get("location", "Por asignar"),
            sentence_case(data.get("unit", "unidad")), minimum, sentence_case(data.get("usage", "")),
            self._text(data.get("source", "")), sentence_case(data.get("notes", "")),
        )

    def import_inventory_batch(self, records: list[dict[str, Any]]) -> dict[str, int]:
        """Importa productos y todos sus lotes en una sola transacción.

        Los productos ya existentes solo actualizan sus datos descriptivos para que
        volver a importar el mismo archivo nunca duplique el stock.
        """
        result={"created":0,"updated":0,"stock_entries":0}
        now=datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            for record in records:
                values=self._item_values(record["data"])
                existing=conn.execute("SELECT id FROM items WHERE lower(name)=lower(?) AND archived=0",(values[0],)).fetchone()
                if existing:
                    item_id=existing["id"]
                    conn.execute("""UPDATE items SET name=?,type=?,generic_name=?,concentration=?,presentation=?,
                        category=?,location=?,unit=?,minimum_stock=?,usage=?,source=?,notes=? WHERE id=?""",values+(item_id,))
                    self._audit(conn,"item_updated","item",item_id,values[0]);result["updated"]+=1
                    continue
                cur=conn.execute("""INSERT INTO items(name,type,generic_name,concentration,presentation,category,
                    location,unit,minimum_stock,usage,source,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",values)
                item_id=cur.lastrowid;self._audit(conn,"item_created","item",item_id,values[0]);result["created"]+=1
                for stock in record.get("stocks",[]):
                    quantity=max(0,int(stock.get("quantity") or 0))
                    if not quantity:continue
                    lot_number=self._text(stock.get("lot_number"));expires_on=stock.get("expires_on") or None;lot_id=None
                    if lot_number or expires_on:
                        lot_cur=conn.execute("INSERT INTO lots(item_id,lot_number,expires_on,quantity) VALUES(?,?,?,?)",
                                             (item_id,lot_number,expires_on,quantity));lot_id=lot_cur.lastrowid
                    conn.execute("UPDATE items SET stock=stock+? WHERE id=?",(quantity,item_id))
                    movement=conn.execute("""INSERT INTO movements(item_id,type,quantity,reason,occurred_at,lot_id)
                        VALUES(?,?,?,?,?,?)""",(item_id,"entry",quantity,"Importación inicial",now,lot_id))
                    self._audit(conn,"stock_added","item",item_id,{"quantity":quantity,"movement_id":movement.lastrowid,"lot":lot_number})
                    result["stock_entries"]+=1
        return result

    def create_item_with_initial_stock(self, data: dict[str, Any], quantity: int = 0,
                                       lot_number: str = "", expires_on: str | None = None,
                                       reason: str = "Inventario inicial") -> int:
        """Crea el producto y su existencia inicial en una sola transacción."""
        quantity=max(0,int(quantity or 0));raw_minimum=data.get("minimum_stock")
        minimum=max(0,int(STOCK_MIN_DEFAULT if raw_minimum in (None,"") else raw_minimum))
        values=(normalized_label(data["name"]),data.get("type","medicine"),normalized_label(data.get("generic_name","")),
                self._text(data.get("concentration","")),sentence_case(data.get("presentation","")),
                sentence_case(data.get("category","")),data.get("location","Por asignar"),
                sentence_case(data.get("unit","unidad")),minimum,sentence_case(data.get("usage","")),
                self._text(data.get("source","")),sentence_case(data.get("notes","")))
        now=datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            cur=conn.execute("""INSERT INTO items(name,type,generic_name,concentration,presentation,category,
                location,unit,minimum_stock,usage,source,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",values)
            item_id=cur.lastrowid;self._audit(conn,"item_created","item",item_id,values[0])
            if quantity:
                lot_id=None
                if lot_number.strip() or expires_on:
                    lot_cur=conn.execute("INSERT INTO lots(item_id,lot_number,expires_on,quantity) VALUES(?,?,?,?)",
                                         (item_id,self._text(lot_number),expires_on,quantity));lot_id=lot_cur.lastrowid
                conn.execute("UPDATE items SET stock=? WHERE id=?",(quantity,item_id))
                mov=conn.execute("""INSERT INTO movements(item_id,type,quantity,reason,occurred_at,lot_id)
                    VALUES(?,?,?,?,?,?)""",(item_id,"entry",quantity,sentence_case(reason) or "Inventario inicial",now,lot_id))
                self._audit(conn,"initial_stock_added","item",item_id,{"quantity":quantity,"movement_id":mov.lastrowid,"lot":lot_number})
            return item_id

    @staticmethod
    def _number_or_none(value):
        return None if value in (None, "", 0, 0.0) else value

    def save_medical_control(self, seminarian_id: int, data: dict[str, Any], control_id: int | None = None) -> int:
        weight=self._number_or_none(data.get("weight_kg"));height=self._number_or_none(data.get("height_cm"))
        bmi=round(float(weight)/((float(height)/100)**2),2) if weight and height else None
        values=(seminarian_id,data["measured_at"],weight,height,bmi,
                self._number_or_none(data.get("systolic")),self._number_or_none(data.get("diastolic")),
                self._number_or_none(data.get("pulse")),self._number_or_none(data.get("glucose_mg_dl")),
                self._text(data.get("glucose_context")),self._number_or_none(data.get("oxygen_saturation")),
                self._number_or_none(data.get("temperature_c")),sentence_case(data.get("notes")),
                sentence_case(data.get("referral")),proper_name(data.get("recorded_by")))
        with self.connect() as conn:
            if not conn.execute("SELECT 1 FROM seminarians WHERE id=? AND archived=0",(seminarian_id,)).fetchone():
                raise ValueError("La ficha del seminarista no existe o está archivada.")
            if control_id:
                if not conn.execute("SELECT 1 FROM medical_controls WHERE id=? AND seminarian_id=? AND voided_at IS NULL",(control_id,seminarian_id)).fetchone():
                    raise ValueError("El control de salud no existe, no corresponde al expediente o está anulado.")
                conn.execute("""UPDATE medical_controls SET seminarian_id=?,measured_at=?,weight_kg=?,height_cm=?,bmi=?,
                    systolic=?,diastolic=?,pulse=?,glucose_mg_dl=?,glucose_context=?,oxygen_saturation=?,temperature_c=?,
                    notes=?,referral=?,recorded_by=?,updated_at=CURRENT_TIMESTAMP WHERE id=?""",values+(control_id,))
                self._audit(conn,"medical_control_updated","medical_control",control_id,{"seminarian_id":seminarian_id})
                return control_id
            cur=conn.execute("""INSERT INTO medical_controls(seminarian_id,measured_at,weight_kg,height_cm,bmi,
                systolic,diastolic,pulse,glucose_mg_dl,glucose_context,oxygen_saturation,temperature_c,
                notes,referral,recorded_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",values)
            self._audit(conn,"medical_control_created","medical_control",cur.lastrowid,{"seminarian_id":seminarian_id})
            return cur.lastrowid

    def void_medical_control(self, control_id: int, reason: str):
        reason=sentence_case(reason)
        if not reason:raise ValueError("Escribe el motivo de la anulación.")
        with self.connect() as conn:
            row=conn.execute("SELECT voided_at FROM medical_controls WHERE id=?",(control_id,)).fetchone()
            if not row or row["voided_at"]:raise ValueError("El control no existe o ya está anulado.")
            conn.execute("UPDATE medical_controls SET voided_at=?,void_reason=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                         (datetime.now().isoformat(timespec="seconds"),reason,control_id))
            self._audit(conn,"medical_control_voided","medical_control",control_id,reason)

    def add_stock(self, item_id: int, quantity: int, lot_number: str = "", expires_on: str | None = None, reason: str = "Entrada"):
        if quantity <= 0:
            raise ValueError("La cantidad debe ser mayor que cero.")
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            lot_id = None
            if lot_number or expires_on:
                cur = conn.execute("INSERT INTO lots(item_id,lot_number,expires_on,quantity) VALUES(?,?,?,?)",
                                   (item_id, self._text(lot_number), expires_on, quantity))
                lot_id = cur.lastrowid
            conn.execute("UPDATE items SET stock=stock+? WHERE id=?", (quantity, item_id))
            cur=conn.execute("""INSERT INTO movements(item_id,type,quantity,reason,occurred_at,lot_id)
                VALUES(?,?,?,?,?,?)""", (item_id, "entry", quantity, sentence_case(reason), now, lot_id))
            self._audit(conn,"stock_added","item",item_id,{"quantity":quantity,"movement_id":cur.lastrowid,"lot":lot_number})

    def record_output(self, item_id: int, quantity: int, movement_type: str, seminarian_id: int | None,
                      dose: str = "", reason: str = ""):
        if quantity <= 0:
            raise ValueError("La cantidad debe ser mayor que cero.")
        if movement_type in {"delivery", "administered", "loan"} and not seminarian_id:
            raise ValueError("Selecciona al seminarista.")
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            return self._record_output(conn, item_id, quantity, movement_type, seminarian_id, dose, reason, now)

    def _record_output(self, conn, item_id: int, quantity: int, movement_type: str,
                       seminarian_id: int | None, dose: str, reason: str, occurred_at: str) -> int:
        item = conn.execute("SELECT stock FROM items WHERE id=? AND archived=0", (item_id,)).fetchone()
        if not item:
            raise ValueError("El producto no existe o está archivado.")
        stock = int(item["stock"])
        blocked = conn.execute("""SELECT COALESCE(SUM(quantity),0) FROM lots
            WHERE item_id=? AND quantity>0 AND (quarantined=1 OR
            (expires_on IS NOT NULL AND date(expires_on)<date('now','localtime')))""", (item_id,)).fetchone()[0]
        available = stock if movement_type == "discard" else stock - int(blocked or 0)
        if available < quantity:
            if movement_type == "discard":
                raise ValueError(f"Stock insuficiente. Disponible: {available}.")
            raise ValueError(f"Disponible utilizable sin contar lotes vencidos o en cuarentena: {max(0, available)}.")
        cur = conn.execute("""INSERT INTO movements(item_id,seminarian_id,type,quantity,dose,reason,occurred_at)
            VALUES(?,?,?,?,?,?,?)""", (item_id, seminarian_id, movement_type, quantity, sentence_case(dose), sentence_case(reason), occurred_at))
        movement_id = cur.lastrowid
        params: list[Any] = [item_id]
        valid_filter = ""
        if movement_type != "discard":
            valid_filter = " AND quarantined=0 AND (expires_on IS NULL OR date(expires_on)>=date('now','localtime'))"
        lots = conn.execute(f"""SELECT id,quantity FROM lots WHERE item_id=? AND quantity>0 {valid_filter}
            ORDER BY expires_on IS NULL, date(expires_on), id""", params).fetchall()
        remaining = quantity
        for lot in lots:
            used = min(remaining, lot["quantity"])
            if used:
                conn.execute("UPDATE lots SET quantity=quantity-? WHERE id=?", (used, lot["id"]))
                conn.execute("INSERT INTO movement_lot_allocations(movement_id,lot_id,quantity) VALUES(?,?,?)",
                             (movement_id, lot["id"], used))
                remaining -= used
            if remaining == 0:
                break
        conn.execute("UPDATE items SET stock=stock-? WHERE id=?", (quantity, item_id))
        self._audit(conn,"stock_output","item",item_id,{"quantity":quantity,"type":movement_type,"movement_id":movement_id,"seminarian_id":seminarian_id})
        return movement_id

    def void_movement(self, movement_id: int, reason: str):
        reason = sentence_case(reason)
        if not reason:
            raise ValueError("Escribe el motivo de la anulación.")
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            mov = conn.execute("SELECT * FROM movements WHERE id=?", (movement_id,)).fetchone()
            if not mov or mov["voided_at"]:
                raise ValueError("El movimiento no existe o ya fue anulado.")
            if mov["type"] == "reversal":
                raise ValueError("Un asiento de reversión no puede anularse.")
            if conn.execute("SELECT 1 FROM equipment_loans WHERE movement_id=? OR return_movement_id=?", (movement_id,movement_id)).fetchone():
                raise ValueError("Este movimiento pertenece a un préstamo. Gestiona la devolución desde Equipos.")
            allocations = conn.execute("SELECT lot_id,quantity FROM movement_lot_allocations WHERE movement_id=?", (movement_id,)).fetchall()
            if mov["type"] in {"entry", "return"}:
                current = conn.execute("SELECT stock FROM items WHERE id=?", (mov["item_id"],)).fetchone()[0]
                if current < mov["quantity"]:
                    raise ValueError("No puede anularse: parte de esa entrada ya fue utilizada.")
                if mov["lot_id"]:
                    lot_qty = conn.execute("SELECT quantity FROM lots WHERE id=?", (mov["lot_id"],)).fetchone()
                    if not lot_qty or lot_qty[0] < mov["quantity"]:
                        raise ValueError("No puede anularse: el lote de esa entrada ya fue utilizado.")
                    conn.execute("UPDATE lots SET quantity=quantity-? WHERE id=?", (mov["quantity"], mov["lot_id"]))
                for allocation in allocations:
                    lot_qty = conn.execute("SELECT quantity FROM lots WHERE id=?", (allocation["lot_id"],)).fetchone()
                    if not lot_qty or lot_qty[0] < allocation["quantity"]:
                        raise ValueError("No puede anularse: las unidades restauradas ya fueron utilizadas.")
                    conn.execute("UPDATE lots SET quantity=quantity-? WHERE id=?", (allocation["quantity"], allocation["lot_id"]))
                conn.execute("UPDATE items SET stock=stock-? WHERE id=?", (mov["quantity"], mov["item_id"]))
            else:
                conn.execute("UPDATE items SET stock=stock+? WHERE id=?", (mov["quantity"], mov["item_id"]))
                for allocation in allocations:
                    conn.execute("UPDATE lots SET quantity=quantity+? WHERE id=?", (allocation["quantity"], allocation["lot_id"]))
            conn.execute("UPDATE movements SET voided_at=?,void_reason=? WHERE id=?", (now, reason, movement_id))
            conn.execute("""INSERT INTO movements(item_id,seminarian_id,type,quantity,dose,reason,occurred_at,reverses_movement_id)
                VALUES(?,?,?,?,?,?,?,?)""", (mov["item_id"], mov["seminarian_id"], "reversal", mov["quantity"], mov["dose"],
                                               f"Anulación #{movement_id}: {reason}", now, movement_id))
            self._audit(conn,"movement_voided","movement",movement_id,reason)

    def archive_item(self, item_id: int):
        with self.connect() as conn:
            conn.execute("UPDATE items SET archived=1 WHERE id=?",(item_id,)); self._audit(conn,"item_archived","item",item_id)

    def restore_item(self, item_id: int):
        with self.connect() as conn:
            conn.execute("UPDATE items SET archived=0 WHERE id=?",(item_id,));self._audit(conn,"item_restored","item",item_id)

    def update_lot(self, lot_id: int, lot_number: str, expires_on: str | None):
        with self.connect() as conn:
            row=conn.execute("SELECT item_id FROM lots WHERE id=?",(lot_id,)).fetchone()
            if not row:raise ValueError("El lote no existe.")
            conn.execute("UPDATE lots SET lot_number=?,expires_on=? WHERE id=?",(lot_number.strip(),expires_on,lot_id))
            self._audit(conn,"lot_updated","lot",lot_id,{"item_id":row["item_id"],"expires_on":expires_on})

    def set_lot_quarantine(self, lot_id: int, quarantined: bool, reason: str = ""):
        reason=sentence_case(reason)
        if quarantined and not reason:raise ValueError("Escribe el motivo de la cuarentena.")
        with self.connect() as conn:
            lot=conn.execute("SELECT item_id,quantity FROM lots WHERE id=?",(lot_id,)).fetchone()
            if not lot:raise ValueError("El lote no existe.")
            if lot["quantity"]<=0:raise ValueError("El lote no tiene existencias.")
            conn.execute("UPDATE lots SET quarantined=?,quarantine_reason=?,quarantined_at=? WHERE id=?",
                         (1 if quarantined else 0,reason if quarantined else "",datetime.now().isoformat(timespec="seconds") if quarantined else None,lot_id))
            self._audit(conn,"lot_quarantined" if quarantined else "lot_released","lot",lot_id,
                        {"item_id":lot["item_id"],"quantity":lot["quantity"],"reason":reason})

    def discard_lot(self, lot_id: int, reason: str):
        reason=reason.strip()
        if not reason:raise ValueError("Escribe el motivo del retiro.")
        now=datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            lot=conn.execute("SELECT item_id,quantity FROM lots WHERE id=?",(lot_id,)).fetchone()
            if not lot or lot["quantity"]<=0:raise ValueError("El lote no existe o ya no tiene unidades.")
            stock=conn.execute("SELECT stock FROM items WHERE id=?",(lot["item_id"],)).fetchone()[0]
            if stock<lot["quantity"]:raise ValueError("El stock total no coincide con el lote. Revisa la base antes de continuar.")
            cur=conn.execute("INSERT INTO movements(item_id,type,quantity,reason,occurred_at) VALUES(?,?,?,?,?)",
                             (lot["item_id"],"discard",lot["quantity"],reason,now))
            conn.execute("INSERT INTO movement_lot_allocations(movement_id,lot_id,quantity) VALUES(?,?,?)",(cur.lastrowid,lot_id,lot["quantity"]))
            conn.execute("UPDATE lots SET quantity=0 WHERE id=?",(lot_id,));conn.execute("UPDATE items SET stock=stock-? WHERE id=?",(lot["quantity"],lot["item_id"]))
            self._audit(conn,"lot_discarded","lot",lot_id,{"quantity":lot["quantity"],"reason":reason})

    def discard_expired_lots(self, item_id: int, reason: str = "Producto vencido") -> dict[str, int]:
        """Retira todos los lotes vencidos de un producto sin borrar su historial."""
        reason=sentence_case(reason)
        if not reason:raise ValueError("Escribe el motivo del retiro.")
        now=datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            lots=conn.execute("""SELECT id,quantity FROM lots WHERE item_id=? AND quantity>0 AND expires_on IS NOT NULL
                AND date(expires_on)<date('now','localtime') ORDER BY expires_on,id""",(item_id,)).fetchall()
            if not lots:raise ValueError("El producto no tiene lotes vencidos con existencias.")
            total=sum(row["quantity"] for row in lots);stock=conn.execute("SELECT stock FROM items WHERE id=?",(item_id,)).fetchone()
            if not stock or stock[0]<total:raise ValueError("El stock total no coincide con los lotes vencidos. Revisa la base antes de continuar.")
            for lot in lots:
                movement=conn.execute("INSERT INTO movements(item_id,type,quantity,reason,occurred_at) VALUES(?,?,?,?,?)",
                                      (item_id,"discard",lot["quantity"],reason,now))
                conn.execute("INSERT INTO movement_lot_allocations(movement_id,lot_id,quantity) VALUES(?,?,?)",(movement.lastrowid,lot["id"],lot["quantity"]))
                conn.execute("UPDATE lots SET quantity=0 WHERE id=?",(lot["id"],))
                self._audit(conn,"lot_discarded","lot",lot["id"],{"quantity":lot["quantity"],"reason":reason})
            conn.execute("UPDATE items SET stock=stock-? WHERE id=?",(total,item_id))
            return {"lots":len(lots),"quantity":total}

    def safe_delete_item(self, item_id: int):
        with self.connect() as conn:
            item = conn.execute("SELECT stock FROM items WHERE id=?", (item_id,)).fetchone()
            if not item:
                return
            history = conn.execute("SELECT COUNT(*) FROM movements WHERE item_id=?", (item_id,)).fetchone()[0]
            loans = conn.execute("SELECT COUNT(*) FROM equipment_loans WHERE item_id=?", (item_id,)).fetchone()[0]
            if item[0] > 0 or history or loans:
                raise ValueError("No puede borrarse porque tiene existencias o historial. Archívalo para conservar la trazabilidad.")
            conn.execute("DELETE FROM lots WHERE item_id=?", (item_id,))
            conn.execute("DELETE FROM items WHERE id=?", (item_id,))
            self._audit(conn,"item_deleted","item",item_id)

    @staticmethod
    def _text(value: Any) -> str:
        return "" if value is None else str(value).strip()

    @staticmethod
    def _code(value: Any) -> str:
        return re.sub(r"\s+","", "" if value is None else str(value)).strip().upper()

    @staticmethod
    def _seminarian_fields() -> list[str]:
        return ["external_id","first_name","last_name","birth_date","birth_city","birth_country","nationality",
                "diocese","parish","address","neighborhood","city","province","country","personal_phone","email",
                "formation_year","room","blood_type",
                "allergies","important_conditions","permanent_medicines","emergency_contact","emergency_relation",
                "emergency_phone","health_center","insurance","dietary_restrictions","notes","consent"]

    @classmethod
    def _normalize_seminarian_data(cls, data: dict[str, Any]) -> dict[str, Any]:
        normalized = {field: cls._text(data.get(field)) for field in cls._seminarian_fields()}
        proper_fields = {"first_name","last_name","birth_city","birth_country","nationality","diocese","parish",
                         "neighborhood","city","province","country","emergency_contact","emergency_relation",
                         "health_center","insurance"}
        sentence_fields = {"address","allergies","important_conditions","permanent_medicines",
                           "dietary_restrictions","notes"}
        for field in proper_fields: normalized[field] = proper_name(normalized[field])
        for field in sentence_fields: normalized[field] = sentence_case(normalized[field])
        normalized["formation_year"] = normalize_formation_stage(normalized["formation_year"])
        normalized["blood_type"] = normalize_blood_type(normalized["blood_type"])
        normalized["external_id"] = normalized["external_id"] or None
        normalized["birth_date"] = normalized["birth_date"] or None
        # Email, phones, dates and identifiers are deliberately not capitalized.
        normalized["consent"] = 1 if data.get("consent") in (1,True,"1","Sí","Si","si","sí") else 0
        return normalized

    def possible_seminarian_duplicates(self, data: dict[str, Any]):
        normalized = self._normalize_seminarian_data(data)
        external_id = normalized["external_id"]
        first = normalized["first_name"]; last = normalized["last_name"]
        birth = normalized["birth_date"]
        if external_id:
            return self.query("SELECT id,first_name,last_name,birth_date,external_id FROM seminarians WHERE external_id=?", (external_id,))
        if birth:
            return self.query("""SELECT id,first_name,last_name,birth_date,external_id FROM seminarians
                WHERE lower(first_name)=lower(?) AND lower(last_name)=lower(?) AND birth_date=?""", (first,last,birth))
        return self.query("""SELECT id,first_name,last_name,birth_date,external_id FROM seminarians
            WHERE lower(first_name)=lower(?) AND lower(last_name)=lower(?)""", (first,last))

    def insert_seminarian(self, data: dict[str, Any]) -> int:
        fields = self._seminarian_fields()
        normalized = self._normalize_seminarian_data(data)
        if not normalized["first_name"] or not normalized["last_name"]:
            raise ValueError("Nombres y apellidos son obligatorios.")
        photo=data.get("photo");insert_fields=fields+["photo"];marks = ",".join("?" for _ in insert_fields)
        try:
            with self.connect() as conn:
                cur=conn.execute(f"INSERT INTO seminarians({','.join(insert_fields)}) VALUES({marks})",[normalized[f] for f in fields]+[photo])
                self._audit(conn,"seminarian_created","seminarian",cur.lastrowid,f"{normalized['first_name']} {normalized['last_name']}")
                return cur.lastrowid
        except sqlite3.IntegrityError as exc:
            raise ValueError("Ya existe una ficha con ese número de identificación.") from exc

    def update_seminarian(self, seminarian_id: int, data: dict[str, Any]):
        fields=self._seminarian_fields(); normalized=self._normalize_seminarian_data(data)
        try:
            with self.connect() as conn:
                assignments=",".join(f"{f}=?" for f in fields)
                values=[normalized[f] for f in fields]
                if "photo" in data:assignments+=",photo=?";values.append(data.get("photo"))
                conn.execute("UPDATE seminarians SET "+assignments+",updated_at=CURRENT_TIMESTAMP WHERE id=?",values+[seminarian_id])
                self._audit(conn,"seminarian_updated","seminarian",seminarian_id,f"{normalized['first_name']} {normalized['last_name']}")
        except sqlite3.IntegrityError as exc:
            raise ValueError("Ya existe otra ficha con ese número de identificación.") from exc

    def archive_seminarian(self, seminarian_id: int):
        with self.connect() as conn:
            conn.execute("UPDATE seminarians SET archived=1,updated_at=CURRENT_TIMESTAMP WHERE id=?",(seminarian_id,))
            self._audit(conn,"seminarian_archived","seminarian",seminarian_id)

    def restore_seminarian(self, seminarian_id: int):
        with self.connect() as conn:
            conn.execute("UPDATE seminarians SET archived=0,updated_at=CURRENT_TIMESTAMP WHERE id=?",(seminarian_id,))
            self._audit(conn,"seminarian_restored","seminarian",seminarian_id)

    def delete_archived_seminarian(self, seminarian_id: int) -> dict[str, int]:
        """Permanently remove an archived health record while preserving anonymous stock history."""
        with self.connect() as conn:
            row=conn.execute("SELECT archived FROM seminarians WHERE id=?",(seminarian_id,)).fetchone()
            if not row:
                raise ValueError("La ficha ya no existe.")
            if not row["archived"]:
                raise ValueError("Primero archiva la ficha antes de eliminarla definitivamente.")
            active_loans=conn.execute("SELECT COUNT(*) FROM equipment_loans WHERE seminarian_id=? AND returned_at IS NULL",(seminarian_id,)).fetchone()[0]
            if active_loans:
                raise ValueError("No se puede eliminar: el seminarista tiene equipos pendientes de devolución.")
            control_ids=[r[0] for r in conn.execute("SELECT id FROM medical_controls WHERE seminarian_id=?",(seminarian_id,))]
            movements=conn.execute("SELECT COUNT(*) FROM movements WHERE seminarian_id=?",(seminarian_id,)).fetchone()[0]
            loans=conn.execute("SELECT COUNT(*) FROM equipment_loans WHERE seminarian_id=?",(seminarian_id,)).fetchone()[0]
            if control_ids:
                marks=",".join("?" for _ in control_ids)
                conn.execute(f"DELETE FROM audit_log WHERE entity_type='medical_control' AND entity_id IN ({marks})",control_ids)
            conn.execute("DELETE FROM medical_controls WHERE seminarian_id=?",(seminarian_id,))
            conn.execute("DELETE FROM audit_log WHERE entity_type='seminarian' AND entity_id=?",(seminarian_id,))
            # ON DELETE SET NULL anonymizes movements and completed loans without damaging inventory totals.
            conn.execute("DELETE FROM seminarians WHERE id=?",(seminarian_id,))
            self._audit(conn,"seminarian_permanently_deleted","seminarian",seminarian_id,
                        {"medical_controls_deleted":len(control_ids),"movements_anonymized":movements,"loans_anonymized":loans})
            result={"medical_controls":len(control_ids),"movements":movements,"loans":loans}
        # VACUUM runs outside the deletion transaction and returns freed pages to disk.
        vacuum=sqlite3.connect(self.path)
        try:vacuum.execute("VACUUM")
        finally:vacuum.close()
        self._chmod(Path(self.path),0o600)
        return result

    def upsert_seminarian(self, data: dict[str, Any]) -> tuple[int, bool]:
        normalized = self._normalize_seminarian_data(data)
        external_id = normalized["external_id"]
        first = normalized["first_name"]; last = normalized["last_name"]
        birth = normalized["birth_date"]
        if not first or not last:
            raise ValueError("Nombres y apellidos son obligatorios.")
        fields = self._seminarian_fields()
        with self.connect() as conn:
            matches = []
            if external_id:
                matches = conn.execute("SELECT id FROM seminarians WHERE external_id=?", (external_id,)).fetchall()
            elif birth:
                matches = conn.execute("""SELECT id FROM seminarians WHERE lower(first_name)=lower(?)
                    AND lower(last_name)=lower(?) AND birth_date=?""", (first,last,birth)).fetchall()
            else:
                same_name = conn.execute("""SELECT id FROM seminarians WHERE lower(first_name)=lower(?)
                    AND lower(last_name)=lower(?)""", (first,last)).fetchall()
                if same_name:
                    raise ValueError("REVISAR_DUPLICADO: existe una ficha con el mismo nombre y faltan identificación o fecha de nacimiento.")
            if len(matches) > 1:
                raise ValueError("REVISAR_DUPLICADO: hay más de una ficha coincidente; requiere revisión manual.")
            if matches:
                update_fields = []
                for field in fields:
                    if field in {"first_name","last_name"} or self._text(data.get(field)):
                        update_fields.append(field)
                assignments = ",".join(f"{f}=?" for f in update_fields)
                conn.execute(f"UPDATE seminarians SET {assignments},updated_at=CURRENT_TIMESTAMP WHERE id=?",
                             [normalized[f] for f in update_fields] + [matches[0]["id"]])
                self._audit(conn,"seminarian_import_updated","seminarian",matches[0]["id"],f"{first} {last}")
                return matches[0]["id"], False
            vals = [normalized[f] for f in fields]
            marks = ",".join("?" for _ in fields)
            cur = conn.execute(f"INSERT INTO seminarians({','.join(fields)}) VALUES({marks})", vals)
            self._audit(conn,"seminarian_import_created","seminarian",cur.lastrowid,f"{first} {last}")
            return cur.lastrowid, True

    def create_equipment_loan(self, item_id: int, seminarian_id: int, quantity: int,
                              expected_return: str | None, notes: str = "") -> int:
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            item = conn.execute("SELECT type FROM items WHERE id=? AND archived=0", (item_id,)).fetchone()
            if not item or item["type"] != "equipment":
                raise ValueError("Selecciona un equipo disponible.")
            movement_id = self._record_output(conn,item_id,quantity,"loan",seminarian_id,"","Préstamo de equipo",now)
            cur = conn.execute("""INSERT INTO equipment_loans(item_id,seminarian_id,quantity,lent_at,expected_return,notes,movement_id)
                VALUES(?,?,?,?,?,?,?)""", (item_id,seminarian_id,quantity,now,expected_return,notes.strip(),movement_id))
            self._audit(conn,"equipment_loaned","loan",cur.lastrowid,{"item_id":item_id,"seminarian_id":seminarian_id,"quantity":quantity})
            return cur.lastrowid

    def return_equipment_loan(self, loan_id: int):
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            loan = conn.execute("SELECT * FROM equipment_loans WHERE id=?", (loan_id,)).fetchone()
            if not loan or loan["returned_at"]:
                raise ValueError("El préstamo no existe o ya fue devuelto.")
            conn.execute("UPDATE equipment_loans SET returned_at=? WHERE id=?", (now,loan_id))
            conn.execute("UPDATE items SET stock=stock+? WHERE id=?", (loan["quantity"],loan["item_id"]))
            cur = conn.execute("""INSERT INTO movements(item_id,seminarian_id,type,quantity,reason,occurred_at)
                VALUES(?,?,?,?,?,?)""", (loan["item_id"],loan["seminarian_id"],"return",loan["quantity"],f"Devolución de préstamo #{loan_id}",now))
            return_movement = cur.lastrowid
            conn.execute("UPDATE equipment_loans SET return_movement_id=? WHERE id=?", (return_movement,loan_id))
            if loan["movement_id"]:
                for a in conn.execute("SELECT lot_id,quantity FROM movement_lot_allocations WHERE movement_id=?", (loan["movement_id"],)):
                    conn.execute("UPDATE lots SET quantity=quantity+? WHERE id=?", (a["quantity"],a["lot_id"]))
                    conn.execute("INSERT INTO movement_lot_allocations(movement_id,lot_id,quantity) VALUES(?,?,?)", (return_movement,a["lot_id"],a["quantity"]))
            self._audit(conn,"equipment_returned","loan",loan_id,{"return_movement_id":return_movement})

    def medication_safety_notice(self, item_id: int | None, seminarian_id: int | None) -> tuple[str, bool]:
        if not item_id or not seminarian_id:
            return "", False
        row = self.query("""SELECT s.allergies,i.name,i.generic_name FROM seminarians s CROSS JOIN items i
            WHERE s.id=? AND i.id=?""", (seminarian_id,item_id))
        if not row:
            return "", False
        allergies = self._text(row[0]["allergies"])
        if not allergies or allergies.lower() in {"ninguna","ninguna conocida","no","n/a","ninguno"}:
            return "Alergias registradas: ninguna conocida.", False
        def words(text: str) -> set[str]:
            plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().casefold()
            ignored = {"alergia","alergico","alergica","medicamento","medicamentos","conocida","ninguna",
                       "tableta","tabletas","capsula","capsulas","jarabe","acido","sodico","clorhidrato"}
            return {w for w in re.findall(r"[a-z0-9]+", plain) if len(w) >= 4 and w not in ignored}
        allergy_words = words(allergies)
        product_words = words(f"{row[0]['name']} {row[0]['generic_name']}")
        match = bool(allergy_words & product_words)
        return f"Alergias registradas: {allergies}", match

    def expiry_alerts(self):
        return self.query("""SELECT i.name,i.location,l.lot_number,l.expires_on,l.quantity,l.quarantined,l.quarantine_reason,
            CAST(julianday(date(l.expires_on))-julianday(date('now','localtime')) AS INTEGER) days
            FROM lots l JOIN items i ON i.id=l.item_id WHERE i.archived=0 AND l.quantity>0
            AND (l.quarantined=1 OR (l.expires_on IS NOT NULL
            AND date(l.expires_on)<=date('now','localtime', '+' || ? || ' days')))
            ORDER BY l.quarantined DESC,l.expires_on""", (EXPIRY_WARNING_DAYS,))
