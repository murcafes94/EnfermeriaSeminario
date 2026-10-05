import sys, tempfile, unittest, json, hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from enfermeria_app.database import Database
from enfermeria_app.web_sync import synchronize,save_connection,viewer_emails,validate_connection

class WebSyncTests(unittest.TestCase):
 def setUp(self):
  self.root=Path(tempfile.mkdtemp());self.db=Database(self.root/'enfermeria.db')
  self.sem=self.db.insert_seminarian({'first_name':'Prueba','last_name':'Sin datos reales','photo':(Path(__file__).resolve().parents[1]/'assets/app_icon.png').read_bytes()})
  self.item=self.db.save_item({'name':'Producto de prueba','type':'medicine'})
  self.db.add_stock(self.item,10,'Lote','2030-12-31')
  self.db.record_output(self.item,1,'administered',self.sem,'1 tableta','Prueba')
  self.db.save_medical_control(self.sem,{'measured_at':'2026-10-04T20:00:00','weight_kg':70,'height_cm':175,'systolic':120,'diastolic':80,'glucose_mg_dl':90,'glucose_context':'fasting'})
  self.db.set_setting('web_sync_viewers','formador@example.org')
  save_connection(self.db.path,{'version':1,'url':'https://example.org','secret':'s'*40,'service_token':'t'*40})
 def test_complete_snapshot_and_unchanged_skip(self):
  sent=[]
  def transport(connection,route,value,*args):sent.append((route,value));return {'ok':True,'syncedAt':'2026-10-05T04:00:00Z'}
  result=synchronize(self.db.path,transport=transport)
  manifest=sent[0][1];self.assertEqual(manifest['viewers'],[{'email':'formador@example.org'}])
  records=[r for path,value in sent if path=='/records' for r in value['records']]
  self.assertEqual(manifest['expectedRecords'],len(records));self.assertEqual(sent[-1][0],'/commit')
  self.assertEqual(next(r for r in records if r['collection']=='seminarians')['data']['id'],self.sem)
  self.assertNotIn('photo',next(r for r in records if r['collection']=='seminarians')['data'])
  files={name.split('/',2)[2]:raw for name,raw in sent if name.startswith('/'+manifest['generation']+'/')}
  self.assertTrue(files['dossiers.pdf'].startswith(b'%PDF'));self.assertTrue(files[f'dossiers/{self.sem}.pdf'].startswith(b'%PDF'))
  for entry in manifest['files']:self.assertEqual(hashlib.sha256(files[entry['name']]).hexdigest(),entry['sha256'])
  self.assertEqual(self.db.query('SELECT stock FROM items WHERE id=?',(self.item,))[0][0],9)
  self.assertEqual(self.db.get_setting('web_sync_last'),result['syncedAt'])
  self.assertTrue(synchronize(self.db.path,transport=lambda *args:self.fail('No debe reenviar sin cambios'))['unchanged'])
 def test_failure_preserves_confirmation(self):
  self.db.set_setting('web_sync_last','COPIA_ANTERIOR')
  def transport(connection,route,value,*args):
   if route=='/commit':raise ValueError('interrumpido')
   return {'ok':True}
  with self.assertRaises(ValueError):synchronize(self.db.path,transport=transport)
  self.assertEqual(self.db.get_setting('web_sync_last'),'COPIA_ANTERIOR')
  self.assertEqual(self.db.get_setting('web_sync_digest'),'')
 def test_connection_and_allowlist_validation(self):
  with self.assertRaises(ValueError):validate_connection({'version':1,'url':'http://example.org','secret':'s'*40,'service_token':'t'*40})
  with self.assertRaises(ValueError):viewer_emails('correo inválido')
  self.assertEqual(viewer_emails('A@example.org; a@example.org'),[{'email':'a@example.org'}])
