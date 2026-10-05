from __future__ import annotations
import json
from pathlib import Path
from PySide6.QtCore import QThread, Signal, QTimer
from PySide6.QtWidgets import QWidget,QVBoxLayout,QFormLayout,QLabel,QPushButton,QTextEdit,QCheckBox,QFileDialog,QMessageBox
from .web_sync import synchronize,load_connection,save_connection,viewer_emails

class SyncWorker(QThread):
    completed=Signal(dict);failed=Signal(str);progress=Signal(str)
    def __init__(self,path,force=False):super().__init__();self.path=path;self.force=force
    def run(self):
        try:self.completed.emit(synchronize(self.path,self.force,self.progress.emit))
        except Exception as error:self.failed.emit(str(error))

class WebSyncPage(QWidget):
    def __init__(self,db):
        super().__init__();self.db=db;self.worker=None;self.manual=False
        layout=QVBoxLayout(self);intro=QLabel('La app es la fuente principal. El portal recibe una copia para consultar fichas, fotos, controles y medicamentos. No modifica los datos de esta computadora.');intro.setWordWrap(True);layout.addWidget(intro)
        form=QFormLayout();self.portal=QLabel('Sin conexión configurada');self.portal.setWordWrap(True);form.addRow('Portal',self.portal);layout.addLayout(form)
        self.import_button=QPushButton('Importar conexión del portal…');self.import_button.clicked.connect(self.import_connection);layout.addWidget(self.import_button)
        layout.addWidget(QLabel('Correos autorizados para consultar (uno por línea):'));self.emails=QTextEdit();self.emails.setMaximumHeight(150);self.emails.setPlainText(db.get_setting('web_sync_viewers',''));layout.addWidget(self.emails)
        note=QLabel('Estos correos también deben tener acceso al sitio. Añadirlos aquí no envía invitaciones ni cambia el acceso del alojamiento.');note.setWordWrap(True);layout.addWidget(note)
        self.auto=QCheckBox('Sincronizar automáticamente cada 5 minutos mientras la app esté abierta');self.auto.setChecked(db.get_setting('web_sync_auto','0')=='1');layout.addWidget(self.auto)
        save=QPushButton('Guardar preferencias');save.clicked.connect(self.save);layout.addWidget(save)
        self.send=QPushButton('Sincronizar ahora');self.send.clicked.connect(lambda:self.start(True));layout.addWidget(self.send)
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status);layout.addStretch();self.refresh()
        self.timer=QTimer(self);self.timer.timeout.connect(lambda:self.start(False));self.timer.start(5*60*1000)
        QTimer.singleShot(15000,lambda:self.start(False))
    def refresh(self):
        try:connection=load_connection(self.db.path);self.portal.setText(connection['url'] if connection else 'Sin conexión configurada')
        except Exception:self.portal.setText('El archivo de conexión necesita revisarse')
        self.status.setText('Último envío confirmado: '+self.db.get_setting('web_sync_last','Todavía no se ha sincronizado'))
    def import_connection(self):
        filename,_=QFileDialog.getOpenFileName(self,'Importar conexión','','Conexión (*.enfconnection)')
        if not filename:return
        try:
            data=json.loads(Path(filename).read_text(encoding='utf-8'))
            if QMessageBox.question(self,'Conectar portal','La app publicará información sanitaria en:\n'+str(data.get('url',''))+'\n\n¿Es el portal de tu enfermería?')!=QMessageBox.StandardButton.Yes:return
            save_connection(self.db.path,data);self.db.set_setting('web_sync_digest','');self.refresh()
        except Exception as error:QMessageBox.warning(self,'Conexión',str(error))
    def save(self):
        try:
            emails=viewer_emails(self.emails.toPlainText());self.db.set_setting('web_sync_viewers','\n'.join(v['email'] for v in emails));self.db.set_setting('web_sync_auto','1' if self.auto.isChecked() else '0');self.status.setText('Preferencias guardadas. Se publicarán en el siguiente envío.');return True
        except Exception as error:QMessageBox.warning(self,'Correos',str(error));return False
    def start(self,manual=False):
        if self.worker and self.worker.isRunning():return
        if not manual and self.db.get_setting('web_sync_auto','0')!='1':return
        if manual and not self.save():return
        try:
            if not load_connection(self.db.path):
                if manual:QMessageBox.information(self,'Conexión','Descarga la conexión desde la web e impórtala aquí.')
                return
        except Exception as error:self.status.setText(str(error));return
        self.manual=manual;self.send.setEnabled(False);self.import_button.setEnabled(False);self.status.setText('Preparando sincronización…')
        self.worker=SyncWorker(self.db.path,manual);self.worker.progress.connect(self.status.setText);self.worker.completed.connect(self.done);self.worker.failed.connect(self.failed);self.worker.finished.connect(self.finished);self.worker.start()
    def done(self,result):
        self.status.setText('Sin cambios pendientes.' if result.get('unchanged') else 'Copia completa publicada: '+result.get('syncedAt',''))
    def failed(self,message):self.status.setText('Envío pendiente: '+message)
    def finished(self):self.send.setEnabled(True);self.import_button.setEnabled(True)
    def stop(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self,'Sincronización','Espera a que termine el envío antes de cerrar la aplicación.');return False
        return True
