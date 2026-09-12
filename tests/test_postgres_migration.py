import os,sqlite3,hashlib
from urllib.parse import urlsplit,parse_qsl,urlencode,urlunsplit,quote
import pytest

@pytest.mark.skipif(not os.environ.get('HV_TEST_POSTGRES_URL'),reason='Requires isolated PostgreSQL test server')
def test_migration_preserves_values_sequences_guards_and_refuses_existing_target(tmp_path):
    import psycopg
    from backend.database_migration import migrate
    source=tmp_path/'source.db'
    with sqlite3.connect(source) as db:
        db.executescript('''CREATE TABLE users(id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT UNIQUE);
        CREATE TABLE ledger(id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id),hours REAL,note BLOB);
        INSERT INTO users VALUES(17,'fictional@example.test');
        CREATE TRIGGER immutable_ledger BEFORE UPDATE ON ledger BEGIN SELECT RAISE(ABORT,'Accounting history is immutable'); END;''')
        db.execute('INSERT INTO ledger VALUES(25,17,?,?)',(3.141592653589793,b'private-test-bytes'))
    original=hashlib.sha256(source.read_bytes()).hexdigest()
    base=os.environ['HV_TEST_POSTGRES_URL'];schema='migration_test'
    with psycopg.connect(base,autocommit=True) as raw:raw.execute(f'CREATE SCHEMA {schema}')
    parts=urlsplit(base);query=dict(parse_qsl(parts.query));query['options']=f'-c search_path={schema}'
    target=urlunsplit((parts.scheme,parts.netloc,parts.path,urlencode(query,quote_via=quote),parts.fragment))
    try:
        result=migrate(source,target);assert result['verified'] and sum(t['rows'] for t in result['tables'])==2
        assert hashlib.sha256(source.read_bytes()).hexdigest()==original
        with psycopg.connect(target) as raw:
            assert raw.execute("INSERT INTO users(email) VALUES('next@example.test') RETURNING id").fetchone()[0]==18
            assert raw.execute('SELECT hours,note FROM ledger').fetchone()==(3.141592653589793,b'private-test-bytes')
        with pytest.raises(ValueError,match='empty'):migrate(source,target)
        with psycopg.connect(target) as raw:
            with pytest.raises(psycopg.IntegrityError):raw.execute('UPDATE ledger SET hours=2')
    finally:
        with psycopg.connect(base,autocommit=True) as raw:raw.execute(f'DROP SCHEMA {schema} CASCADE')
