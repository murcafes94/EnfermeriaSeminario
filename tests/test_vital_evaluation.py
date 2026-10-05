import os
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from enfermeria_app.vital_evaluation import evaluate_pressure, evaluate_pulse
from enfermeria_app.database import Database
from enfermeria_app.pdf_export import export_control_pdf, export_seminarian_dossier_pdf

class VitalEvaluationTests(unittest.TestCase):
    def test_pressure_boundaries_and_discordant_components(self):
        cases=[(89,70,'low'),(110,59,'low'),(90,60,'normal'),(119,79,'normal'),
               (120,79,'elevated'),(119,80,'elevated'),(139,89,'elevated'),
               (140,79,'high'),(118,90,'high'),(118,95,'high'),
               (180,120,'high'),(181,70,'critical'),(118,121,'critical')]
        for systolic,diastolic,code in cases:
            with self.subTest(systolic=systolic,diastolic=diastolic):
                self.assertEqual(evaluate_pressure(systolic,diastolic).code,code)
    def test_missing_values_never_look_normal(self):
        for s,d in [(None,None),(0,0),(118,None),(None,75),(-1,75),(float('nan'),75)]:
            with self.subTest(s=s,d=d):
                self.assertNotEqual(evaluate_pressure(s,d).code,'normal')
        self.assertEqual(evaluate_pressure(181,None).code,'critical')
        self.assertIn('incompleta',evaluate_pressure(181,None).note)
    def test_mixed_low_and_high_retains_both_alerts(self):
        result=evaluate_pressure(150,50)
        self.assertEqual(result.code,'high')
        self.assertIn('presión baja',result.note)
    def test_pulse_inclusive_boundaries(self):
        for value,code in [(None,'missing'),(0,'missing'),(59,'low'),(60,'normal'),(100,'normal'),(101,'high')]:
            self.assertEqual(evaluate_pulse(value).code,code)
    def test_critical_advice_does_not_delay_emergency_care(self):
        note=evaluate_pressure(181,70).note
        self.assertIn('911 de inmediato; no esperar',note)
        self.assertIn('Si no hay síntomas',note)
        self.assertIn('al menos un minuto',note)
    def test_saved_control_and_a4_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);db=Database(root/'test.db')
            sem=db.insert_seminarian({'first_name':'Prueba','last_name':'Sin datos reales'})
            control=db.save_medical_control(sem,{'measured_at':'2026-10-05T10:00:00','systolic':118,'diastolic':95,'pulse':101})
            reopened=Database(db.path);row=reopened.query('SELECT * FROM medical_controls WHERE id=?',(control,))[0]
            self.assertEqual((row['systolic'],row['diastolic'],row['pulse']),(118,95,101))
            self.assertEqual(evaluate_pressure(row['systolic'],row['diastolic']).code,'high')
            export_control_pdf(reopened,control,root/'control.pdf')
            export_seminarian_dossier_pdf(reopened,sem,root/'history.pdf')
            for name in ('control.pdf','history.pdf'):
                self.assertTrue((root/name).read_bytes().startswith(b'%PDF'))

class LiveEvaluationTests(unittest.TestCase):
    def test_live_form_and_reopening_saved_values(self):
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        try:
            from PySide6.QtWidgets import QApplication
        except ImportError:
            self.skipTest('PySide6 no disponible en este entorno; se ejecuta en CI.')
        from enfermeria_app.ui import MedicalControlDialog
        app=QApplication.instance() or QApplication([])
        dialog=MedicalControlDialog(None)
        dialog.systolic.setValue(118);dialog.diastolic.setValue(95);dialog.pulse.setValue(101)
        app.processEvents()
        self.assertEqual(dialog.pressure_evaluation.text(),'Presión alta')
        self.assertEqual(dialog.pulse_evaluation.text(),'Frecuencia alta')
        values=dialog.values();dialog.close()
        reopened=MedicalControlDialog(None,values)
        self.assertEqual(reopened.pressure_evaluation.text(),'Presión alta')
        reopened.systolic.setValue(181);app.processEvents()
        self.assertIn('Alerta crítica',reopened.pressure_evaluation.text())
        self.assertIn('911 de inmediato',reopened.evaluation_advice.text())
        reopened.close()
