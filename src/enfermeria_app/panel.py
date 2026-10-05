from __future__ import annotations

import sys

from PySide6.QtCore import QLockFile, QSettings, QTimer, Qt
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QMainWindow, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .config import ASSETS_DIR, DATA_DIR, DB_PATH, STYLE_SHEET
from .panel_data import PanelSnapshot, read_panel_snapshot
from .panel_integration import launch_main_application


class QuickPanel(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("SeminarioMayorGuayaquil", "PanelRapidoEnfermeria")
        self.compact = self.settings.value("compact", False, bool)
        self.setWindowTitle("Panel rápido de Enfermería")
        self.setWindowIcon(QIcon(str(ASSETS_DIR / "app_icon.png")))
        self.setMinimumWidth(360)
        self.resize(self.settings.value("size", self.size()))
        if self.settings.contains("position"):
            self.move(self.settings.value("position"))

        body = QWidget(); self.setCentralWidget(body)
        root = QVBoxLayout(body); root.setContentsMargins(16, 14, 16, 14); root.setSpacing(10)
        heading = QHBoxLayout()
        title_box = QVBoxLayout(); self.title_label = QLabel("Panel rápido de Enfermería"); self.title_label.setObjectName("title"); title_box.addWidget(self.title_label)
        self.updated = QLabel("Preparando resumen…"); self.updated.setObjectName("subtitle"); title_box.addWidget(self.updated); heading.addLayout(title_box, 1)
        self.refresh_button = QPushButton("Actualizar"); self.refresh_button.clicked.connect(self.refresh); heading.addWidget(self.refresh_button)
        root.addLayout(heading)

        self.cards = QGridLayout(); self.cards.setSpacing(8); root.addLayout(self.cards)
        self.card_values: dict[str, QLabel] = {}
        for index, (key, label, color) in enumerate((
            ("expiry", "Vencimientos", "#f1bd63"), ("low", "Stock bajo", "#f1bd63"),
            ("loans", "Equipos prestados", "#60d5b7"), ("attention", "Atención requerida", "#ef6a72"),
        )):
            frame = QFrame(); frame.setObjectName("card"); frame.setMinimumHeight(62); box = QVBoxLayout(frame); box.setContentsMargins(9, 5, 9, 5); box.setSpacing(0)
            value = QLabel("0"); value.setStyleSheet(f"font-size:25px;font-weight:800;color:{color};background:transparent"); box.addWidget(value)
            caption = QLabel(label); caption.setObjectName("muted"); caption.setWordWrap(True); box.addWidget(caption)
            self.cards.addWidget(frame, index // 2, index % 2); self.card_values[key] = value

        self.detail_heading = QLabel("Alertas y préstamos"); self.detail_heading.setObjectName("sectionTitle"); root.addWidget(self.detail_heading)
        self.grid = QTableWidget(0, 5); self.grid.setHorizontalHeaderLabels(["Tipo", "Producto o equipo", "Detalle", "Ubicación / fecha", "Estado"])
        self.grid.verticalHeader().setVisible(False); self.grid.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.grid.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.grid.setAlternatingRowColors(True)
        self.grid.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.grid.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.grid.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.grid.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.grid.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.grid.doubleClicked.connect(self.open_main); root.addWidget(self.grid, 1)

        controls = QHBoxLayout(); self.always_on_top = QCheckBox("Siempre visible"); self.always_on_top.setChecked(self.settings.value("always_on_top", False, bool)); self.always_on_top.toggled.connect(self.set_always_on_top); controls.addWidget(self.always_on_top)
        self.compact_button = QPushButton(); self.compact_button.clicked.connect(self.toggle_compact); controls.addWidget(self.compact_button)
        controls.addStretch(); self.open_button = QPushButton("Abrir Enfermería"); self.open_button.setProperty("primary", True); self.open_button.clicked.connect(self.open_main); controls.addWidget(self.open_button); root.addLayout(controls)

        self.timer = QTimer(self); self.timer.setInterval(5 * 60 * 1000); self.timer.timeout.connect(self.refresh); self.timer.start()
        self.set_always_on_top(self.always_on_top.isChecked()); self.apply_compact(); self.refresh()

    def refresh(self):
        self.refresh_button.setEnabled(False)
        try:
            snapshot = read_panel_snapshot(DB_PATH)
            self.render(snapshot)
        except Exception as exc:
            self.updated.setText("No se pudo leer la base. Se intentará de nuevo automáticamente.")
            self.statusBar().showMessage(str(exc), 8000)
        finally:
            self.refresh_button.setEnabled(True)

    def render(self, snapshot: PanelSnapshot):
        self.card_values["expiry"].setText(str(snapshot.expired + snapshot.expiring))
        self.card_values["low"].setText(str(snapshot.low_stock))
        self.card_values["loans"].setText(str(snapshot.active_loans))
        self.card_values["attention"].setText(str(snapshot.attention_required))
        self.updated.setText(f"Actualizado {snapshot.updated_at.strftime('%H:%M')}" if self.compact else f"Actualizado {snapshot.updated_at.strftime('%H:%M')} · lectura automática cada 5 minutos")
        self.grid.setRowCount(0)
        for alert in snapshot.alerts:
            row = self.grid.rowCount(); self.grid.insertRow(row)
            location_due = alert.location if alert.due == "—" else f"{alert.location} · {alert.due}"
            color = "#ef6a72" if alert.severity >= 3 else ("#f1bd63" if alert.severity == 2 else "#60d5b7")
            for column, value in enumerate((alert.kind, alert.title, alert.detail, location_due, alert.state)):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                if column == 4: item.setForeground(QColor(color))
                self.grid.setItem(row, column, item)
        if not snapshot.alerts:
            self.grid.insertRow(0); item = QTableWidgetItem("Sin novedades pendientes"); item.setForeground(QColor("#56d38a")); self.grid.setItem(0, 0, item); self.grid.setSpan(0, 0, 1, 5)

    def toggle_compact(self):
        self.compact = not self.compact; self.settings.setValue("compact", self.compact); self.apply_compact()

    def apply_compact(self):
        self.detail_heading.setVisible(not self.compact); self.grid.setVisible(not self.compact)
        self.compact_button.setText("Ver detalles" if self.compact else "Vista compacta")
        if self.compact:
            self.title_label.setText("Panel de Enfermería");self.title_label.setStyleSheet("font-size:19px;font-weight:800;background:transparent")
            self.refresh_button.setText("Actualizar");self.open_button.setText("Abrir")
            self.setMinimumSize(380, 280); self.setMaximumSize(430, 335); self.resize(400, 300)
        else:
            self.title_label.setText("Panel rápido de Enfermería");self.title_label.setStyleSheet("")
            self.refresh_button.setText("Actualizar");self.open_button.setText("Abrir Enfermería")
            self.setMaximumSize(16777215, 16777215); self.setMinimumSize(620, 500); self.resize(max(720, self.width()), max(590, self.height()))

    def set_always_on_top(self, enabled: bool):
        self.settings.setValue("always_on_top", enabled)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)
        if self.isVisible(): self.show()

    def open_main(self):
        if not launch_main_application():
            QMessageBox.warning(self, "No se pudo abrir", "No fue posible iniciar la aplicación principal.")

    def closeEvent(self, event):
        self.settings.setValue("position", self.pos()); self.settings.setValue("size", self.size())
        super().closeEvent(event)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Panel rápido de Enfermería")
    app.setOrganizationName("Seminario Mayor de Guayaquil")
    app.setStyle("Fusion"); app.setStyleSheet(STYLE_SHEET)
    lock = QLockFile(str(DATA_DIR / "panel-rapido.lock")); lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(None, "Panel rápido", "El Panel rápido ya está abierto.")
        return 0
    panel = QuickPanel(); panel._instance_lock = lock; panel.show()
    return app.exec()
