from __future__ import annotations

import base64
import json
import os
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


MAGIC = b"ENFERMERIA-AESGCM-1\n"
KDF_ITERATIONS = 600_000


def _password_key(password: str, salt: bytes) -> bytes:
    if len(password) < 10:
        raise ValueError("La contraseña debe tener al menos 10 caracteres.")
    return PBKDF2HMAC(algorithm=hashes.SHA256(),length=32,salt=salt,iterations=KDF_ITERATIONS).derive(password.encode("utf-8"))


def encrypt_bytes(payload: bytes, password: str, kind: str) -> bytes:
    salt=os.urandom(16);nonce=os.urandom(12);key=_password_key(password,salt)
    metadata={"kind":kind,"created_at":datetime.now().isoformat(timespec="seconds"),"salt":base64.b64encode(salt).decode(),"nonce":base64.b64encode(nonce).decode(),"iterations":KDF_ITERATIONS}
    header=json.dumps(metadata,ensure_ascii=False,separators=(",",":")).encode("utf-8")
    encrypted=AESGCM(key).encrypt(nonce,payload,MAGIC+header)
    return MAGIC+header+b"\n"+encrypted


def decrypt_bytes(container: bytes, password: str, expected_kind: str | None = None) -> tuple[bytes,dict]:
    if not container.startswith(MAGIC):raise ValueError("El archivo no es un paquete cifrado válido de Enfermería.")
    try:
        header,ciphertext=container[len(MAGIC):].split(b"\n",1);metadata=json.loads(header.decode("utf-8"))
        if expected_kind and metadata.get("kind")!=expected_kind:raise ValueError("El tipo de paquete no corresponde a esta operación.")
        salt=base64.b64decode(metadata["salt"]);nonce=base64.b64decode(metadata["nonce"]);key=_password_key(password,salt)
        return AESGCM(key).decrypt(nonce,ciphertext,MAGIC+header),metadata
    except ValueError:raise
    except Exception as exc:raise ValueError("No se pudo leer el paquete cifrado.") from exc


def encrypt_file(source: Path | str, destination: Path | str, password: str, kind: str) -> Path:
    source=Path(source);destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_bytes(encrypt_bytes(source.read_bytes(),password,kind));_restrict(destination);return destination


def decrypt_file(source: Path | str, destination: Path | str, password: str, expected_kind: str) -> Path:
    payload,_=decrypt_bytes(Path(source).read_bytes(),password,expected_kind);destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(payload);_restrict(destination);return destination


def build_transfer_payload(database_file: Path | str, settings: dict[str,str], version: str) -> bytes:
    database_file=Path(database_file)
    with tempfile.TemporaryDirectory() as folder:
        archive=Path(folder)/"transfer.zip"
        manifest={"format":"enfermeria-transfer-1","app_version":version,"created_at":datetime.now().isoformat(timespec="seconds"),"settings":settings}
        manual=("ENTREGA FORMAL DE LA ENFERMERÍA\n\n"
                f"Institución: {settings.get('institution_name','')}\nEnfermería: {settings.get('clinic_name','')}\n"
                f"Encargado saliente: {settings.get('manager_name','')}\nFecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
                "Contenido: base de datos, configuración institucional y manifiesto.\n"
                "El encargado receptor debe importar este paquete desde Configuración > Transferencia, revisar el inventario, cambiar el PIN y generar un nuevo código institucional de recuperación.\n"
                "La contraseña del paquete debe comunicarse por un canal distinto al archivo.\n")
        with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as zf:
            zf.write(database_file,"enfermeria.db");zf.writestr("manifest.json",json.dumps(manifest,ensure_ascii=False,indent=2));zf.writestr("MANUAL_DE_ENTREGA.txt",manual)
        return archive.read_bytes()


def extract_transfer_payload(payload: bytes, destination: Path | str) -> tuple[Path,dict]:
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        archive=Path(folder)/"transfer.zip";archive.write_bytes(payload)
        with zipfile.ZipFile(archive) as zf:
            names=set(zf.namelist())
            if not {"enfermeria.db","manifest.json","MANUAL_DE_ENTREGA.txt"}.issubset(names):raise ValueError("El paquete de transferencia está incompleto.")
            manifest=json.loads(zf.read("manifest.json").decode("utf-8"))
            if manifest.get("format")!="enfermeria-transfer-1":raise ValueError("La versión del paquete de transferencia no es compatible.")
            target=destination/"enfermeria-transfer.db";target.write_bytes(zf.read("enfermeria.db"));_restrict(target)
            return target,manifest


def _restrict(path: Path):
    try:os.chmod(path,0o600)
    except OSError:pass
