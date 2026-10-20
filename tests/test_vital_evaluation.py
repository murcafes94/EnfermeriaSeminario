import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from enfermeria_app.vital_evaluation import evaluate_glucose, evaluate_pressure, evaluate_pulse
from enfermeria_app.database import Database
from enfermeria_app.pdf_export import export_control_pdf, export_seminarian_dossier_pdf

class VitalEvaluationTests(unittest.TestCase):
    def test_pressure_boundaries_and_discordant_components(self):
        cases=[(89,70,'low'),(110,59,'low'),(90,60,'normal'),(119,79,'normal'),
               (120,79,'elevated'),(129,79,'elevated'),(119,80,'stage1'),(139,89,'stage1'),
               (140,79,'stage2'),(145,75,'stage2'),(118,90,'stage2'),(118,95,'stage2'),
               (180,120,'stage2'),(181,70,'critical'),(150,125,'critical'),(118,121,'critical')]
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
        self.assertEqual(result.code,'stage2')
        self.assertIn('presión baja',result.note)
    def test_pulse_inclusive_boundaries(self):
        for value,code in [(None,'missing'),(0,'missing'),(59,'low'),(60,'normal'),(100,'normal'),(101,'high')]:
            self.assertEqual(evaluate_pulse(value).code,code)
    def test_critical_advice_does_not_delay_emergency_care(self):
        without_symptoms=evaluate_pressure(181,70)
        self.assertIn('al menos un minuto',without_symptoms.note)
        self.assertNotIn('911',without_symptoms.note)
        with_symptoms=evaluate_pressure(181,70,['chest_pain'])
        self.assertIn('Atención médica urgente',with_symptoms.label)
        self.assertIn('911',with_symptoms.note)
        self.assertIn('No esperar',with_symptoms.note)

    def test_fasting_glucose_boundaries(self):
        cases=[(53,'critical'),(54,'low'),(69,'low'),(70,'normal'),(99,'normal'),
               (100,'elevated'),(125,'elevated'),(126,'high'),(199,'high'),(200,'critical')]
        for value,code in cases:
            with self.subTest(value=value):
                self.assertEqual(evaluate_glucose(value,'capillary','fasting').code,code)

    def test_capillary_glucose_never_claims_a_diabetes_diagnosis(self):
        result=evaluate_glucose(126,'capillary','fasting')
        self.assertIn('requiere evaluación',result.label)
        self.assertIn('no diagnostica diabetes',result.note)
        self.assertNotIn('diabetes',result.label.lower())

    def test_non_fasting_midrange_is_not_classified_with_fasting_ranges(self):
        for context in ('postprandial_2h','random'):
            self.assertEqual(evaluate_glucose(110,'capillary',context).code,'context_required')
    def test_saved_control_and_a4_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);db=Database(root/'test.db')
            sem=db.insert_seminarian({'first_name':'Prueba','last_name':'Sin datos reales'})
            control=db.save_medical_control(sem,{'measured_at':'2026-10-05T10:00:00','systolic':150,'diastolic':125,'pulse':101,'pressure_alarm_symptoms':'visual_change','glucose_mg_dl':126,'glucose_sample_type':'capillary','glucose_context':'fasting'})
            reopened=Database(db.path);row=reopened.query('SELECT * FROM medical_controls WHERE id=?',(control,))[0]
            self.assertEqual((row['systolic'],row['diastolic'],row['pulse']),(150,125,101))
            self.assertEqual(row['glucose_sample_type'],'capillary')
            self.assertEqual(row['pressure_alarm_symptoms'],'visual_change')
            self.assertEqual(evaluate_pressure(row['systolic'],row['diastolic'],row['pressure_alarm_symptoms']).code,'critical')
            export_control_pdf(reopened,control,root/'control.pdf')
            export_seminarian_dossier_pdf(reopened,sem,root/'history.pdf')
            for name in ('control.pdf','history.pdf'):
                self.assertTrue((root/name).read_bytes().startswith(b'%PDF'))

    def test_existing_controls_are_preserved_by_the_schema_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'legacy.db';db=Database(path)
            sem=db.insert_seminarian({'first_name':'Registro','last_name':'Existente'})
            control=db.save_medical_control(sem,{'measured_at':'2026-10-01T08:00:00','glucose_mg_dl':92,'glucose_context':'fasting'})
            with sqlite3.connect(path) as connection:
                connection.execute('ALTER TABLE medical_controls DROP COLUMN pressure_alarm_symptoms')
                connection.execute('ALTER TABLE medical_controls DROP COLUMN glucose_sample_type')
            migrated=Database(path);row=migrated.query('SELECT * FROM medical_controls WHERE id=?',(control,))[0]
            self.assertEqual((row['glucose_mg_dl'],row['glucose_context']),(92,'fasting'))
            self.assertEqual((row['pressure_alarm_symptoms'],row['glucose_sample_type']),('',''))

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
        self.assertEqual(dialog.glucose_sample_type.currentData(),'capillary')
        self.assertEqual(dialog.glucose_context.currentData(),'fasting')
        dialog.systolic.setValue(118);dialog.diastolic.setValue(95);dialog.pulse.setValue(101);dialog.glucose.setValue(126)
        app.processEvents()
        self.assertIn('etapa 2',dialog.pressure_evaluation.text())
        self.assertIn('requiere evaluación',dialog.glucose_evaluation.text())
        self.assertEqual(dialog.pulse_evaluation.text(),'Frecuencia alta')
        values=dialog.values();dialog.close()
        reopened=MedicalControlDialog(None,values)
        self.assertIn('etapa 2',reopened.pressure_evaluation.text())
        reopened.systolic.setValue(181);app.processEvents()
        self.assertFalse(reopened.pressure_alarm_group.isHidden())
        self.assertIn('severamente elevada',reopened.pressure_evaluation.text())
        reopened.pressure_alarm_checks['chest_pain'].setChecked(True);app.processEvents()
        self.assertIn('Atención médica urgente',reopened.pressure_evaluation.text())
        self.assertIn('911',reopened.evaluation_advice.text())
        reopened.close()
