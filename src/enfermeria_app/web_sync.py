"""One-way publication of a consistent local snapshot; never imports web changes."""
from __future__ import annotations
import hashlib
import json
import os
import re
import sqlite3
import time
import uuid
from datetime import datetime, timezone, date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from .pdf_export import export_seminarian_dossier_pdf, export_emergency_summary_pdf, export_all_dossiers_pdf

COLLECTIONS = ('seminarians','items','lots','medical_controls','movements')

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('La dirección del portal redirige a otra página. Verifica la conexión.')

class SnapshotDatabase:
    def __init__(self, connection): self.connection=connection
    def query(self, sql, parameters=()): return self.connection.execute(sql,parameters).fetchall()
    def get_setting(self, key, default=''):
        row=self.connection.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
        return row[0] if row else default


def validate_connection(data):
    if data.get('version')!=1: raise ValueError('Archivo de conexión no compatible.')
    parsed=urlparse(str(data.get('url','')))
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/'):
        raise ValueError('El portal debe tener una dirección HTTPS válida, sin rutas adicionales.')
    for key in ('secret','service_token'):
        value=data.get(key)
        if not isinstance(value,str) or len(value)<32 or any(ord(c)<33 or ord(c)>126 for c in value):
            raise ValueError('El archivo de conexión no contiene las claves necesarias.')
    return {**data,'url':parsed.geturl().rstrip('/')}


def config_path(database_path): return Path(database_path).parent/'web_connection.json'


def load_connection(database_path):
    path=config_path(database_path)
    if not path.exists(): return None
    return validate_connection(json.loads(path.read_text(encoding='utf-8')))


def save_connection(database_path, data):
    data=validate_connection(data);target=config_path(database_path);temp=target.with_suffix('.tmp')
    descriptor=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(descriptor,'w',encoding='utf-8') as stream: json.dump(data,stream)
    os.replace(temp,target)
    if os.name!='nt': target.chmod(0o600)


def viewer_emails(raw):
    emails=sorted(set(x.strip().lower() for x in re.split(r'[\s,;]+',raw) if x.strip()))
    if len(emails)>100 or any(not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',e) for e in emails):
        raise ValueError('Revisa los correos de los formadores.')
    return [{'email':email} for email in emails]


def _request(connection, route, value, method='POST', mime='application/json'):
    payload=json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8') if mime=='application/json' else value
    headers={'Content-Type':mime,'Authorization':'Bearer '+connection['secret'],
             'OAI-Sites-Authorization':'Bearer '+connection['service_token']}
    request=Request(connection['url']+'/api/sync'+route,data=payload,headers=headers,method=method)
    try:
        with build_opener(NoRedirect()).open(request,timeout=45) as response:
            result=json.loads(response.read(65536))
            if not result.get('ok'): raise ValueError('El portal no confirmó el envío.')
            return result
    except HTTPError as exc:
        try: message=json.loads(exc.read(65536)).get('error')
        except (ValueError,AttributeError): message=None
        raise ValueError(message or f'El portal rechazó la conexión (HTTP {exc.code}).') from None
    except (URLError,TimeoutError):
        raise ValueError('No se pudo conectar. Tus datos locales y la copia publicada se conservan.') from None


def _snapshot(database_path, source):
    connection=sqlite3.connect(':memory:');connection.row_factory=sqlite3.Row
    with sqlite3.connect(f'file:{Path(database_path).resolve().as_posix()}?mode=ro',uri=True) as local:
        local.backup(connection)
    return connection


def synchronize(database_path, force=False, progress=lambda message:None, transport=_request):
    connection=load_connection(database_path)
    if connection is None: raise ValueError('Primero importa el archivo de conexión del portal.')
    with sqlite3.connect(database_path) as local:
        row=local.execute("SELECT value FROM settings WHERE key='web_sync_source'").fetchone()
        source=row[0] if row else str(uuid.uuid4())
        if not row: local.execute("INSERT INTO settings(key,value) VALUES('web_sync_source',?)",(source,))
    snap=_snapshot(database_path,source)
    try:
        db=SnapshotDatabase(snap);records=[];photos={}
        emails=viewer_emails(db.get_setting('web_sync_viewers',''))
        for collection in COLLECTIONS:
            for row in db.query('SELECT * FROM '+collection+' ORDER BY id'):
                data=dict(row)
                if collection=='seminarians':
                    photo=data.pop('photo',None)
                    if photo:
                        extension='png' if bytes(photo).startswith(b'\x89PNG\r\n\x1a\n') else 'jpg'
                        name=f"photos/{data['id']}.{extension}";photos[name]=bytes(photo);data['photo_path']=name
                if collection=='items':
                    lots=[dict(r) for r in db.query('SELECT * FROM lots WHERE item_id=? AND quantity>0',(data['id'],))]
                    today=date.today().isoformat()
                    unavailable=sum(l['quantity'] for l in lots if l['quarantined'] or (l['expires_on'] and l['expires_on']<today))
                    data['available_stock']=max(0,data['stock']-unavailable)
                    dates=sorted(l['expires_on'] for l in lots if l['expires_on'])
                    data['nearest_expiry']=dates[0] if dates else ''
                    data['expiry_status']='Contiene lotes vencidos o en cuarentena' if unavailable else ('Vence pronto' if dates and dates[0]<=(date.today()+timedelta(days=90)).isoformat() else ('Vigente' if dates else 'Fecha no registrada'))
                records.append({'collection':collection,'id':data['id'],'data':data})
        content={'records':records,'viewers':emails,'institution':db.get_setting('institution_name'),'clinic':db.get_setting('clinic_name'),'day':date.today().isoformat(),'photos':{k:hashlib.sha256(v).hexdigest() for k,v in photos.items()}}
        fingerprint=hashlib.sha256(json.dumps(content,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        if not force and fingerprint==db.get_setting('web_sync_digest'): return {'unchanged':True,'syncedAt':db.get_setting('web_sync_last')}
        with TemporaryDirectory(prefix='enfermeria_sync_') as work:
            root=Path(work);files=dict(photos);active=db.query('SELECT id FROM seminarians WHERE archived=0 ORDER BY id')
            progress('Preparando fichas y documentos…')
            for row in active:
                for folder,export in (('dossiers',export_seminarian_dossier_pdf),('emergency',export_emergency_summary_pdf)):
                    target=root/f"{folder}_{row['id']}.pdf";export(db,row['id'],target);files[f"{folder}/{row['id']}.pdf"]=target.read_bytes()
            if active:
                target=root/'dossiers.pdf';export_all_dossiers_pdf(db,target);files['dossiers.pdf']=target.read_bytes()
            manifest=[{'name':name,'size':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} for name,raw in files.items()]
            if len(records)>50000 or len(manifest)>3000 or any(f['size']>25*1024*1024 for f in manifest):
                raise ValueError('La copia supera el límite de publicación. No se ha cambiado la web.')
            sequence=max(int(time.time()*1000),int(db.get_setting('web_sync_sequence','0'))+1)
            generation=str(uuid.uuid4());captured=datetime.now(timezone.utc).isoformat()
            transport(connection,'',{'generation':generation,'source':source,'sequence':sequence,'capturedAt':captured,'expectedRecords':len(records),'files':manifest,'viewers':emails,'institution':content['institution'],'clinic':content['clinic']})
            chunk=[];chunk_size=0
            for record in records:
                size=len(json.dumps(record,ensure_ascii=False).encode())
                if size>60000: raise ValueError('Una ficha supera el tamaño permitido. La copia anterior sigue publicada.')
                if chunk and (len(chunk)>=100 or chunk_size+size>500000):
                    transport(connection,'/records',{'generation':generation,'records':chunk});chunk=[];chunk_size=0
                chunk.append(record);chunk_size+=size
            if chunk: transport(connection,'/records',{'generation':generation,'records':chunk})
            for index,(name,raw) in enumerate(files.items(),1):
                progress(f'Enviando archivos {index} de {len(files)}…');transport(connection,'/'+generation+'/'+name,raw,'PUT','application/octet-stream')
            progress('Confirmando copia completa…');result=transport(connection,'/commit',{'generation':generation})
            with sqlite3.connect(database_path) as local:
                for key,value in (('web_sync_digest',fingerprint),('web_sync_last',result['syncedAt']),('web_sync_sequence',str(sequence))):
                    local.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,value))
            return result
    finally: snap.close()
