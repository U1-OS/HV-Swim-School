"""Encrypted, non-overwriting recovery bundles for database, uploads and key material."""
import hashlib,io,json,os,sqlite3,tempfile,zipfile
from pathlib import Path
from nacl.secret import SecretBox
from nacl.exceptions import CryptoError

MAGIC=b'HVRECOVERY1'


def key_for(passphrase,salt):
    if len(passphrase)<20:raise ValueError('Use a recovery passphrase of at least 20 characters')
    return hashlib.scrypt(passphrase.encode(),salt=salt,n=16384,r=8,p=1,dklen=32)


def create_bundle(source,destination,passphrase,key_material):
    source=Path(source).resolve();destination=Path(destination).resolve()
    if not (source/'hv_swim.db').is_file():raise ValueError('Source database does not exist')
    if destination.exists() or destination.is_relative_to(source):raise ValueError('Choose a new destination outside the live data directory')
    if not key_material.get('HV_DATA_ENCRYPTION_KEY'):raise ValueError('Include the data encryption key in the encrypted recovery bundle')
    manifest={};buffer=io.BytesIO()
    with tempfile.TemporaryDirectory() as temporary:
        snapshot=Path(temporary)/'hv_swim.db'
        with sqlite3.connect((source/'hv_swim.db').as_uri()+'?mode=ro',uri=True) as original:
            with sqlite3.connect(snapshot) as backup:original.backup(backup)
        with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
            if any(p.is_symlink() for p in source.rglob('*')):raise ValueError('Private uploads must not contain symlinks')
            files=[p for p in source.rglob('*') if p.is_file() and p.name not in ('hv_swim.db','hv_swim.db-wal','hv_swim.db-shm')]
            if any(p.is_symlink() or not p.resolve().is_relative_to(source) for p in files):raise ValueError('Private uploads must not contain symlinks')
            for name,path in [('hv_swim.db',snapshot),*((str(p.relative_to(source)),p) for p in files)]:
                data=path.read_bytes();manifest[name]=hashlib.sha256(data).hexdigest();archive.writestr('data/'+name,data)
            archive.writestr('keys.json',json.dumps(key_material))
            archive.writestr('manifest.json',json.dumps(manifest,sort_keys=True))
    salt=os.urandom(16);encrypted=SecretBox(key_for(passphrase,salt)).encrypt(buffer.getvalue())
    fd=os.open(destination,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'wb') as output:output.write(MAGIC+salt+encrypted)
    return {'files':len(manifest),'encrypted':True}


def restore_bundle(bundle,destination,passphrase):
    target=Path(destination).resolve()
    if target.exists():raise ValueError('Restore requires a new directory; existing data is never overwritten')
    raw=Path(bundle).read_bytes()
    if not raw.startswith(MAGIC):raise ValueError('Unrecognised recovery bundle')
    salt=raw[len(MAGIC):len(MAGIC)+16]
    try:data=SecretBox(key_for(passphrase,salt)).decrypt(raw[len(MAGIC)+16:])
    except CryptoError as exc:raise ValueError('Incorrect passphrase or damaged recovery bundle') from exc
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names=archive.namelist()
        if len(names)!=len(set(names)) or any(Path(name).is_absolute() or '..' in Path(name).parts for name in names):raise ValueError('Unsafe bundle paths')
        manifest=json.loads(archive.read('manifest.json'))
        if set(names)!={'manifest.json','keys.json',*('data/'+name for name in manifest)}:raise ValueError('Unexpected bundle files')
        for name,digest in manifest.items():
            if hashlib.sha256(archive.read('data/'+name)).hexdigest()!=digest:raise ValueError('Bundle checksum failed')
        target.mkdir(mode=0o700)
        for name in names:
            path=target/name;path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            path.write_bytes(archive.read(name));path.chmod(0o600)
    with sqlite3.connect((target/'data/hv_swim.db').as_uri()+'?mode=ro',uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Restored database integrity failed; restored folder retained for investigation')
    return {'files':len(manifest),'integrity':'ok','keys_restored':True}
