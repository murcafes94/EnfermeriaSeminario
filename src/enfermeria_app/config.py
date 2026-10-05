import os
import sys
from pathlib import Path

APP_NAME = "EnfermeriaSeminario"
APP_AUTHOR = "SeminarioMayorGuayaquil"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
ASSETS_DIR = BUNDLE_ROOT / "assets"
if sys.platform == "win32":
    DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / APP_AUTHOR / APP_NAME
else:
    DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_NAME
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "enfermeria.db"

STOCK_MIN_DEFAULT = 5
EXPIRY_WARNING_DAYS = 90

FORMATION_STAGES = [
    "Propedéutico",
    "1° Filosofía",
    "2° Filosofía",
    "1° Teología",
    "2° Teología",
    "3° Teología",
    "4° Teología",
]

BLOOD_TYPES = ["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"]

LOCATIONS = [
    ("Por asignar", "Por asignar"),
    ("AB", "AB · Antibióticos y antiinfecciosos"),
    ("AL", "AL · Antialérgicos y antihistamínicos"),
    ("RS", "RS · Respiratorio, tos y mucolíticos"),
    ("NO", "NO · Nasales y óticos"),
    ("GR", "GR · Estómago, reflujo y protectores"),
    ("DG", "DG · Digestivo, náuseas y motilidad"),
    ("IN", "IN · Intestino, estreñimiento y probióticos"),
    ("DA", "DA · Dolor, fiebre y antiinflamatorios"),
    ("CV", "CV · Hipertensión y cardiovascular"),
    ("AC", "AC · Anticoagulantes y circulación"),
    ("CL", "CL · Colesterol y triglicéridos"),
    ("DM", "DM · Diabetes y metabolismo"),
    ("DR", "DR · Dermatológicos, cremas y ungüentos"),
    ("AF", "AF · Antifúngicos"),
    ("VH", "VH · Vitaminas, hierro y suplementación"),
    ("UR", "UR · Urología"),
    ("HB", "HB · Hígado y vías biliares"),
    ("SH", "SH · Sedantes e hipnóticos (controlado)"),
    ("OT", "OT · Otros o pendiente de clasificar"),
    ("VP", "VP · Vence pronto (separar físicamente)"),
    ("VE", "VE · Vencido, no entregar (cuarentena)"),
    ("CU", "CU · Cuarentena o revisar"),
]

COLORS = {
    "navy": "#0b2f49",
    "navy_2": "#123b5d",
    "teal": "#0f6f78",
    "mint": "#60d5b7",
    "surface": "#102b3c",
    "surface_2": "#17384b",
    "text": "#edf7f8",
    "muted": "#a9bdc7",
    "danger": "#ef6a72",
    "warning": "#f1bd63",
    "success": "#56d38a",
}

STYLE_SHEET = """
QMainWindow, QWidget { background:#071d2b; color:#edf7f8; font-family:'Noto Sans','Segoe UI',sans-serif; font-size:13px; }
QLabel { background:transparent; }
QFrame#sidebar { background:#0b2f49; border-right:1px solid #1d5268; }
QFrame#card, QGroupBox { background:#102b3c; border:1px solid #224b5e; border-radius:12px; }
QGroupBox { margin-top:12px; padding:14px 10px 10px; font-weight:700; }
QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 6px; }
QLabel#title { font-size:23px; font-weight:800; }
QLabel#sectionTitle { font-size:15px; font-weight:800; color:#60d5b7; padding-top:10px; }
QLabel#subtitle, QLabel#muted { color:#a9bdc7; }
QLabel#stat { font-size:28px; font-weight:800; }
QPushButton { background:#17384b; border:1px solid #28556a; border-radius:8px; padding:8px 12px; color:#edf7f8; }
QPushButton:hover { background:#1e4b60; }
QPushButton:disabled { color:#708995; background:#102b3c; border-color:#1c4355; }
QPushButton[primary='true'] { background:#0f6f78; border-color:#31949b; font-weight:700; }
QPushButton[danger='true'] { background:#753844; border-color:#a44b59; }
QPushButton#nav { text-align:left; border:0; background:transparent; padding:10px 14px; font-weight:600; }
QPushButton#nav:checked { background:#0f6f78; }
QLineEdit, QComboBox, QDateEdit, QSpinBox, QTextEdit { background:#0c2636; border:1px solid #2b576b; border-radius:7px; padding:7px; selection-background-color:#0f6f78; }
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus, QTextEdit:focus { border:2px solid #60d5b7; }
QTableWidget { background:#0c2636; alternate-background-color:#102f41; border:1px solid #28556a; border-radius:8px; gridline-color:#28556a; selection-background-color:#0f6f78; }
QHeaderView::section { background:#16384b; color:#edf7f8; padding:8px; border:0; border-right:1px solid #28556a; font-weight:700; }
QScrollBar:vertical { background:#0c2636; width:12px; margin:0; }
QScrollBar::handle:vertical { background:#0f6f78; border-radius:6px; min-height:28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
QScrollBar:horizontal { background:#0c2636; height:12px; margin:0; }
QScrollBar::handle:horizontal { background:#0f6f78; border-radius:6px; min-width:28px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0; }
QTabWidget::pane { border:1px solid #28556a; border-radius:8px; }
QTabBar::tab { background:#102b3c; padding:8px 14px; }
QTabBar::tab:selected { background:#0f6f78; }
QStatusBar { background:#0b2f49; color:#a9bdc7; border-top:1px solid #1d5268; }
QToolTip { background:#17384b; color:#edf7f8; border:1px solid #60d5b7; padding:5px; }
"""
