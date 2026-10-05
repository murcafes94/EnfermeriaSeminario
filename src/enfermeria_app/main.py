import shutil
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from .config import DATA_DIR, DB_PATH, PROJECT_ROOT, STYLE_SHEET
from .database import Database
from .ui import MainWindow, PinDialog
from .linux_desktop import is_linux_desktop, move_window_to_workspace


def configure_logging():
    handler=RotatingFileHandler(DATA_DIR/"enfermeria.log",maxBytes=1_000_000,backupCount=3,encoding="utf-8")
    try:(DATA_DIR/"enfermeria.log").chmod(0o600)
    except OSError:pass
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root=logging.getLogger();root.setLevel(logging.INFO);root.addHandler(handler)


def main():
    # Conserva automáticamente la base de la versión GTK si está junto al proyecto.
    if not DB_PATH.exists():
        candidates = [PROJECT_ROOT / "enfermeria.db", Path.cwd() / "enfermeria.db"]
        legacy = next((p for p in candidates if p.exists() and p.resolve() != DB_PATH.resolve()), None)
        if legacy:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy, DB_PATH)
    configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("Enfermería San Giuseppe Moscati")
    app.setDesktopFileName("enfermeria-san-giuseppe-moscati")
    app.setOrganizationName("Seminario Mayor de Guayaquil")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE_SHEET)
    db=Database()
    def handle_exception(exc_type,exc_value,traceback):
        logging.getLogger("enfermeria").exception("Error no controlado",exc_info=(exc_type,exc_value,traceback))
        QMessageBox.critical(None,"Error inesperado","Ocurrió un error inesperado. La información técnica se guardó en enfermeria.log.")
    sys.excepthook=handle_exception
    if db.has_pin() and not PinDialog(db).exec():
        return 0
    db.log_action("application_opened","application")
    window = MainWindow(db)
    window.show()
    if is_linux_desktop() and db.get_setting("linux_workspace_2","1")=="1":
        QTimer.singleShot(350,lambda:move_window_to_workspace(int(window.winId()),1))
    if is_linux_desktop() and db.get_setting("linux_fullscreen","1")=="1":
        QTimer.singleShot(650,window.showFullScreen)
    return app.exec()
