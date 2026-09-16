import sqlite3
import pytest
from nacl.secret import SecretBox
from backend.recovery import create_bundle,restore_bundle

def test_database_upload_and_key_recovery(tmp_path):
    source=tmp_path/'original';source.mkdir();(source/'uploads').mkdir()
    secret=b's'*32
    encrypted=bytes(SecretBox(secret).encrypt(b'fictional private note'))
    with sqlite3.connect(source/'hv_swim.db') as db:
        db.execute('CREATE TABLE example(id INTEGER PRIMARY KEY,note BLOB)');db.execute('INSERT INTO example VALUES(1,?)',(encrypted,))
    (source/'uploads/certificate.bin').write_bytes(b'fictional certificate')
    bundle=tmp_path/'backup.hvbackup';phrase='a long fictional recovery phrase'
    create_bundle(source,bundle,phrase,{'HV_DATA_ENCRYPTION_KEY':secret.hex()})
    assert b'fictional private note' not in bundle.read_bytes()
    with pytest.raises(ValueError):restore_bundle(bundle,tmp_path/'wrong','an incorrect long recovery phrase')
    result=restore_bundle(bundle,tmp_path/'restored',phrase)
    assert result['integrity']=='ok'
    import json
    key=bytes.fromhex(json.loads((tmp_path/'restored/keys.json').read_text())['HV_DATA_ENCRYPTION_KEY'])
    with sqlite3.connect(tmp_path/'restored/data/hv_swim.db') as db:restored=db.execute('SELECT note FROM example').fetchone()[0]
    assert SecretBox(key).decrypt(restored)==b'fictional private note'
    assert (tmp_path/'restored/data/uploads/certificate.bin').read_bytes()==b'fictional certificate'
    with pytest.raises(ValueError):restore_bundle(bundle,tmp_path/'restored',phrase)
    with pytest.raises(ValueError):create_bundle(source,bundle,phrase,{'HV_DATA_ENCRYPTION_KEY':'key'})
