from __future__ import annotations

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtCore import QBuffer, QByteArray, QDate, QDateTime, QIODevice, QLocale, QSize, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDateEdit, QDateTimeEdit, QDialog, QDialogButtonBox,
    QCheckBox, QFileDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QGroupBox, QInputDialog, QLineEdit, QMainWindow, QMessageBox, QPushButton, QScrollArea,
    QDoubleSpinBox, QSpinBox, QStackedWidget, QTabWidget, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout, QWidget,
)

from .config import ASSETS_DIR, BLOOD_TYPES, FORMATION_STAGES, LOCATIONS
from .database import Database, proper_name, sentence_case
from .excel_io import export_inventory, export_medical_controls, export_movements, export_seminarians, import_inventory, import_seminarians
from .pdf_export import export_all_dossiers_pdf, export_control_pdf, export_emergency_summary_pdf, export_seminarian_dossier_pdf
from .linux_desktop import is_linux_desktop, workspace_support_status
from .notifier import send_native_notification
from .panel_integration import (
    is_notifier_autostart_enabled, is_panel_autostart_enabled, launch_panel,
    set_notifier_autostart, set_panel_autostart,
)
from .sync_ui import WebSyncPage
from . import __version__


def button(text: str, slot=None, primary=False, danger=False):
    b = QPushButton(text)
    if primary: b.setProperty("primary", True)
    if danger: b.setProperty("danger", True)
    if slot: b.clicked.connect(slot)
    return b


def table(headers: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setAlternatingRowColors(True)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.verticalHeader().setVisible(False);t.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    t.horizontalHeader().setStretchLastSection(False);t.horizontalHeader().setMinimumSectionSize(55)
    t.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    t.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    t.setWordWrap(False);t.setTextElideMode(Qt.TextElideMode.ElideRight)
    for index,header in enumerate(headers):t.setColumnWidth(index,max(85,min(210,len(header)*12+35)))
    return t


def fit_table_height(widget: QTableWidget, minimum_rows: int = 2, maximum_rows: int = 12):
    """Auto-fit cells like a spreadsheet and keep short tables compact."""
    widget.resizeColumnsToContents()
    for column in range(widget.columnCount()):
        widget.setColumnWidth(column,max(70,min(widget.columnWidth(column)+14,380)))
    visible_rows=max(minimum_rows,min(widget.rowCount(),maximum_rows))
    row_height=widget.verticalHeader().defaultSectionSize()
    height=widget.horizontalHeader().height()+(visible_rows*row_height)+4
    if widget.horizontalScrollBar().maximum()>0:height+=widget.horizontalScrollBar().sizeHint().height()
    widget.setMinimumHeight(height);widget.setMaximumHeight(height)


def save_cancel_buttons(parent, accept_slot):
    controls=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel,parent=parent)
    controls.button(QDialogButtonBox.StandardButton.Save).setText("Guardar")
    controls.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
    controls.accepted.connect(accept_slot);controls.rejected.connect(parent.reject)
    return controls


def scrollable_form(parent):
    scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.Shape.NoFrame)
    body=QWidget();form=QFormLayout(body);form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    form.setContentsMargins(8,8,14,8);form.setHorizontalSpacing(18);form.setVerticalSpacing(10);scroll.setWidget(body)
    return scroll,form


def selected_id(t: QTableWidget) -> int | None:
    rows = t.selectionModel().selectedRows()
    return int(t.item(rows[0].row(), 0).text()) if rows else None


def set_row(t: QTableWidget, values, colors: dict[int, str] | None = None):
    row = t.rowCount(); t.insertRow(row)
    for col, value in enumerate(values):
        item = QTableWidgetItem("" if value is None else str(value))
        if colors and col in colors: item.setForeground(QColor(colors[col]))
        t.setItem(row, col, item)


def add_page_header(layout: QVBoxLayout, title: str, subtitle: str):
    label=QLabel(title); label.setObjectName("title"); layout.addWidget(label)
    sub=QLabel(subtitle); sub.setObjectName("subtitle"); sub.setWordWrap(True); layout.addWidget(sub)
    layout.addSpacing(6)


class ImportPreviewDialog(QDialog):
    def __init__(self,parent,title,result):
        super().__init__(parent);self.setWindowTitle(title);self.resize(640,430);self.setMinimumSize(560,390)
        root=QVBoxLayout(self);heading=QLabel("Revisión antes de importar");heading.setObjectName("title");root.addWidget(heading)
        note=QLabel("La base de datos todavía no ha sido modificada. Revisa el resumen y confirma para aplicar los cambios.");note.setWordWrap(True);note.setObjectName("subtitle");root.addWidget(note)
        grid=table(["Resultado","Cantidad"]);labels=[]
        if "recognized" in result:labels.append(("Filas reconocidas",result.get("recognized",0)))
        labels.extend([("Registros nuevos",result.get("created",0)),("Registros actualizados",result.get("updated",0))])
        if "stock_entries" in result:labels.append(("Entradas de stock o lotes",result.get("stock_entries",0)))
        if "expired_rejected" in result:labels.extend([("Lotes vencidos rechazados",result.get("expired_rejected",0)),("Unidades vencidas no importadas",result.get("expired_units",0))])
        labels.extend([("Requieren revisión",result.get("review",0)),("Omitidos",result.get("skipped",0)),("Errores",result.get("errors",0))])
        grid.setColumnWidth(0,390);grid.setColumnWidth(1,150)
        warning_labels={"Requieren revisión","Errores","Lotes vencidos rechazados","Unidades vencidas no importadas"}
        for label,value in labels:set_row(grid,[label,value],{1:"#ef6a72" if label in warning_labels and value else "#edf7f8"})
        root.addWidget(grid,1);buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Apply|QDialogButtonBox.StandardButton.Cancel);apply_button=buttons.button(QDialogButtonBox.StandardButton.Apply);apply_button.setText("Confirmar importación");apply_button.clicked.connect(self.accept);buttons.rejected.connect(self.reject);root.addWidget(buttons)


class PinDialog(QDialog):
    def __init__(self,db:Database):
        super().__init__();self.db=db;self.attempts=0;self.setWindowTitle("Acceso a Enfermería");self.setFixedSize(420,245)
        root=QVBoxLayout(self);title=QLabel("Enfermería San Giuseppe Moscati");title.setObjectName("title");root.addWidget(title)
        subtitle=QLabel("Ingresa el PIN del encargado para abrir la aplicación.");subtitle.setObjectName("subtitle");root.addWidget(subtitle)
        self.pin=QLineEdit();self.pin.setEchoMode(QLineEdit.EchoMode.Password);self.pin.setMaxLength(8);self.pin.setPlaceholderText("PIN de 4 a 8 números");self.pin.returnPressed.connect(self.validate);root.addWidget(self.pin)
        self.error=QLabel("");self.error.setStyleSheet("color:#ef6a72;font-weight:700");root.addWidget(self.error)
        recover=button("Recuperar acceso con código institucional",self.recover);root.addWidget(recover)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Ingresar");buttons.accepted.connect(self.validate);buttons.rejected.connect(self.reject);root.addWidget(buttons)

    def validate(self):
        if self.db.verify_pin(self.pin.text()):self.accept();return
        self.attempts+=1;self.pin.clear();self.error.setText(f"PIN incorrecto. Intento {self.attempts} de 5.")
        if self.attempts>=5:self.reject()

    def recover(self):
        dialog=RecoveryDialog(self,self.db)
        if dialog.exec():
            QMessageBox.information(self,"Acceso recuperado",f"El PIN fue cambiado. Guarda este NUEVO código institucional en custodia separada:\n\n{dialog.new_recovery_code}\n\nEl código anterior dejó de funcionar.")
            self.accept()


class RecoveryDialog(QDialog):
    def __init__(self,parent,db:Database):
        super().__init__(parent);self.db=db;self.new_recovery_code="";self.setWindowTitle("Recuperación supervisada del PIN");self.resize(510,350)
        form=QFormLayout(self);notice=QLabel("Este procedimiento exige el nombre exacto del responsable institucional y el código entregado al configurar el PIN. El proceso queda registrado en auditoría.");notice.setWordWrap(True);notice.setObjectName("subtitle");form.addRow(notice)
        self.supervisor=QLineEdit();self.code=QLineEdit();self.code.setEchoMode(QLineEdit.EchoMode.Password);self.new_pin=QLineEdit();self.new_pin.setEchoMode(QLineEdit.EchoMode.Password);self.confirm=QLineEdit();self.confirm.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Responsable institucional *",self.supervisor);form.addRow("Código de recuperación *",self.code);form.addRow("Nuevo PIN *",self.new_pin);form.addRow("Confirmar nuevo PIN *",self.confirm)
        controls=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);controls.button(QDialogButtonBox.StandardButton.Ok).setText("Recuperar acceso");controls.accepted.connect(self.validate);controls.rejected.connect(self.reject);form.addRow(controls)
    def validate(self):
        if self.new_pin.text()!=self.confirm.text():QMessageBox.warning(self,"No coincide","Los PIN no coinciden.");return
        try:self.new_recovery_code=self.db.reset_pin_with_recovery(self.code.text(),self.supervisor.text(),self.new_pin.text());self.accept()
        except Exception as exc:QMessageBox.critical(self,"No se pudo recuperar",str(exc))


class PurgeDialog(QDialog):
    def __init__(self,parent):
        super().__init__(parent);self.setWindowTitle("Purgar datos de la aplicación");self.resize(520,330)
        root=QVBoxLayout(self);title=QLabel("Esta acción es irreversible");title.setObjectName("title");title.setStyleSheet("color:#ef6a72;background:transparent;");root.addWidget(title)
        warning=QLabel("Se eliminarán definitivamente el inventario, lotes, movimientos, préstamos, expedientes de salud, fotografías, controles de salud y el registro de auditoría. Se conservarán la identidad institucional, la configuración y el PIN.");warning.setWordWrap(True);warning.setObjectName("subtitle");root.addWidget(warning)
        outside=QLabel("Las copias guardadas manualmente fuera de la carpeta de la aplicación no pueden eliminarse desde aquí.");outside.setWordWrap(True);outside.setStyleSheet("color:#f1bd63;background:transparent;");root.addWidget(outside)
        self.delete_backups=QCheckBox("Eliminar también todas las copias de seguridad locales");self.delete_backups.setChecked(True);root.addWidget(self.delete_backups)
        root.addWidget(QLabel("Para continuar, escribe PURGAR:"));self.confirmation=QLineEdit();self.confirmation.setPlaceholderText("PURGAR");root.addWidget(self.confirmation)
        controls=QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok);controls.button(QDialogButtonBox.StandardButton.Ok).setText("Purgar definitivamente");controls.button(QDialogButtonBox.StandardButton.Ok).setProperty("danger",True);controls.accepted.connect(self.validate);controls.rejected.connect(self.reject);root.addWidget(controls)
    def validate(self):
        if self.confirmation.text().strip()!="PURGAR":QMessageBox.warning(self,"Confirmación incorrecta","Escribe exactamente PURGAR para habilitar esta acción.");return
        self.accept()


class ItemDialog(QDialog):
    def __init__(self, parent, data=None):
        super().__init__(parent);self.is_new=not data;self.setWindowTitle("Editar producto" if data else "Nuevo producto");self.resize(650,650);self.setMinimumSize(480,420)
        data=dict(data or {});layout=QVBoxLayout(self);scroll,form=scrollable_form(self);layout.addWidget(scroll,1)
        self.name = QLineEdit(str(data.get("name", "")))
        self.kind = QComboBox(); self.kind.addItem("Medicamento", "medicine"); self.kind.addItem("Insumo", "supply"); self.kind.addItem("Equipo", "equipment")
        self.kind.setCurrentIndex(max(0, self.kind.findData(data.get("type", "medicine"))))
        self.generic = QLineEdit(str(data.get("generic_name", ""))); self.concentration = QLineEdit(str(data.get("concentration", "")))
        self.presentation = QLineEdit(str(data.get("presentation", ""))); self.category = QLineEdit(str(data.get("category", "")))
        self.location = QComboBox()
        for code, label in LOCATIONS: self.location.addItem(label, code)
        self.location.setCurrentIndex(max(0, self.location.findData(data.get("location", "Por asignar"))))
        minimum = data.get("minimum_stock", 5)
        self.unit = QLineEdit(str(data.get("unit", "unidad"))); self.minimum = QSpinBox(); self.minimum.setRange(0, 100000); self.minimum.setValue(int(5 if minimum in (None, "") else minimum))
        self.usage = QTextEdit(str(data.get("usage", ""))); self.usage.setMaximumHeight(80)
        self.source = QLineEdit(str(data.get("source", ""))); self.notes = QTextEdit(str(data.get("notes", ""))); self.notes.setMaximumHeight(70)
        for label, widget in [("Nombre *",self.name),("Tipo *",self.kind),("Genérico",self.generic),("Concentración",self.concentration),
                              ("Presentación",self.presentation),("Categoría",self.category),("Ubicación",self.location),("Unidad",self.unit),
                              ("Stock mínimo",self.minimum),("Uso o indicación",self.usage),("Fuente",self.source),("Observaciones",self.notes)]: form.addRow(label, widget)
        self.initial_qty=None
        if self.is_new:
            section=QLabel("Existencia inicial (opcional)");section.setObjectName("sectionTitle");form.addRow(section)
            self.initial_qty=QSpinBox();self.initial_qty.setRange(0,100000);self.initial_qty.setSpecialValueText("Sin existencia inicial")
            self.initial_lot=QLineEdit()
            self.initial_expiry_choice=QComboBox();self.initial_expiry_choice.addItem("Selecciona una opción…",None);self.initial_expiry_choice.addItem("Sí, registrar fecha",True);self.initial_expiry_choice.addItem("No tiene o se desconoce",False)
            self.initial_expiry=QDateEdit(QDate.currentDate());self.initial_expiry.setCalendarPopup(True);self.initial_expiry.setDisplayFormat("dd/MM/yyyy")
            self.initial_reason=QLineEdit("Inventario inicial")
            for label,widget in [("Cantidad disponible",self.initial_qty),("Número de lote",self.initial_lot),("¿Tiene vencimiento?",self.initial_expiry_choice),("Fecha de vencimiento",self.initial_expiry),("Motivo de entrada",self.initial_reason)]:form.addRow(label,widget)
        layout.addWidget(save_cancel_buttons(self,self.validate))

    def validate(self):
        if not self.name.text().strip(): QMessageBox.warning(self,"Dato requerido","Escribe el nombre del producto."); return
        if self.initial_qty and self.initial_qty.value()>0 and self.initial_expiry_choice.currentData() is None:
            QMessageBox.warning(self,"Dato requerido","Confirma si la existencia inicial tiene fecha de vencimiento.");return
        self.accept()

    def values(self):
        return {"name":self.name.text(),"type":self.kind.currentData(),"generic_name":self.generic.text(),"concentration":self.concentration.text(),
                "presentation":self.presentation.text(),"category":self.category.text(),"location":self.location.currentData(),"unit":self.unit.text(),
                "minimum_stock":self.minimum.value(),"usage":self.usage.toPlainText(),"source":self.source.text(),"notes":self.notes.toPlainText()}

    def initial_stock(self):
        if not self.initial_qty or self.initial_qty.value()==0:return (0,"",None,"")
        expiry=self.initial_expiry.date().toString("yyyy-MM-dd") if self.initial_expiry_choice.currentData() else None
        return self.initial_qty.value(),self.initial_lot.text(),expiry,self.initial_reason.text()


class StockDialog(QDialog):
    def __init__(self, parent, item_name):
        super().__init__(parent); self.setWindowTitle(f"Añadir existencia · {item_name}"); self.resize(430, 330)
        form = QFormLayout(self); self.qty=QSpinBox(); self.qty.setRange(1,100000); self.qty.setValue(1)
        self.lot=QLineEdit();self.expires=QDateEdit(); self.expires.setCalendarPopup(True); self.expires.setDisplayFormat("dd/MM/yyyy"); self.expires.setDate(QDate.currentDate())
        self.expiry_choice=QComboBox(); self.expiry_choice.addItem("Selecciona una opción…",None); self.expiry_choice.addItem("Sí, registrar fecha",True); self.expiry_choice.addItem("No tiene o se desconoce",False)
        self.reason=QLineEdit("Entrada de inventario")
        form.addRow("Cantidad *",self.qty); form.addRow("Número de lote",self.lot); form.addRow("¿Tiene vencimiento? *",self.expiry_choice); form.addRow("Fecha",self.expires); form.addRow("Motivo",self.reason)
        controls=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); controls.accepted.connect(self.validate); controls.rejected.connect(self.reject); form.addRow(controls)

    def validate(self):
        if self.expiry_choice.currentData() is None:
            QMessageBox.warning(self,"Dato requerido","Confirma si el producto tiene fecha de vencimiento."); return
        self.accept()

    def values(self):
        expiry = self.expires.date().toString("yyyy-MM-dd") if self.expiry_choice.currentData() else None
        return self.qty.value(),self.lot.text(),expiry,self.reason.text()


class LotsDialog(QDialog):
    def __init__(self,parent,db:Database,item_id:int,item_name:str):
        super().__init__(parent);self.db=db;self.item_id=item_id;self.setWindowTitle(f"Lotes · {item_name}");self.resize(720,430)
        root=QVBoxLayout(self);title=QLabel(f"Lotes de {item_name}");title.setObjectName("title");root.addWidget(title)
        note=QLabel("Edita la identificación o vencimiento. La cuarentena bloquea la entrega del lote sin cambiar la ubicación general ni borrar sus unidades.");note.setWordWrap(True);note.setObjectName("subtitle");root.addWidget(note)
        self.grid=table(["ID","Lote","Vencimiento","Cantidad","Estado","Motivo de cuarentena"]);root.addWidget(self.grid,1)
        actions=QHBoxLayout();actions.addWidget(button("Editar lote",self.edit));actions.addWidget(button("Cuarentena / liberar",self.quarantine));actions.addWidget(button("Retirar lote seleccionado",self.discard,False,True));actions.addStretch();actions.addWidget(button("Cerrar",self.accept));root.addLayout(actions);self.refresh()

    def refresh(self):
        self.grid.setRowCount(0);today=date.today()
        for r in self.db.query("SELECT id,lot_number,expires_on,quantity,quarantined,quarantine_reason FROM lots WHERE item_id=? ORDER BY quarantined DESC,CASE WHEN expires_on IS NULL THEN 1 ELSE 0 END,expires_on,id",(self.item_id,)):
            expiry=r["expires_on"] or "—"
            if r["quantity"]<=0:state="Sin existencias";color="#a9bdc7"
            elif r["quarantined"]:state="CUARENTENA";color="#ef6a72"
            elif not r["expires_on"]:state="Sin fecha";color="#f1bd63"
            else:
                days=(date.fromisoformat(r["expires_on"])-today).days
                if days<0:state="Vencido";color="#ef6a72"
                elif days<=90:state=f"Vence en {days} días";color="#f1bd63"
                else:state="Vigente";color="#56d38a"
            set_row(self.grid,[r["id"],r["lot_number"] or "—",expiry,r["quantity"],state,r["quarantine_reason"] or "—"],{4:color})

    def edit(self,*_):
        lot_id=selected_id(self.grid)
        if not lot_id:QMessageBox.information(self,"Selecciona","Selecciona un lote.");return
        row=self.db.query("SELECT lot_number,expires_on FROM lots WHERE id=?",(lot_id,))[0]
        dialog=QDialog(self);dialog.setWindowTitle("Editar lote");form=QFormLayout(dialog);lot=QLineEdit(row["lot_number"] or "")
        choice=QComboBox();choice.addItem("Registrar fecha",True);choice.addItem("Sin fecha o desconocida",False);choice.setCurrentIndex(0 if row["expires_on"] else 1)
        expiry=QDateEdit();expiry.setCalendarPopup(True);expiry.setDisplayFormat("dd/MM/yyyy");expiry.setDate(QDate.fromString(row["expires_on"],"yyyy-MM-dd") if row["expires_on"] else QDate.currentDate())
        form.addRow("Número de lote",lot);form.addRow("Vencimiento",choice);form.addRow("Fecha",expiry)
        controls=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);controls.accepted.connect(dialog.accept);controls.rejected.connect(dialog.reject);form.addRow(controls)
        if dialog.exec():
            try:self.db.update_lot(lot_id,lot.text(),expiry.date().toString("yyyy-MM-dd") if choice.currentData() else None);self.refresh()
            except Exception as exc:QMessageBox.critical(self,"No se pudo completar",str(exc))

    def quarantine(self):
        lot_id=selected_id(self.grid)
        if not lot_id:QMessageBox.information(self,"Selecciona","Selecciona un lote.");return
        row=self.db.query("SELECT quarantined,quantity FROM lots WHERE id=?",(lot_id,))[0]
        try:
            if row["quarantined"]:
                if QMessageBox.question(self,"Liberar lote","¿Confirmas que el lote fue revisado y puede volver a utilizarse?")!=QMessageBox.StandardButton.Yes:return
                self.db.set_lot_quarantine(lot_id,False);self.refresh()
            else:
                reason,ok=QInputDialog.getText(self,"Enviar a cuarentena","Motivo (vencido, dañado, sello roto, revisión pendiente…):")
                if not ok:return
                self.db.set_lot_quarantine(lot_id,True,reason);self.refresh()
        except Exception as exc:QMessageBox.warning(self,"No se pudo completar",str(exc))

    def discard(self):
        lot_id=selected_id(self.grid)
        if not lot_id:QMessageBox.information(self,"Selecciona","Selecciona un lote.");return
        row=self.db.query("SELECT lot_number,quantity,expires_on FROM lots WHERE id=?",(lot_id,))[0]
        if row["quantity"]<=0:QMessageBox.information(self,"Sin existencias","Ese lote ya no tiene existencias.");return
        expired=bool(row["expires_on"] and date.fromisoformat(row["expires_on"])<date.today());default_reason="Producto vencido" if expired else ""
        reason,ok=QInputDialog.getText(self,"Retirar lote",f"Motivo para retirar las {row['quantity']} unidades del lote {row['lot_number'] or 'sin número'}:",QLineEdit.EchoMode.Normal,default_reason)
        if not ok:return
        if QMessageBox.warning(self,"Confirmar retiro","Se descontará todo el lote del inventario y se creará un movimiento auditable. ¿Continuar?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        try:self.db.discard_lot(lot_id,reason);self.refresh()
        except Exception as exc:QMessageBox.critical(self,"No se pudo completar",str(exc))


class ArchivedItemsDialog(QDialog):
    restored=Signal()
    def __init__(self,parent,db:Database):
        super().__init__(parent);self.db=db;self.setWindowTitle("Productos archivados");self.resize(680,400)
        root=QVBoxLayout(self);title=QLabel("Productos archivados");title.setObjectName("title");root.addWidget(title);note=QLabel("Los productos archivados conservan lotes, movimientos y trazabilidad. Puedes devolverlos al inventario activo. El borrado definitivo solo está disponible para registros vacíos creados por error.");note.setWordWrap(True);note.setObjectName("subtitle");root.addWidget(note)
        self.grid=table(["ID","Producto","Tipo","Stock","Ubicación"]);root.addWidget(self.grid,1);actions=QHBoxLayout();actions.addWidget(button("Restaurar seleccionado",self.restore,True));actions.addWidget(button("Borrar registro vacío",self.delete_empty,False,True));actions.addStretch();actions.addWidget(button("Cerrar",self.accept));root.addLayout(actions);self.refresh()
    def refresh(self):
        self.grid.setRowCount(0);labels={"medicine":"Medicamento","supply":"Insumo","equipment":"Equipo"}
        for r in self.db.query("SELECT id,name,type,stock,location FROM items WHERE archived=1 ORDER BY name"):set_row(self.grid,[r["id"],r["name"],labels.get(r["type"],r["type"]),r["stock"],r["location"]])
    def restore(self):
        item_id=selected_id(self.grid)
        if not item_id:QMessageBox.information(self,"Selecciona","Selecciona un producto archivado.");return
        self.db.restore_item(item_id);self.refresh();self.restored.emit()
    def delete_empty(self):
        item_id=selected_id(self.grid)
        if not item_id:QMessageBox.information(self,"Selecciona","Selecciona un producto archivado.");return
        name=self.db.query("SELECT name FROM items WHERE id=?",(item_id,))[0]["name"]
        message=(f"¿Borrar definitivamente el registro vacío «{name}»?\n\n"
                 "La aplicación impedirá el borrado si tiene existencias, movimientos o préstamos. Esta acción no puede deshacerse.")
        if QMessageBox.warning(self,"Borrar registro vacío",message,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        try:self.db.safe_delete_item(item_id);self.refresh();self.restored.emit()
        except Exception as exc:QMessageBox.warning(self,"Se conserva la trazabilidad",str(exc))


class ArchivedSeminariansDialog(QDialog):
    restored=Signal()
    def __init__(self,parent,db:Database):
        super().__init__(parent);self.db=db;self.setWindowTitle("Expedientes de salud archivados");self.resize(820,430)
        root=QVBoxLayout(self);title=QLabel("Expedientes archivados");title.setObjectName("title");root.addWidget(title)
        note=QLabel("Los expedientes archivados conservan sus datos de salud, movimientos y controles de salud. Puedes restaurarlos o eliminarlos definitivamente cuando la persona se haya retirado del Seminario.");note.setWordWrap(True);note.setObjectName("subtitle");root.addWidget(note)
        self.grid=table(["ID","Identificación","Seminarista","Año","Habitación","Diócesis"]);self.grid.doubleClicked.connect(self.restore);root.addWidget(self.grid,1)
        actions=QHBoxLayout();actions.addWidget(button("Restaurar expediente seleccionado",self.restore,True));actions.addWidget(button("Eliminar definitivamente",self.delete_permanently,False,True));actions.addStretch();actions.addWidget(button("Cerrar",self.accept));root.addLayout(actions);self.refresh()
    def refresh(self):
        self.grid.setRowCount(0)
        for r in self.db.query("SELECT id,external_id,first_name,last_name,formation_year,room,diocese FROM seminarians WHERE archived=1 ORDER BY last_name,first_name"):
            set_row(self.grid,[r["id"],r["external_id"] or "—",f"{r['first_name']} {r['last_name']}",r["formation_year"] or "—",r["room"] or "—",r["diocese"] or "—"])
        fit_table_height(self.grid,3,11)
    def restore(self,*_):
        seminarian_id=selected_id(self.grid)
        if not seminarian_id:QMessageBox.information(self,"Selecciona","Selecciona un expediente archivado.");return
        self.db.restore_seminarian(seminarian_id);self.refresh();self.restored.emit()
    def delete_permanently(self):
        seminarian_id=selected_id(self.grid)
        if not seminarian_id:QMessageBox.information(self,"Selecciona","Selecciona un expediente archivado.");return
        row=self.db.query("SELECT first_name,last_name FROM seminarians WHERE id=?",(seminarian_id,))[0];name=f"{row['first_name']} {row['last_name']}"
        message=(f"¿Eliminar definitivamente el expediente de «{name}»?\n\n"
                 "Se borrarán la fotografía, los datos de salud y todos sus controles de salud. Los movimientos de inventario conservarán fecha, producto y cantidad, pero quedarán anonimizados.\n\n"
                 "Las copias de seguridad antiguas podrían conservar una versión anterior. Esta acción no puede deshacerse.")
        if QMessageBox.warning(self,"Eliminación definitiva",message,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        confirmation,ok=QInputDialog.getText(self,"Confirmación final","Escribe ELIMINAR para confirmar:")
        if not ok:return
        if confirmation.strip().upper()!="ELIMINAR":QMessageBox.information(self,"No eliminado","La confirmación no coincide. No se modificó el expediente.");return
        try:
            result=self.db.delete_archived_seminarian(seminarian_id);self.refresh();self.restored.emit()
            QMessageBox.information(self,"Expediente eliminado",f"El expediente fue eliminado. Controles de salud borrados: {result['medical_controls']}. Movimientos anonimizados: {result['movements']}.")
        except Exception as exc:QMessageBox.warning(self,"No se pudo eliminar",str(exc))


SEMINARIAN_FIELDS = [
    ("external_id","Identificación"),("first_name","Nombres *"),("last_name","Apellidos *"),("birth_date","Fecha de nacimiento"),
    ("birth_city","Ciudad de nacimiento"),("birth_country","País de nacimiento"),("nationality","Nacionalidad"),
    ("diocese","Diócesis de procedencia"),("parish","Parroquia de procedencia"),
    ("address","Dirección"),("neighborhood","Barrio o sector"),("city","Ciudad de residencia"),("province","Provincia o estado"),("country","País de residencia"),
    ("personal_phone","Teléfono personal"),("email","Correo electrónico"),
    ("formation_year","Año de formación"),("room","Habitación"),("blood_type","Tipo de sangre"),("allergies","Alergias"),
    ("important_conditions","Condiciones médicas"),("permanent_medicines","Medicamentos permanentes"),("emergency_contact","Contacto de emergencia"),
    ("emergency_relation","Parentesco"),("emergency_phone","Teléfono de emergencia"),("health_center","Centro de salud"),
    ("insurance","Seguro médico"),("dietary_restrictions","Restricciones alimentarias"),("notes","Observaciones")]


class SeminarianDialog(QDialog):
    def __init__(self,parent,data=None):
        super().__init__(parent);self.setWindowTitle("Expediente de salud del seminarista");self.resize(700,650);self.setMinimumSize(500,420);data=dict(data or {})
        outer=QVBoxLayout(self);scroll,form=scrollable_form(self);outer.addWidget(scroll,1);self.fields={};self.photo_data=data.get("photo")
        photo_box=QWidget();photo_layout=QHBoxLayout(photo_box);photo_layout.setContentsMargins(0,0,0,8)
        self.photo_preview=QLabel();self.photo_preview.setFixedSize(125,155);self.photo_preview.setAlignment(Qt.AlignmentFlag.AlignCenter);self.photo_preview.setStyleSheet("border:1px solid #31536a;border-radius:10px;background:#102a3a;color:#9fb5c1")
        photo_actions=QVBoxLayout();photo_actions.addWidget(button("Añadir o cambiar foto",self.choose_photo,True));photo_actions.addWidget(button("Quitar foto",self.remove_photo));photo_actions.addStretch();photo_layout.addWidget(self.photo_preview);photo_layout.addLayout(photo_actions);photo_layout.addStretch();form.addRow("Fotografía",photo_box);self.update_photo_preview()
        long_fields={"allergies","important_conditions","permanent_medicines","dietary_restrictions","notes"}
        sections={"external_id":"Datos personales","diocese":"Procedencia eclesiástica","address":"Domicilio y contacto","formation_year":"Formación","blood_type":"Información sanitaria","emergency_contact":"Contacto de emergencia"}
        for key,label in SEMINARIAN_FIELDS:
            if key in sections:
                section=QLabel(sections[key]);section.setObjectName("sectionTitle");form.addRow(section)
            current=str(data.get(key, "") or "").strip()
            if key == "birth_date":
                widget=QDateEdit();widget.setLocale(QLocale(QLocale.Language.Spanish,QLocale.Country.Ecuador));widget.setCalendarPopup(True);widget.setDisplayFormat("dd MMM yyyy")
                widget.setMinimumDate(QDate(1900,1,1));widget.setMaximumDate(QDate.currentDate());widget.setSpecialValueText("No consta")
                saved=QDate.fromString(current,Qt.DateFormat.ISODate)
                widget.setDate(saved if saved.isValid() and saved <= QDate.currentDate() else widget.minimumDate())
            elif key in {"formation_year","blood_type"}:
                widget=QComboBox();widget.addItem("No consta","")
                options=FORMATION_STAGES if key == "formation_year" else BLOOD_TYPES
                for option in options:widget.addItem(option,option)
                index=widget.findData(current)
                if current and index < 0:widget.addItem(f"{current} · revisar",current);index=widget.count()-1
                widget.setCurrentIndex(max(0,index))
            else:
                widget=QTextEdit(current) if key in long_fields else QLineEdit(current)
            if isinstance(widget,QTextEdit): widget.setMaximumHeight(62)
            self.fields[key]=widget; form.addRow(label,widget)
        self.consent=QComboBox(); self.consent.addItem("No consta",0); self.consent.addItem("Sí",1); self.consent.setCurrentIndex(1 if data.get("consent") else 0); form.addRow("Consentimiento",self.consent)
        outer.addWidget(save_cancel_buttons(self,self.validate))

    def validate(self):
        if not self.fields["first_name"].text().strip() or not self.fields["last_name"].text().strip(): QMessageBox.warning(self,"Datos requeridos","Nombres y apellidos son obligatorios."); return
        self.accept()

    def values(self):
        out={}
        for key,w in self.fields.items():
            if isinstance(w,QTextEdit):out[key]=w.toPlainText()
            elif isinstance(w,QDateEdit):out[key]="" if w.date()==w.minimumDate() else w.date().toString(Qt.DateFormat.ISODate)
            elif isinstance(w,QComboBox):out[key]=w.currentData() or ""
            else:out[key]=w.text()
        out["consent"]=self.consent.currentData();out["photo"]=self.photo_data;return out

    def choose_photo(self):
        filename,_=QFileDialog.getOpenFileName(self,"Seleccionar fotografía","","Imágenes (*.jpg *.jpeg *.png *.webp)")
        if not filename:return
        image=QImage(filename)
        if image.isNull():QMessageBox.warning(self,"Imagen no válida","No se pudo leer la fotografía seleccionada.");return
        image=image.scaled(600,800,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
        payload=QByteArray();buffer=QBuffer(payload);buffer.open(QIODevice.OpenModeFlag.WriteOnly);image.save(buffer,"JPG",88);buffer.close()
        self.photo_data=bytes(payload);self.update_photo_preview()

    def remove_photo(self):
        self.photo_data=None;self.update_photo_preview()

    def update_photo_preview(self):
        if self.photo_data:
            pix=QPixmap();pix.loadFromData(self.photo_data);self.photo_preview.setPixmap(pix.scaled(self.photo_preview.size(),Qt.AspectRatioMode.KeepAspectRatioByExpanding,Qt.TransformationMode.SmoothTransformation))
            self.photo_preview.setText("")
        else:self.photo_preview.setPixmap(QPixmap());self.photo_preview.setText("Sin foto")


class MedicalControlDialog(QDialog):
    def __init__(self,parent,data=None):
        super().__init__(parent);data=dict(data or {});self.setWindowTitle("Editar control de salud" if data else "Nuevo control de salud");self.resize(620,610);self.setMinimumSize(500,420)
        root=QVBoxLayout(self);scroll,form=scrollable_form(self);root.addWidget(scroll,1)
        self.measured=QDateTimeEdit();self.measured.setCalendarPopup(True);self.measured.setDisplayFormat("dd/MM/yyyy HH:mm")
        parsed=QDateTime.fromString(str(data.get("measured_at", "")),Qt.DateFormat.ISODate);self.measured.setDateTime(parsed if parsed.isValid() else QDateTime.currentDateTime())
        def decimal(maximum,decimals=1,suffix=""):
            widget=QDoubleSpinBox();widget.setRange(0,maximum);widget.setDecimals(decimals);widget.setSpecialValueText("No registrado");widget.setSuffix(suffix);return widget
        def integer(maximum,suffix=""):
            widget=QSpinBox();widget.setRange(0,maximum);widget.setSpecialValueText("No registrado");widget.setSuffix(suffix);return widget
        self.weight=decimal(500,2," kg");self.height=decimal(260,1," cm")
        self.systolic=integer(300," mmHg");self.diastolic=integer(200," mmHg");self.pulse=integer(250," lpm")
        self.glucose=decimal(1000,1," mg/dL");self.glucose_context=QComboBox()
        for text,value in [("No especificado",""),("En ayunas","fasting"),("Después de comer","postprandial"),("Aleatoria","random")]:self.glucose_context.addItem(text,value)
        self.spo2=decimal(100,1," %");self.temperature=decimal(45,1," °C");self.notes=QTextEdit();self.notes.setMaximumHeight(85);self.referral=QLineEdit();self.recorded_by=QLineEdit()
        for widget,key in [(self.weight,"weight_kg"),(self.height,"height_cm"),(self.systolic,"systolic"),(self.diastolic,"diastolic"),(self.pulse,"pulse"),(self.glucose,"glucose_mg_dl"),(self.spo2,"oxygen_saturation"),(self.temperature,"temperature_c")]:
            if data.get(key) not in (None,""):widget.setValue(float(data[key]))
        idx=self.glucose_context.findData(data.get("glucose_context", ""));self.glucose_context.setCurrentIndex(max(0,idx))
        self.notes.setPlainText(str(data.get("notes","") or ""));self.referral.setText(str(data.get("referral","") or ""));self.recorded_by.setText(str(data.get("recorded_by","") or ""))
        for label,widget in [("Fecha y hora *",self.measured),("Peso",self.weight),("Estatura",self.height),("Presión sistólica",self.systolic),("Presión diastólica",self.diastolic),("Frecuencia cardíaca",self.pulse),("Glucosa",self.glucose),("Condición de glucosa",self.glucose_context),("Saturación de oxígeno",self.spo2),("Temperatura",self.temperature),("Síntomas u observaciones",self.notes),("Recomendación o derivación",self.referral),("Registrado por",self.recorded_by)]:form.addRow(label,widget)
        info=QLabel("Estos datos sirven para seguimiento y no constituyen un diagnóstico médico.");info.setWordWrap(True);info.setObjectName("subtitle");form.addRow(info)
        root.addWidget(save_cancel_buttons(self,self.accept))

    def values(self):
        return {"measured_at":self.measured.dateTime().toString(Qt.DateFormat.ISODate),"weight_kg":self.weight.value(),"height_cm":self.height.value(),
                "systolic":self.systolic.value(),"diastolic":self.diastolic.value(),"pulse":self.pulse.value(),"glucose_mg_dl":self.glucose.value(),
                "glucose_context":self.glucose_context.currentData(),"oxygen_saturation":self.spo2.value(),"temperature_c":self.temperature.value(),
                "notes":self.notes.toPlainText(),"referral":self.referral.text(),"recorded_by":self.recorded_by.text()}


class MedicalHistoryDialog(QDialog):
    changed=Signal()
    def __init__(self,parent,db:Database,seminarian_id:int,name:str):
        super().__init__(parent);self.db=db;self.seminarian_id=seminarian_id;self.setWindowTitle(f"Controles de salud · {name}");self.resize(1100,600);self.setMinimumSize(760,430)
        root=QVBoxLayout(self);root.setAlignment(Qt.AlignmentFlag.AlignTop);title=QLabel(f"Controles de salud de {name}");title.setObjectName("title");title.setMaximumHeight(48);root.addWidget(title);sub=QLabel("Historial cronológico de signos vitales y mediciones. Los registros anteriores se conservan.");sub.setObjectName("subtitle");sub.setMaximumHeight(38);root.addWidget(sub)
        self.grid=table(["ID","Fecha","Peso","Estatura","IMC","Presión","Pulso","Glucosa","Contexto","SpO₂","Temp.","Observaciones","Estado"]);root.addWidget(self.grid);self.grid.doubleClicked.connect(self.edit)
        actions=QHBoxLayout();actions.addWidget(button("+ Nuevo control",self.add,True));actions.addWidget(button("Editar seleccionado",self.edit));actions.addWidget(button("PDF del control seleccionado",self.export_control));actions.addWidget(button("PDF del historial",self.export_history));actions.addWidget(button("Anular registro",self.void,False,True));self.show_voided=QCheckBox("Mostrar anulados");self.show_voided.setToolTip("Los controles anulados se conservan únicamente para auditoría");self.show_voided.toggled.connect(self.refresh);actions.addWidget(self.show_voided);actions.addStretch();actions.addWidget(button("Cerrar",self.accept));root.addLayout(actions);root.addStretch();self.refresh()
    def refresh(self):
        self.grid.setRowCount(0);contexts={"fasting":"Ayunas","postprandial":"Después de comer","random":"Aleatoria","":"—"}
        sql="SELECT * FROM medical_controls WHERE seminarian_id=?"
        if not self.show_voided.isChecked():sql+=" AND voided_at IS NULL"
        sql+=" ORDER BY measured_at DESC,id DESC"
        for r in self.db.query(sql,(self.seminarian_id,)):
            pressure=f"{r['systolic']}/{r['diastolic']}" if r["systolic"] and r["diastolic"] else "—";state="Anulado" if r["voided_at"] else "Vigente"
            set_row(self.grid,[r["id"],r["measured_at"].replace("T"," ")[:16],r["weight_kg"] or "—",r["height_cm"] or "—",r["bmi"] or "—",pressure,r["pulse"] or "—",r["glucose_mg_dl"] or "—",contexts.get(r["glucose_context"],r["glucose_context"]),r["oxygen_saturation"] or "—",r["temperature_c"] or "—",r["notes"] or "—",state],{12:"#ef6a72" if r["voided_at"] else "#56d38a"})
        fit_table_height(self.grid,3,10)
    def add(self):
        dialog=MedicalControlDialog(self)
        if dialog.exec():
            try:self.db.save_medical_control(self.seminarian_id,dialog.values());self.refresh();self.changed.emit()
            except Exception as exc:QMessageBox.critical(self,"No se pudo completar",str(exc))
    def edit(self,*_):
        control_id=selected_id(self.grid)
        if not control_id:return
        row=self.db.query("SELECT * FROM medical_controls WHERE id=?",(control_id,))[0]
        if row["voided_at"]:QMessageBox.information(self,"Registro anulado","Un registro anulado no puede modificarse.");return
        dialog=MedicalControlDialog(self,row)
        if dialog.exec():
            try:self.db.save_medical_control(self.seminarian_id,dialog.values(),control_id);self.refresh();self.changed.emit()
            except Exception as exc:QMessageBox.critical(self,"No se pudo completar",str(exc))
    def void(self):
        control_id=selected_id(self.grid)
        if not control_id:return
        reason,ok=QInputDialog.getText(self,"Anular control","Motivo de la anulación:")
        if ok:
            try:self.db.void_medical_control(control_id,reason);self.refresh();self.changed.emit()
            except Exception as exc:QMessageBox.critical(self,"No se pudo completar",str(exc))
    def export_control(self):
        control_id=selected_id(self.grid)
        if not control_id:QMessageBox.information(self,"Selecciona","Selecciona el control que deseas exportar.");return
        filename,_=QFileDialog.getSaveFileName(self,"Exportar registro del control de salud","Control_de_Salud.pdf","PDF (*.pdf)")
        if filename:
            target=filename if filename.lower().endswith(".pdf") else filename+".pdf";export_control_pdf(self.db,control_id,target);self.db.log_action("medical_control_pdf_exported","medical_control",control_id,Path(target).name);QMessageBox.information(self,"Exportación completa","Se creó el registro PDF del control seleccionado.")
    def export_history(self):
        filename,_=QFileDialog.getSaveFileName(self,"Exportar historial de controles de salud","Historial_Controles_de_Salud.pdf","PDF (*.pdf)")
        if filename:
            target=filename if filename.lower().endswith(".pdf") else filename+".pdf";export_seminarian_dossier_pdf(self.db,self.seminarian_id,target);self.db.log_action("seminarian_dossier_exported","seminarian",self.seminarian_id,Path(target).name);QMessageBox.information(self,"Exportación completa","Se creó el expediente de salud con el historial de controles.")


class MovementDialog(QDialog):
    def __init__(self,parent,db:Database,movement_type:str):
        super().__init__(parent); self.db=db; self.kind=movement_type; labels={"delivery":"Entrega","administered":"Dosis administrada","discard":"Retiro"}; self.setWindowTitle(labels[movement_type]); self.resize(470,390)
        form=QFormLayout(self); self.item=QComboBox()
        if movement_type == "discard":
            products=db.query("SELECT id,name,stock available FROM items WHERE archived=0 AND stock>0 ORDER BY name")
        else:
            products=db.query("""SELECT i.id,i.name,i.stock-COALESCE(SUM(CASE WHEN l.quantity>0 AND (l.quarantined=1 OR (l.expires_on IS NOT NULL
                AND date(l.expires_on)<date('now','localtime'))) THEN l.quantity ELSE 0 END),0) available
                FROM items i LEFT JOIN lots l ON l.item_id=i.id WHERE i.archived=0 GROUP BY i.id HAVING available>0 ORDER BY i.name""")
        for r in products: self.item.addItem(f"{r['name']} · disponible {r['available']}",r["id"])
        self.sem=QComboBox(); self.sem.addItem("Seleccionar…",None)
        for r in db.query("SELECT id,first_name,last_name FROM seminarians WHERE archived=0 ORDER BY last_name,first_name"): self.sem.addItem(f"{r['first_name']} {r['last_name']}",r["id"])
        self.qty=QSpinBox(); self.qty.setRange(1,100000); self.dose=QLineEdit(); self.dose.setPlaceholderText("Ej.: 1 tableta de 500 mg")
        self.reason=QLineEdit(); form.addRow("Producto *",self.item)
        if movement_type in {"delivery","administered"}: form.addRow("Seminarista *",self.sem)
        form.addRow("Cantidad *",self.qty)
        if movement_type=="administered": form.addRow("Dosis",self.dose)
        self.safety=QLabel(""); self.safety.setWordWrap(True); self.safety.setObjectName("muted")
        if movement_type in {"delivery","administered"}: form.addRow("Revisión sanitaria",self.safety)
        form.addRow("Motivo u observación",self.reason)
        controls=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); controls.accepted.connect(self.validate); controls.rejected.connect(self.reject); form.addRow(controls)
        self.item.currentIndexChanged.connect(self.update_safety); self.sem.currentIndexChanged.connect(self.update_safety); self.update_safety()

    def update_safety(self):
        if self.kind not in {"delivery","administered"}: return
        message,match=self.db.medication_safety_notice(self.item.currentData(),self.sem.currentData())
        self.safety.setText(("⚠ POSIBLE COINCIDENCIA. " if match else "")+message)
        self.safety.setStyleSheet("color:#ef6a72;font-weight:700" if match else "color:#f1bd63")

    def validate(self):
        if self.item.currentData() is None:
            QMessageBox.warning(self,"Dato requerido","No hay un producto disponible seleccionado."); return
        if self.kind in {"delivery","administered"} and self.sem.currentData() is None:
            QMessageBox.warning(self,"Dato requerido","Selecciona al seminarista."); return
        message,match=self.db.medication_safety_notice(self.item.currentData(),self.sem.currentData())
        if match and QMessageBox.warning(self,"Revisar alergia",f"{message}\n\nEl nombre o genérico coincide con la alergia registrada. Este aviso no sustituye el criterio médico. ¿Registrar de todos modos?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:
            return
        self.accept()


class BasePage(QWidget):
    changed=Signal()
    notice=Signal(str)
    def __init__(self,db): super().__init__(); self.db=db
    def error(self,exc): QMessageBox.critical(self,"No se pudo completar",str(exc))
    def success(self,message): self.notice.emit(message)
    def preview_import(self,filename,importer,title):
        try:
            self.notice.emit("Leyendo el archivo y preparando la vista previa…");QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor);QApplication.processEvents()
            try:
                with TemporaryDirectory() as folder:
                    clone=Path(folder)/"preview.db";self.db.snapshot_to(clone);preview_db=Database(clone);result=importer(preview_db,filename)
            finally:QApplication.restoreOverrideCursor()
            if not ImportPreviewDialog(self,title,result).exec():return None
            self.notice.emit("Aplicando la importación…");QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor);QApplication.processEvents()
            try:return importer(self.db,filename)
            finally:QApplication.restoreOverrideCursor()
        except Exception as exc:self.error(exc);return None


class DashboardPage(BasePage):
    def __init__(self,db):
        super().__init__(db); self.layout=QVBoxLayout(self); self.layout.setContentsMargins(24,14,24,18); self.layout.setSpacing(10)
        content=QHBoxLayout();content.setSpacing(18);self.layout.addLayout(content,1)
        left=QWidget();left_layout=QVBoxLayout(left);left_layout.setContentsMargins(0,0,0,0);left_layout.setSpacing(10);content.addWidget(left,1)
        self.stats_grid=QGridLayout(); self.stats_grid.setHorizontalSpacing(10); self.stats_grid.setVerticalSpacing(10)
        for column in range(4): self.stats_grid.setColumnStretch(column,1)
        left_layout.addLayout(self.stats_grid)
        alerts_title=QLabel("Alertas prioritarias"); alerts_title.setObjectName("sectionTitle"); left_layout.addWidget(alerts_title)
        self.alerts=table(["Producto","Ubicación","Lote","Vencimiento","Cantidad","Estado"])
        for column,width in enumerate((170,95,90,115,85,135)):self.alerts.setColumnWidth(column,width)
        left_layout.addWidget(self.alerts);left_layout.addStretch()
        patron_panel=QWidget();patron_panel.setMinimumWidth(325);patron_panel.setMaximumWidth(385);patron_layout=QVBoxLayout(patron_panel);patron_layout.setContentsMargins(4,0,4,0);patron_layout.setSpacing(8)
        patron_layout.addStretch();image=QLabel();pix=QPixmap(str(ASSETS_DIR/"san_giuseppe_moscati.png"));image.setPixmap(pix.scaled(350,430,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation));image.setAlignment(Qt.AlignmentFlag.AlignCenter);image.setToolTip("San Giuseppe Moscati · Patrono de la Enfermería");patron_layout.addWidget(image)
        patron_name=QLabel("San Giuseppe Moscati");patron_name.setAlignment(Qt.AlignmentFlag.AlignCenter);patron_name.setStyleSheet("font-size:15px;font-weight:800;color:#60d5b7;background:transparent;");patron_layout.addWidget(patron_name)
        quote=QLabel("«No olviden que los enfermos son imágenes de Cristo. La ciencia humana nunca sustituirá al consuelo divino»." );quote.setWordWrap(True);quote.setAlignment(Qt.AlignmentFlag.AlignCenter);quote.setStyleSheet("font-size:13px;font-style:italic;color:#c7d9df;background:transparent;padding:4px;");patron_layout.addWidget(quote);patron_layout.addStretch();content.addWidget(patron_panel)
        self.cards=[]; self.refresh()
    def refresh(self):
        while self.stats_grid.count():
            w=self.stats_grid.takeAt(0).widget()
            if w:w.hide();w.setParent(None);w.deleteLater()
        s=self.db.stats(); cards=[("Productos",s["total"],"#56d38a"),("Stock bajo",s["low"],"#f1bd63"),("Vence pronto",s["expiring"],"#f1bd63"),("Vencidos",s["expired"],"#ef6a72"),("Cuarentena",s["quarantined"],"#ef6a72"),("Sin fecha",s["no_expiry"],"#f1bd63"),("Expedientes",s["seminarians"],"#60d5b7"),("Préstamos",s["loans"],"#60d5b7")]
        for i,(label,value,color) in enumerate(cards):
            frame=QFrame(); frame.setObjectName("card"); frame.setMaximumHeight(82); box=QVBoxLayout(frame); box.setContentsMargins(11,7,11,7); box.setSpacing(0)
            v=QLabel(str(value)); v.setObjectName("stat"); v.setStyleSheet(f"font-size:25px;color:{color};background:transparent;"); box.addWidget(v)
            m=QLabel(label); m.setObjectName("muted"); m.setStyleSheet("background:transparent;"); box.addWidget(m)
            self.stats_grid.addWidget(frame,i//4,i%4)
        self.alerts.setRowCount(0)
        for r in self.db.expiry_alerts():
            days=r["days"]
            if r["quarantined"]:status=f"Cuarentena: {r['quarantine_reason'] or 'Revisar'}";color="#ef6a72"
            else:status=f"Vencido hace {abs(days)} días" if days<0 else f"Vence en {days} días";color="#ef6a72" if days<0 else "#f1bd63"
            set_row(self.alerts,[r["name"],r["location"] or "Por asignar",r["lot_number"] or "—",r["expires_on"],r["quantity"],status],{5:color})
        if not self.alerts.rowCount():
            set_row(self.alerts,["Sin alertas prioritarias","","","","",""] ,{0:"#56d38a"}); self.alerts.setSpan(0,0,1,6)
        fit_table_height(self.alerts,1,8)


class InventoryPage(BasePage):
    def __init__(self,db):
        super().__init__(db); root=QVBoxLayout(self);add_page_header(root,"Inventario","Medicamentos, insumos y equipos con control de stock, ubicación, lotes y vencimiento.");top=QHBoxLayout(); self.search=QLineEdit(); self.search.setPlaceholderText("Buscar medicamento, insumo, equipo o ubicación…"); self.search.textChanged.connect(self.refresh); top.addWidget(self.search,1)
        top.addWidget(button("+ Producto",self.add,True)); top.addWidget(button("+ Existencia",self.stock)); top.addWidget(button("Importar",self.import_file)); top.addWidget(button("Exportar",self.export_file)); root.addLayout(top)
        self.grid=table(["ID","Producto","Tipo","Ubicación","Stock","Cuarentena","Mínimo","Vence","Estado","Uso"]);self.grid.doubleClicked.connect(self.edit);root.addWidget(self.grid)
        actions=QHBoxLayout(); actions.addWidget(button("Editar",self.edit));actions.addWidget(button("Gestionar lotes",self.lots));actions.addWidget(button("Retirar vencidos",self.retire_expired,False,True));actions.addWidget(button("Eliminar del inventario",self.delete,False,True));actions.addStretch();actions.addWidget(button("Ver eliminados / archivados",self.archived));root.addLayout(actions);root.addStretch(); self.refresh()
    def refresh(self,*_):
        self.grid.setRowCount(0); today=date.today()
        for r in self.db.inventory(self.search.text() if hasattr(self,"search") else ""):
            exp=r["earliest_expiry"] or "—"; stock=r["stock"]
            usable=stock-r["quarantined_stock"]
            if stock==0: state="Agotado"; color="#ef6a72"
            elif usable<=r["minimum_stock"]: state="Stock utilizable bajo"; color="#f1bd63"
            else: state="Disponible"; color="#56d38a"
            if r["earliest_expiry"]:
                days=(date.fromisoformat(r["earliest_expiry"])-today).days
                if days<0: state="Vencido"; color="#ef6a72"
                elif days<=90: state="Vence pronto"; color="#f1bd63"
            type_label={"medicine":"Medicamento","supply":"Insumo","equipment":"Equipo"}.get(r["type"],r["type"])
            set_row(self.grid,[r["id"],r["name"],type_label,r["location"],stock,r["quarantined_stock"],r["minimum_stock"],exp,state,r["usage"]],{8:color,5:"#ef6a72" if r["quarantined_stock"] else "#a9bdc7"})
        fit_table_height(self.grid,3,13)
    def add(self):
        d=ItemDialog(self)
        if d.exec():
            try:self.db.create_item_with_initial_stock(d.values(),*d.initial_stock());self.refresh();self.changed.emit();self.success("Producto y existencia inicial guardados")
            except Exception as exc:self.error(exc)
    def edit(self,*_):
        item_id=selected_id(self.grid)
        if not item_id: return
        data=self.db.query("SELECT * FROM items WHERE id=?",(item_id,))[0]; d=ItemDialog(self,data)
        if d.exec(): self.db.save_item(d.values(),item_id); self.refresh(); self.changed.emit();self.success("Producto actualizado")
    def stock(self):
        item_id=selected_id(self.grid)
        if not item_id: QMessageBox.information(self,"Selecciona","Selecciona un producto."); return
        name=self.db.query("SELECT name FROM items WHERE id=?",(item_id,))[0]["name"]; d=StockDialog(self,name)
        if d.exec():
            try: self.db.add_stock(item_id,*d.values()); self.refresh(); self.changed.emit();self.success("Existencia registrada")
            except Exception as e: self.error(e)
    def lots(self):
        item_id=selected_id(self.grid)
        if not item_id:QMessageBox.information(self,"Selecciona","Selecciona un producto.");return
        name=self.db.query("SELECT name FROM items WHERE id=?",(item_id,))[0]["name"];dialog=LotsDialog(self,self.db,item_id,name);dialog.exec();self.refresh();self.changed.emit();self.success("Gestión de lotes actualizada")
    def retire_expired(self):
        item_id=selected_id(self.grid)
        if not item_id:QMessageBox.information(self,"Selecciona","Selecciona un producto.");return
        rows=self.db.query("""SELECT i.name,COUNT(l.id) lots,COALESCE(SUM(l.quantity),0) quantity FROM items i
            LEFT JOIN lots l ON l.item_id=i.id AND l.quantity>0 AND l.expires_on IS NOT NULL
            AND date(l.expires_on)<date('now','localtime') WHERE i.id=? GROUP BY i.id""",(item_id,))
        if not rows or not rows[0]["lots"]:QMessageBox.information(self,"Sin lotes vencidos","El producto seleccionado no tiene lotes vencidos con existencias.");return
        row=rows[0];message=(f"Se retirarán {row['quantity']} unidades distribuidas en {row['lots']} lote(s) vencido(s) de «{row['name']}».\n\n"
                            "Quedará un movimiento auditable por cada lote y podrá anularse desde Movimientos. ¿Continuar?")
        if QMessageBox.warning(self,"Retirar lotes vencidos",message,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        try:
            result=self.db.discard_expired_lots(item_id,"Producto vencido");self.refresh();self.changed.emit();self.success(f"Retirados {result['quantity']} unidades de {result['lots']} lote(s) vencido(s)")
        except Exception as exc:self.error(exc)
    def archived(self):
        dialog=ArchivedItemsDialog(self,self.db);dialog.restored.connect(lambda:(self.refresh(),self.changed.emit(),self.success("Producto restaurado")));dialog.exec()
    def archive(self):
        item_id=selected_id(self.grid)
        if item_id and QMessageBox.question(self,"Archivar","Se ocultará del inventario activo, pero conservará su historial.")==QMessageBox.StandardButton.Yes: self.db.archive_item(item_id); self.refresh(); self.changed.emit();self.success("Producto archivado")
    def delete(self):
        item_id=selected_id(self.grid)
        if not item_id:QMessageBox.information(self,"Selecciona","Selecciona un producto.");return
        row=self.db.query("SELECT name,stock FROM items WHERE id=?",(item_id,))[0]
        message=(f"¿Eliminar «{row['name']}» del inventario activo?\n\n"
                 "Desaparecerá de esta lista, pero se conservarán sus movimientos y podrá restaurarse desde "
                 "«Ver eliminados / archivados».")
        if row["stock"]>0:message+=f"\n\nAviso: conserva {row['stock']} unidades registradas."
        if QMessageBox.question(self,"Eliminar del inventario",message)==QMessageBox.StandardButton.Yes:
            self.db.archive_item(item_id);self.refresh();self.changed.emit();self.success("Producto retirado del inventario activo; historial conservado")
    def import_file(self):
        filename,_=QFileDialog.getOpenFileName(self,"Importar inventario","","Excel (*.xlsx)")
        if filename:
            r=self.preview_import(filename,import_inventory,"Vista previa del inventario")
            if r:self.refresh();self.changed.emit();self.success(f"Importación completada: {r['created']} nuevos y {r['updated']} actualizados")
    def export_file(self):
        filename,_=QFileDialog.getSaveFileName(self,"Exportar","Inventario_Enfermeria.xlsx","Excel (*.xlsx)")
        if filename: export_inventory(self.db,filename if filename.endswith(".xlsx") else filename+".xlsx");self.db.log_action("inventory_exported","export",None,Path(filename).name);self.success("Inventario exportado")


class SeminariansPage(BasePage):
    def __init__(self,db):
        super().__init__(db); root=QVBoxLayout(self);add_page_header(root,"Expedientes de salud","Información esencial y confidencial para una atención responsable de los seminaristas.");top=QHBoxLayout(); self.search=QLineEdit(); self.search.setPlaceholderText("Buscar por nombre, identificación, diócesis, ciudad o país…"); self.search.textChanged.connect(self.refresh); top.addWidget(self.search,1); top.addWidget(button("+ Nuevo expediente",self.add,True)); top.addWidget(button("Importar respuestas",self.import_file)); top.addWidget(button("Exportar Excel",self.export_file));top.addWidget(button("Expedientes en PDF",self.export_all_pdf,True)); root.addLayout(top)
        filters=QHBoxLayout();filters.addWidget(QLabel("Etapa:"));self.stage_filter=QComboBox();self.stage_filter.addItem("Todas","");
        for stage in FORMATION_STAGES:self.stage_filter.addItem(stage,stage)
        self.stage_filter.currentIndexChanged.connect(self.refresh);filters.addWidget(self.stage_filter);filters.addWidget(QLabel("Diócesis:"));self.diocese_filter=QComboBox();self.diocese_filter.currentIndexChanged.connect(self.refresh);filters.addWidget(self.diocese_filter);self.allergy_status=QComboBox();self.allergy_status.addItem("Todas las alergias","");self.allergy_status.addItem("Con alergias registradas","with");self.allergy_status.addItem("Sin alergias registradas","without");self.allergy_status.currentIndexChanged.connect(self.refresh);filters.addWidget(self.allergy_status);self.allergy_text=QLineEdit();self.allergy_text.setPlaceholderText("Buscar alergia específica…");self.allergy_text.textChanged.connect(self.refresh);filters.addWidget(self.allergy_text,1);root.addLayout(filters)
        self.grid=table(["ID","Foto","Seminarista","Año","Habitación","Diócesis","Sangre","Alergias","Teléfono"]);self.grid.setIconSize(QSize(44,44));self.grid.doubleClicked.connect(self.edit);root.addWidget(self.grid);actions=QHBoxLayout();actions.addWidget(button("Editar expediente",self.edit));actions.addWidget(button("Controles de salud",self.medical_controls,True));actions.addWidget(button("Resumen de emergencia",self.export_emergency_pdf,True));actions.addWidget(button("Exportar expediente PDF",self.export_selected_pdf));actions.addWidget(button("Archivar expediente",self.archive));actions.addStretch();actions.addWidget(button("Ver expedientes archivados",self.archived));root.addLayout(actions);root.addStretch();self.reload_dioceses();self.refresh()
    def reload_dioceses(self):
        current=self.diocese_filter.currentData() if self.diocese_filter.count() else "";self.diocese_filter.blockSignals(True);self.diocese_filter.clear();self.diocese_filter.addItem("Todas","")
        for r in self.db.query("SELECT DISTINCT diocese FROM seminarians WHERE archived=0 AND trim(diocese)<>'' ORDER BY diocese COLLATE NOCASE"):self.diocese_filter.addItem(r["diocese"],r["diocese"])
        self.diocese_filter.setCurrentIndex(max(0,self.diocese_filter.findData(current)));self.diocese_filter.blockSignals(False)
    def refresh(self,*_):
        self.grid.setRowCount(0); term=f"%{self.search.text()}%" if hasattr(self,"search") else "%";where=["archived=0","(first_name LIKE ? OR last_name LIKE ? OR external_id LIKE ? OR diocese LIKE ? OR city LIKE ? OR birth_city LIKE ? OR country LIKE ? OR birth_country LIKE ?)"];params=list((term,)*8)
        stage=self.stage_filter.currentData() if hasattr(self,"stage_filter") else "";diocese=self.diocese_filter.currentData() if hasattr(self,"diocese_filter") else "";allergy_status=self.allergy_status.currentData() if hasattr(self,"allergy_status") else "";allergy_text=self.allergy_text.text().strip() if hasattr(self,"allergy_text") else ""
        if stage:where.append("formation_year=?");params.append(stage)
        if diocese:where.append("diocese=?");params.append(diocese)
        if allergy_status=="with":where.append("trim(allergies)<>'' AND lower(trim(allergies)) NOT IN ('ninguna','ninguna conocida','no','n/a','ninguno')")
        elif allergy_status=="without":where.append("(trim(allergies)='' OR lower(trim(allergies)) IN ('ninguna','ninguna conocida','no','n/a','ninguno'))")
        if allergy_text:where.append("allergies LIKE ?");params.append(f"%{allergy_text}%")
        for r in self.db.query("SELECT * FROM seminarians WHERE "+" AND ".join(where)+" ORDER BY last_name,first_name",params):
            set_row(self.grid,[r["id"],"",f"{r['first_name']} {r['last_name']}",r["formation_year"],r["room"],r["diocese"],r["blood_type"],r["allergies"],r["personal_phone"] or r["emergency_phone"]])
            row_index=self.grid.rowCount()-1;self.grid.setRowHeight(row_index,52)
            if r["photo"]:
                pix=QPixmap();pix.loadFromData(r["photo"]);item=self.grid.item(row_index,1);item.setIcon(QIcon(pix));item.setSizeHint(QSize(48,48))
        fit_table_height(self.grid,3,13)
    def add(self):
        d=SeminarianDialog(self)
        if d.exec():
            values=d.values(); matches=self.db.possible_seminarian_duplicates(values)
            if matches:
                names="\n".join(f"• {r['first_name']} {r['last_name']} · nacimiento {r['birth_date'] or 'sin fecha'}" for r in matches)
                if values.get("external_id") and any(r["external_id"]==values["external_id"].strip() for r in matches):
                    QMessageBox.warning(self,"Expediente existente",f"Ya existe un expediente con esa identificación:\n{names}\n\nAbre el expediente existente y elige Editar."); return
                if QMessageBox.warning(self,"Posible duplicado",f"Encontré un expediente parecido:\n{names}\n\n¿Crear otro expediente independiente?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
            try:self.db.insert_seminarian(values);self.reload_dioceses();self.refresh();self.changed.emit();self.success("Expediente de salud creado")
            except Exception as e:self.error(e)
    def edit(self,*_):
        sem_id=selected_id(self.grid)
        if not sem_id:return
        data=self.db.query("SELECT * FROM seminarians WHERE id=?",(sem_id,))[0];d=SeminarianDialog(self,data)
        if d.exec():
            values=d.values();values["external_id"]=values["external_id"] or data["external_id"]
            try:
                self.db.update_seminarian(sem_id,values);self.reload_dioceses();self.refresh();self.changed.emit();self.success("Expediente de salud actualizado")
            except Exception as e:self.error(e)
    def medical_controls(self,*_):
        sem_id=selected_id(self.grid)
        if not sem_id:QMessageBox.information(self,"Selecciona","Selecciona un seminarista.");return
        row=self.db.query("SELECT first_name,last_name FROM seminarians WHERE id=?",(sem_id,))[0];dialog=MedicalHistoryDialog(self,self.db,sem_id,f"{row['first_name']} {row['last_name']}")
        dialog.changed.connect(lambda:(self.changed.emit(),self.success("Control de salud actualizado")));dialog.exec()
    def archive(self):
        sem_id=selected_id(self.grid)
        if sem_id and QMessageBox.question(self,"Archivar expediente","El expediente se ocultará, pero sus atenciones conservarán el nombre histórico.")==QMessageBox.StandardButton.Yes:self.db.archive_seminarian(sem_id);self.refresh();self.changed.emit();self.success("Expediente archivado")
    def archived(self):
        dialog=ArchivedSeminariansDialog(self,self.db);dialog.restored.connect(lambda:(self.refresh(),self.changed.emit(),self.success("Expediente restaurado")));dialog.exec()
    def import_file(self):
        filename,_=QFileDialog.getOpenFileName(self,"Importar respuestas de Google Forms o expedientes","","Excel (*.xlsx)")
        if filename:
            r=self.preview_import(filename,import_seminarians,"Vista previa de expedientes")
            if r:self.reload_dioceses();self.refresh();self.changed.emit();self.success(f"Importación completada: {r['created']} nuevas, {r['updated']} actualizadas, {r['review']} para revisión")
    def export_file(self):
        filename,_=QFileDialog.getSaveFileName(self,"Exportar expedientes de salud","Expedientes_de_Salud.xlsx","Excel (*.xlsx)")
        if filename: export_seminarians(self.db,filename if filename.endswith(".xlsx") else filename+".xlsx");self.db.log_action("seminarians_exported","export",None,Path(filename).name);self.success("Expedientes de salud exportados")
    def export_selected_pdf(self):
        sem_id=selected_id(self.grid)
        if not sem_id:QMessageBox.information(self,"Selecciona","Selecciona un seminarista.");return
        filename,_=QFileDialog.getSaveFileName(self,"Exportar expediente de salud","Expediente_de_Salud.pdf","PDF (*.pdf)")
        if filename:
            target=filename if filename.lower().endswith(".pdf") else filename+".pdf";export_seminarian_dossier_pdf(self.db,sem_id,target);self.db.log_action("seminarian_dossier_exported","seminarian",sem_id,Path(target).name);self.success("Expediente de salud exportado en PDF")
    def export_emergency_pdf(self):
        sem_id=selected_id(self.grid)
        if not sem_id:QMessageBox.information(self,"Selecciona","Selecciona un seminarista.");return
        filename,_=QFileDialog.getSaveFileName(self,"Resumen de salud para emergencias","Resumen_Salud_Emergencias.pdf","PDF (*.pdf)")
        if filename:
            target=filename if filename.lower().endswith(".pdf") else filename+".pdf";manager=self.db.get_setting("manager_name","")
            export_emergency_summary_pdf(self.db,sem_id,target,manager);self.db.log_action("emergency_summary_exported","seminarian",sem_id,{"file":Path(target).name,"generated_by":manager});self.success("Resumen de salud para emergencias exportado y registrado en auditoría")
    def export_all_pdf(self):
        filename,_=QFileDialog.getSaveFileName(self,"Exportar todos los expedientes de salud","Expedientes_de_Salud.pdf","PDF (*.pdf)")
        if filename:
            target=filename if filename.lower().endswith(".pdf") else filename+".pdf";export_all_dossiers_pdf(self.db,target);self.db.log_action("all_dossiers_exported","export",None,Path(target).name);self.success("PDF general exportado por seminarista")


class MovementsPage(BasePage):
    def __init__(self,db):
        super().__init__(db);root=QVBoxLayout(self);add_page_header(root,"Movimientos","Historial trazable de entradas, entregas, dosis, retiros y anulaciones.");top=QHBoxLayout();top.addWidget(button("Registrar entrega",lambda:self.new("delivery"),True));top.addWidget(button("Registrar dosis",lambda:self.new("administered"),True));top.addWidget(button("Retirar stock",lambda:self.new("discard"),False,True));top.addWidget(button("Exportar",self.export_file));top.addStretch();root.addLayout(top)
        self.grid=table(["ID","Fecha","Tipo","Producto","Seminarista","Cantidad","Dosis","Motivo","Estado"]);root.addWidget(self.grid);actions=QHBoxLayout();actions.addWidget(button("Anular movimiento",self.void_selected,False,True));actions.addStretch();root.addLayout(actions);root.addStretch();self.refresh()
    def refresh(self):
        self.grid.setRowCount(0); labels={"entry":"Entrada","delivery":"Entrega","administered":"Dosis","discard":"Retiro","return":"Devolución","adjustment":"Ajuste","loan":"Préstamo","reversal":"Anulación"}
        for r in self.db.query("""SELECT m.id,m.occurred_at,m.type,i.name product,
            CASE WHEN s.id IS NOT NULL THEN s.first_name||' '||s.last_name WHEN m.type IN ('delivery','administered','loan','return') THEN 'Expediente eliminado' ELSE '—' END sem,
            m.quantity,m.dose,m.reason,m.voided_at FROM movements m JOIN items i ON i.id=m.item_id
            LEFT JOIN seminarians s ON s.id=m.seminarian_id ORDER BY m.occurred_at DESC,m.id DESC LIMIT 500"""):
            state="Anulado" if r["voided_at"] else "Vigente"; set_row(self.grid,[r["id"],r["occurred_at"].replace("T"," ")[:16],labels.get(r["type"],r["type"]),r["product"],r["sem"],r["quantity"],r["dose"],r["reason"],state],{8:"#ef6a72" if r["voided_at"] else "#56d38a"})
        fit_table_height(self.grid,3,13)
    def new(self,kind):
        d=MovementDialog(self,self.db,kind)
        if d.exec():
            try:self.db.record_output(d.item.currentData(),d.qty.value(),kind,d.sem.currentData(),d.dose.text(),d.reason.text());self.refresh();self.changed.emit();self.success("Movimiento registrado")
            except Exception as e:self.error(e)
    def void_selected(self):
        movement_id=selected_id(self.grid)
        if not movement_id:return
        reason,ok=QInputDialog.getText(self,"Anular movimiento","Motivo de la anulación:")
        if ok:
            try:self.db.void_movement(movement_id,reason);self.refresh();self.changed.emit();self.success("Movimiento anulado y existencias restauradas")
            except Exception as e:self.error(e)
    def export_file(self):
        filename,_=QFileDialog.getSaveFileName(self,"Exportar movimientos","Movimientos_Enfermeria.xlsx","Excel (*.xlsx)")
        if filename: export_movements(self.db,filename if filename.endswith(".xlsx") else filename+".xlsx");self.db.log_action("movements_exported","export",None,Path(filename).name);self.success("Movimientos exportados")


class EquipmentPage(BasePage):
    def __init__(self,db):
        super().__init__(db);root=QVBoxLayout(self);add_page_header(root,"Equipos médicos","Control de existencias, préstamos activos y devoluciones de equipos.");top=QHBoxLayout();top.addWidget(button("Registrar préstamo",self.loan,True));top.addWidget(button("Marcar devolución",self.return_item));top.addStretch();root.addLayout(top);self.grid=table(["ID","Equipo","Seminarista","Cantidad","Prestado","Retorno esperado","Estado","Observaciones"]);root.addWidget(self.grid);root.addStretch();self.refresh()
    def refresh(self):
        self.grid.setRowCount(0)
        for r in self.db.query("""SELECT e.id,i.name,COALESCE(s.first_name||' '||s.last_name,'Expediente eliminado') sem,e.quantity,e.lent_at,e.expected_return,e.returned_at,e.notes FROM equipment_loans e JOIN items i ON i.id=e.item_id LEFT JOIN seminarians s ON s.id=e.seminarian_id ORDER BY e.lent_at DESC"""):
            set_row(self.grid,[r["id"],r["name"],r["sem"],r["quantity"],r["lent_at"][:10],r["expected_return"] or "—","Devuelto" if r["returned_at"] else "Prestado",r["notes"]],{6:"#56d38a" if r["returned_at"] else "#f1bd63"})
        fit_table_height(self.grid,3,13)
    def loan(self):
        dialog=QDialog(self);dialog.setWindowTitle("Préstamo de equipo");form=QFormLayout(dialog);item=QComboBox();sem=QComboBox();qty=QSpinBox();qty.setRange(1,100);expected=QDateEdit(QDate.currentDate().addDays(7));expected.setCalendarPopup(True);notes=QLineEdit()
        for r in self.db.query("SELECT id,name,stock FROM items WHERE archived=0 AND type='equipment' AND stock>0 ORDER BY name"):item.addItem(f"{r['name']} · disponibles {r['stock']}",r["id"])
        for r in self.db.query("SELECT id,first_name,last_name FROM seminarians WHERE archived=0 ORDER BY last_name"):sem.addItem(f"{r['first_name']} {r['last_name']}",r["id"])
        for l,w in [("Equipo",item),("Seminarista",sem),("Cantidad",qty),("Retorno esperado",expected),("Observaciones",notes)]:form.addRow(l,w)
        c=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);c.accepted.connect(dialog.accept);c.rejected.connect(dialog.reject);form.addRow(c)
        if dialog.exec():
            try:
                self.db.create_equipment_loan(item.currentData(),sem.currentData(),qty.value(),expected.date().toString("yyyy-MM-dd"),notes.text());self.refresh();self.changed.emit();self.success("Préstamo registrado")
            except Exception as e:self.error(e)
    def return_item(self):
        loan_id=selected_id(self.grid)
        if not loan_id:return
        try:self.db.return_equipment_loan(loan_id);self.refresh();self.changed.emit();self.success("Devolución registrada")
        except Exception as e:self.error(e)


class ConfigurationPage(BasePage):
    def __init__(self,db):
        super().__init__(db);root=QVBoxLayout(self);add_page_header(root,"Configuración y seguridad","Identidad institucional, acceso del encargado, copias de seguridad y auditoría.")
        self.tabs=QTabWidget();root.addWidget(self.tabs,1)
        self.general=QWidget();form=QFormLayout(self.general);self.clinic=QLineEdit();self.institution=QLineEdit();self.manager=QLineEdit();self.supervisor=QLineEdit();form.addRow("Nombre de la enfermería",self.clinic);form.addRow("Institución",self.institution);form.addRow("Encargado",self.manager);form.addRow("Responsable de recuperación del PIN",self.supervisor);supervisor_note=QLabel("Debe ser una persona institucional distinta del encargado cuando sea posible.");supervisor_note.setObjectName("subtitle");supervisor_note.setWordWrap(True);form.addRow("",supervisor_note);form.addRow(button("Guardar configuración",self.save_settings,True));self.tabs.addTab(self.general,"General")

        security=QWidget();sec=QVBoxLayout(security);group=QGroupBox("Acceso del encargado");g=QVBoxLayout(group);self.pin_state=QLabel();self.pin_state.setObjectName("subtitle");g.addWidget(self.pin_state);g.addWidget(QLabel("El PIN bloquea la interfaz. Las copias y transferencias pueden cifrarse con AES-256; la base activa permanece local y protegida por permisos del sistema."));row=QHBoxLayout();row.addWidget(button("Establecer o cambiar PIN",self.change_pin,True));row.addWidget(button("Recuperar PIN de forma supervisada",self.recover_pin));row.addWidget(button("Quitar PIN",self.remove_pin));row.addStretch();g.addLayout(row);sec.addWidget(group);sec.addStretch();self.tabs.addTab(security,"Acceso")

        backups=QWidget();bl=QVBoxLayout(backups);self.db_path=QLabel();self.db_path.setWordWrap(True);self.db_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse);bl.addWidget(self.db_path);controls=QHBoxLayout();controls.addWidget(button("Crear copia local",self.backup_now));controls.addWidget(button("Guardar copia cifrada…",self.backup_encrypted,True));controls.addWidget(button("Restaurar copia cifrada…",self.restore_encrypted));controls.addWidget(button("Restaurar copia local…",self.restore));controls.addWidget(button("Abrir carpeta de datos",self.open_data_folder));controls.addStretch();bl.addLayout(controls);self.backup_table=table(["Copia local","Fecha","Tamaño"]);bl.addWidget(self.backup_table,1);self.tabs.addTab(backups,"Copias")

        transfer=QWidget();tl=QVBoxLayout(transfer);transfer_info=QLabel("Genera un paquete institucional cifrado con la base, configuración, manifiesto y manual de entrega. Comunica la contraseña al nuevo encargado por un canal distinto al archivo.");transfer_info.setWordWrap(True);transfer_info.setObjectName("subtitle");tl.addWidget(transfer_info);transfer_actions=QHBoxLayout();transfer_actions.addWidget(button("Exportar transferencia cifrada…",self.export_transfer,True));transfer_actions.addWidget(button("Importar transferencia cifrada…",self.import_transfer));transfer_actions.addStretch();tl.addLayout(transfer_actions);tl.addStretch();self.tabs.addTab(transfer,"Transferencia")

        panel=QWidget();pl=QVBoxLayout(panel);panel_info=QLabel("El Panel rápido muestra vencimientos, stock bajo y equipos prestados. Consulta la misma base únicamente en modo de lectura y no presenta nombres ni datos de salud de los seminaristas.");panel_info.setWordWrap(True);panel_info.setObjectName("subtitle");pl.addWidget(panel_info)
        panel_actions=QHBoxLayout();panel_actions.addWidget(button("Mostrar panel rápido",self.open_quick_panel,True));panel_actions.addWidget(button("Actualizar estado",self.refresh_panel_settings));panel_actions.addStretch();pl.addLayout(panel_actions)
        self.panel_autostart=QCheckBox("Iniciar el Panel rápido al entrar en el sistema");self.panel_autostart.toggled.connect(self.change_panel_autostart);pl.addWidget(self.panel_autostart)
        self.panel_state=QLabel();self.panel_state.setObjectName("subtitle");self.panel_state.setWordWrap(True);pl.addWidget(self.panel_state);pl.addStretch();self.tabs.addTab(panel,"Panel rápido")

        linux=QWidget();ll=QVBoxLayout(linux);linux_info=QLabel("Opciones exclusivas de Linux Mint. No modifican la base, el PIN, el código institucional ni las claves de las copias cifradas.");linux_info.setWordWrap(True);linux_info.setObjectName("subtitle");ll.addWidget(linux_info)
        self.linux_fullscreen=QCheckBox("Abrir Enfermería en pantalla completa");self.linux_fullscreen.toggled.connect(self.change_linux_fullscreen);ll.addWidget(self.linux_fullscreen)
        self.linux_workspace=QCheckBox("Mover Enfermería al área de trabajo 2 al abrir");self.linux_workspace.toggled.connect(self.change_linux_workspace);ll.addWidget(self.linux_workspace)
        self.linux_notifications=QCheckBox("Activar notificaciones automáticas de vencimientos, stock y préstamos");self.linux_notifications.toggled.connect(self.change_linux_notifications);ll.addWidget(self.linux_notifications)
        notification_actions=QHBoxLayout();notification_actions.addWidget(button("Probar notificación",self.test_linux_notification));notification_actions.addStretch();ll.addLayout(notification_actions)
        self.linux_state=QLabel();self.linux_state.setObjectName("subtitle");self.linux_state.setWordWrap(True);ll.addWidget(self.linux_state);ll.addStretch();self.tabs.addTab(linux,"Linux")

        self.web_sync=WebSyncPage(db);self.tabs.addTab(self.web_sync,"Portal web")

        audit=QWidget();al=QVBoxLayout(audit);audit_top=QHBoxLayout();audit_top.addWidget(QLabel("Últimas 500 operaciones registradas"));audit_top.addStretch();audit_top.addWidget(button("Actualizar",self.refresh_audit));al.addLayout(audit_top);self.audit_table=table(["Fecha","Acción","Tipo","ID","Detalle"]);al.addWidget(self.audit_table,1);self.tabs.addTab(audit,"Auditoría")

        reset=QWidget();rl=QVBoxLayout(reset);danger=QGroupBox("Zona de peligro");dl=QVBoxLayout(danger);purge_text=QLabel("Usa esta opción al terminar tus pruebas y antes de comenzar con los datos reales. El proceso elimina permanentemente toda la información operativa y puede borrar también las copias locales.");purge_text.setWordWrap(True);purge_text.setObjectName("subtitle");dl.addWidget(purge_text);purge_button=button("Purgar todos los datos de prueba…",self.purge_data,False,True);purge_button.setMaximumWidth(330);dl.addWidget(purge_button);rl.addWidget(danger);rl.addStretch();self.tabs.addTab(reset,"Restablecer")

        about=QWidget();ab=QHBoxLayout(about);image=QLabel();pix=QPixmap(str(ASSETS_DIR/"san_giuseppe_moscati.png"));image.setPixmap(pix.scaledToHeight(430,Qt.TransformationMode.SmoothTransformation));image.setAlignment(Qt.AlignmentFlag.AlignCenter);ab.addWidget(image);text=QVBoxLayout();title=QLabel("Enfermería San Giuseppe Moscati");title.setObjectName("title");text.addWidget(title);description=QLabel(f"Versión {__version__}\n\nAplicación local para el cuidado sanitario, el control responsable de medicamentos y la trazabilidad de Enfermería.\n\nPatrono: San Giuseppe Moscati.\n\nLa aplicación ofrece avisos de seguridad, pero no diagnostica ni sustituye el criterio médico.");description.setWordWrap(True);description.setObjectName("subtitle");text.addWidget(description);text.addStretch();ab.addLayout(text,1);self.tabs.addTab(about,"Acerca de")
        self.refresh()

    def refresh(self):
        self.clinic.setText(self.db.get_setting("clinic_name","Enfermería San Giuseppe Moscati"));self.institution.setText(self.db.get_setting("institution_name","Seminario Mayor de Guayaquil"));self.manager.setText(self.db.get_setting("manager_name",""));self.supervisor.setText(self.db.get_setting("recovery_supervisor_name",""));self.pin_state.setText("PIN configurado: sí" if self.db.has_pin() else "PIN configurado: no");self.db_path.setText(f"Base de datos local:\n{self.db.path}")
        self.refresh_panel_settings();self.refresh_linux_settings();self.backup_table.setRowCount(0)
        for path in self.db.list_backups():set_row(self.backup_table,[path.name,date.fromtimestamp(path.stat().st_mtime).isoformat(),f"{path.stat().st_size/1024:.1f} KB"])
        self.refresh_audit()

    def open_quick_panel(self):
        if launch_panel():self.success("Panel rápido abierto")
        else:self.error("No fue posible iniciar el Panel rápido.")

    def refresh_panel_settings(self):
        enabled=is_panel_autostart_enabled()
        self.panel_autostart.blockSignals(True);self.panel_autostart.setChecked(enabled);self.panel_autostart.blockSignals(False)
        self.panel_state.setText("Inicio automático: activado" if enabled else "Inicio automático: desactivado")

    def change_panel_autostart(self,enabled):
        try:
            set_panel_autostart(enabled);self.refresh_panel_settings();self.db.log_action("panel_autostart_changed","settings",None,{"enabled":bool(enabled)});self.success("Inicio automático del panel actualizado")
        except Exception as exc:
            self.panel_autostart.blockSignals(True);self.panel_autostart.setChecked(not enabled);self.panel_autostart.blockSignals(False);self.error(exc)

    def refresh_linux_settings(self):
        linux=is_linux_desktop();supported,message=workspace_support_status()
        for widget,value in ((self.linux_fullscreen,self.db.get_setting("linux_fullscreen","1")=="1"),(self.linux_workspace,self.db.get_setting("linux_workspace_2","1")=="1"),(self.linux_notifications,is_notifier_autostart_enabled())):
            widget.blockSignals(True);widget.setChecked(value);widget.setEnabled(linux);widget.blockSignals(False)
        self.linux_workspace.setEnabled(linux and supported)
        notification_state="activadas" if is_notifier_autostart_enabled() else "desactivadas"
        self.linux_state.setText(f"{message}\nNotificaciones automáticas: {notification_state}. Se revisan cada 10 minutos y no repiten una alerta sin cambios.")

    def change_linux_fullscreen(self,enabled):
        self.db.set_setting("linux_fullscreen","1" if enabled else "0");self.db.log_action("linux_fullscreen_changed","settings",None,{"enabled":bool(enabled)});self.success("Preferencia de pantalla completa guardada")

    def change_linux_workspace(self,enabled):
        self.db.set_setting("linux_workspace_2","1" if enabled else "0");self.db.log_action("linux_workspace_changed","settings",None,{"enabled":bool(enabled)});self.success("Preferencia de área de trabajo guardada")

    def change_linux_notifications(self,enabled):
        try:
            set_notifier_autostart(enabled);self.db.log_action("linux_notifications_changed","settings",None,{"enabled":bool(enabled)});self.refresh_linux_settings();self.success("Notificaciones automáticas actualizadas")
        except Exception as exc:
            self.refresh_linux_settings();self.error(exc)

    def test_linux_notification(self):
        if send_native_notification("Enfermería San Giuseppe Moscati","Notificación de prueba recibida correctamente."):self.success("Notificación de prueba enviada")
        else:self.error("No fue posible enviar la notificación. Comprueba que notify-send esté instalado y que exista una sesión gráfica activa.")

    def save_settings(self):
        self.db.set_setting("clinic_name",sentence_case(self.clinic.text()) or "Enfermería San Giuseppe Moscati");self.db.set_setting("institution_name",proper_name(self.institution.text()));self.db.set_setting("manager_name",proper_name(self.manager.text()));self.db.set_setting("recovery_supervisor_name",proper_name(self.supervisor.text()));self.changed.emit();self.success("Configuración guardada")
    def _ask_pin(self,title,label):
        return QInputDialog.getText(self,title,label,QLineEdit.EchoMode.Password)
    def change_pin(self):
        if self.db.has_pin():
            current,ok=self._ask_pin("Verificación","PIN actual:")
            if not ok:return
            if not self.db.verify_pin(current):self.error("El PIN actual no es correcto.");return
        new,ok=self._ask_pin("Nuevo PIN","Nuevo PIN de 4 a 8 números:")
        if not ok:return
        confirm,ok=self._ask_pin("Confirmar PIN","Repite el nuevo PIN:")
        if not ok:return
        if new!=confirm:self.error("Los PIN no coinciden.");return
        try:
            recovery=self.db.set_pin(new);self.refresh();QMessageBox.information(self,"PIN actualizado",f"Guarda este código institucional de recuperación en un lugar separado y bajo custodia:\n\n{recovery}\n\nSolo se mostrará ahora. Al usarlo se generará otro.")
        except Exception as e:self.error(e)
    def recover_pin(self):
        dialog=RecoveryDialog(self,self.db)
        if dialog.exec():self.refresh();QMessageBox.information(self,"PIN recuperado",f"El PIN fue cambiado. Guarda el NUEVO código institucional:\n\n{dialog.new_recovery_code}")
    def remove_pin(self):
        if not self.db.has_pin():self.success("No hay un PIN configurado");return
        current,ok=self._ask_pin("Quitar PIN","PIN actual:")
        if not ok:return
        if not self.db.verify_pin(current):self.error("El PIN no es correcto.");return
        self.db.remove_pin();self.refresh();self.success("PIN eliminado")
    def backup_now(self):
        try:path=self.db.create_backup();self.refresh();self.success(f"Copia creada: {path.name}")
        except Exception as e:self.error(e)
    def backup_as(self):
        filename,_=QFileDialog.getSaveFileName(self,"Guardar copia de seguridad","Enfermeria_respaldo.db","Base SQLite (*.db)")
        if filename:
            try:self.db.create_backup(filename if filename.endswith(".db") else filename+".db");self.refresh();self.success("Copia guardada")
            except Exception as e:self.error(e)
    def _password(self,title,confirm=False):
        password,ok=QInputDialog.getText(self,title,"Contraseña (mínimo 10 caracteres):",QLineEdit.EchoMode.Password)
        if not ok:return None
        if confirm:
            repeated,ok=QInputDialog.getText(self,title,"Repite la contraseña:",QLineEdit.EchoMode.Password)
            if not ok:return None
            if password!=repeated:self.error("Las contraseñas no coinciden.");return None
        return password
    def backup_encrypted(self):
        filename,_=QFileDialog.getSaveFileName(self,"Guardar copia cifrada","Enfermeria_respaldo.enfbackup","Copia cifrada (*.enfbackup)")
        if not filename:return
        password=self._password("Contraseña de la copia",True)
        if password is None:return
        try:self.db.create_encrypted_backup(filename if filename.endswith(".enfbackup") else filename+".enfbackup",password);self.success("Copia cifrada guardada")
        except Exception as exc:self.error(exc)
    def restore_encrypted(self):
        filename,_=QFileDialog.getOpenFileName(self,"Restaurar copia cifrada","","Copia cifrada (*.enfbackup)")
        if not filename:return
        password=self._password("Abrir copia cifrada")
        if password is None:return
        if QMessageBox.warning(self,"Confirmar restauración","La información actual será reemplazada. Antes se conservará una copia automática local. ¿Continuar?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        try:self.db.restore_encrypted_backup(filename,password);self.refresh();self.changed.emit();self.success("Copia cifrada restaurada")
        except Exception as exc:self.error(exc)
    def export_transfer(self):
        filename,_=QFileDialog.getSaveFileName(self,"Exportar entrega formal","Transferencia_Enfermeria.enftransfer","Transferencia cifrada (*.enftransfer)")
        if not filename:return
        password=self._password("Contraseña de transferencia",True)
        if password is None:return
        try:self.db.export_transfer_package(filename if filename.endswith(".enftransfer") else filename+".enftransfer",password,__version__);self.success("Paquete de transferencia creado")
        except Exception as exc:self.error(exc)
    def import_transfer(self):
        filename,_=QFileDialog.getOpenFileName(self,"Importar entrega formal","","Transferencia cifrada (*.enftransfer)")
        if not filename:return
        password=self._password("Abrir transferencia cifrada")
        if password is None:return
        if QMessageBox.warning(self,"Confirmar transferencia","La base y configuración actuales serán reemplazadas. Se creará primero una copia automática. ¿Continuar?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        try:
            manifest=self.db.import_transfer_package(filename,password);self.refresh();self.changed.emit();self.success(f"Transferencia importada (versión de origen {manifest.get('app_version','desconocida')})")
        except Exception as exc:self.error(exc)
    def restore(self):
        filename,_=QFileDialog.getOpenFileName(self,"Restaurar copia de seguridad","","Base SQLite (*.db);;Todos los archivos (*)")
        if not filename:return
        if QMessageBox.warning(self,"Confirmar restauración","La información actual será reemplazada por la copia seleccionada. Antes se creará un respaldo automático. ¿Continuar?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        try:self.db.restore_backup(filename);self.refresh();self.changed.emit();self.success("Copia restaurada correctamente")
        except Exception as e:self.error(e)
    def purge_data(self):
        if self.db.has_pin():
            current,ok=self._ask_pin("Verificación administrativa","PIN actual:")
            if not ok:return
            if not self.db.verify_pin(current):self.error("El PIN no es correcto.");return
        dialog=PurgeDialog(self)
        if not dialog.exec():return
        if QMessageBox.warning(self,"Última confirmación","¿Deseas purgar definitivamente todos los datos indicados? No se podrá deshacer.",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        try:
            self.db.purge_all_data(dialog.delete_backups.isChecked());self.refresh();self.changed.emit();self.success("La aplicación quedó limpia y lista para datos reales")
        except Exception as exc:self.error(exc)
    def open_data_folder(self):QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.db.path).parent)))
    def refresh_audit(self):
        self.audit_table.setRowCount(0)
        for r in self.db.query("SELECT occurred_at,action,entity_type,entity_id,details FROM audit_log ORDER BY id DESC LIMIT 500"):set_row(self.audit_table,[r["occurred_at"].replace("T"," ")[:19],r["action"],r["entity_type"],r["entity_id"] or "—",r["details"]])


class MainWindow(QMainWindow):
    def __init__(self,db:Database):
        super().__init__();self.db=db;self.setWindowTitle("Enfermería · Enfermería San Giuseppe Moscati");self.setWindowIcon(QIcon(str(ASSETS_DIR/"app_icon.png")));self.resize(1280,820);self.setMinimumSize(960,640)
        central=QWidget();self.setCentralWidget(central);layout=QHBoxLayout(central);layout.setContentsMargins(0,0,0,0);layout.setSpacing(0)
        self.sidebar=QFrame();self.sidebar.setObjectName("sidebar");nav=QVBoxLayout(self.sidebar);nav.setContentsMargins(9,12,9,14);nav.setSpacing(5)
        self.menu_button=QPushButton("☰");self.menu_button.setObjectName("nav");self.menu_button.setToolTip("Contraer o ampliar el menú");self.menu_button.setFixedHeight(42);self.menu_button.clicked.connect(self.toggle_sidebar);nav.addWidget(self.menu_button)
        self.brand_icon=QLabel();self.brand_icon.setPixmap(QPixmap(str(ASSETS_DIR/"app_icon.png")).scaled(42,42,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation));self.brand_icon.setAlignment(Qt.AlignmentFlag.AlignCenter);nav.addWidget(self.brand_icon)
        self.brand=QLabel();self.brand.setWordWrap(True);self.brand.setFixedHeight(66);self.brand.setAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter);self.brand.setStyleSheet("font-size:14px;font-weight:800;color:#60d5b7;padding:6px");nav.addWidget(self.brand);nav.addSpacing(5)
        layout.addWidget(self.sidebar);right=QWidget();right_layout=QVBoxLayout(right);right_layout.setContentsMargins(0,0,0,0);right_layout.setSpacing(0);layout.addWidget(right,1)
        top_bar=QFrame();top_bar.setObjectName("sidebar");top_bar.setFixedHeight(48);top=QHBoxLayout(top_bar);top.setContentsMargins(16,5,14,5)
        self.section_name=QLabel("Inicio");self.section_name.setStyleSheet("font-size:15px;font-weight:800;color:#60d5b7;background:transparent");top.addWidget(self.section_name);top.addStretch()
        self.clock=QLabel();self.clock.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter);self.clock.setStyleSheet("font-size:14px;font-weight:700;color:#edf7f8;background:transparent");top.addWidget(self.clock)
        self.fullscreen_button=QPushButton("F11");self.fullscreen_button.setToolTip("Pantalla completa (F11)");self.fullscreen_button.setFixedSize(46,34);self.fullscreen_button.clicked.connect(self.toggle_fullscreen);top.addWidget(self.fullscreen_button);right_layout.addWidget(top_bar)
        self.stack=QStackedWidget();right_layout.addWidget(self.stack,1)
        self.pages=[DashboardPage(db),InventoryPage(db),SeminariansPage(db),MovementsPage(db),EquipmentPage(db),ConfigurationPage(db)]
        self.nav_items=[("⌂","Inicio"),("▦","Inventario"),("♙","Seminaristas"),("⇄","Movimientos"),("+","Equipos"),("⚙","Configuración")]
        self.nav=[]
        for index,((icon,name),page) in enumerate(zip(self.nav_items,self.pages)):
            self.stack.addWidget(page);b=QPushButton();b.setObjectName("nav");b.setCheckable(True);b.setToolTip(name);b.clicked.connect(lambda checked,i=index:self.show_page(i));nav.addWidget(b);self.nav.append(b)
        nav.addStretch();self.foot=QLabel(f"Versión {__version__}\nCopias cifradas disponibles\nLinux · Windows 10/11");self.foot.setObjectName("muted");nav.addWidget(self.foot)
        self.sidebar_expanded=True;self.set_sidebar_expanded(True)
        for page in self.pages:page.changed.connect(self.refresh_all);page.notice.connect(self.show_notice)
        self.statusBar().showMessage("Sistema listo · base local verificada")
        self.update_brand()
        self.clock_timer=QTimer(self);self.clock_timer.timeout.connect(self.update_clock);self.clock_timer.start(1000);self.update_clock()
        self.show_page(0)
    def closeEvent(self,event):
        if not self.pages[5].web_sync.stop():event.ignore();return
        super().closeEvent(event)
    def show_page(self,index):
        self.stack.setCurrentIndex(index)
        self.section_name.setText(self.nav_items[index][1])
        for i,b in enumerate(self.nav):b.setChecked(i==index)
        self.set_sidebar_expanded(index==0)
        page=self.pages[index]
        if hasattr(page,"refresh"):page.refresh()
    def toggle_sidebar(self):self.set_sidebar_expanded(not self.sidebar_expanded)
    def set_sidebar_expanded(self,expanded):
        self.sidebar_expanded=expanded;self.sidebar.setFixedWidth(230 if expanded else 72);self.brand.setVisible(expanded);self.brand_icon.setVisible(not expanded);self.foot.setVisible(expanded)
        self.menu_button.setText("☰" if expanded else "☰")
        self.menu_button.setStyleSheet("text-align:left;font-size:20px;padding:7px 12px" if expanded else "text-align:center;font-size:20px;padding:7px 0")
        for button_widget,(icon,name) in zip(self.nav,self.nav_items):
            button_widget.setText(f"{icon}   {name}" if expanded else icon)
            button_widget.setStyleSheet("" if expanded else "text-align:center;font-size:19px;padding:10px 0")
    def refresh_all(self):
        for p in self.pages:
            if hasattr(p,"refresh"):p.refresh()
        self.update_brand()
    def update_brand(self):
        name=self.db.get_setting("clinic_name","Enfermería San Giuseppe Moscati");self.brand.setText(f"ENFERMERÍA\n{name}")
    def update_clock(self):
        now=QDateTime.currentDateTime();locale=QLocale(QLocale.Language.Spanish,QLocale.Country.Ecuador);self.clock.setText(locale.toString(now,"dddd, d 'de' MMMM · HH:mm:ss"))
    def toggle_fullscreen(self):
        if self.isFullScreen():self.showNormal()
        else:self.showFullScreen()
    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_F11:self.toggle_fullscreen();event.accept();return
        if event.key()==Qt.Key.Key_Escape and self.isFullScreen():self.showNormal();event.accept();return
        super().keyPressEvent(event)
    def show_notice(self,message):self.statusBar().showMessage(message,5000)
