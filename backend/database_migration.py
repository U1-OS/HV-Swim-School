"""Verified SQLite snapshot transfer to an EMPTY PostgreSQL schema.

No target rows are deleted. DDL, data, indexes and triggers commit together only after
row-level checksums and sequence reconciliation pass. Credentials are never printed.
"""
import hashlib,json,sqlite3
from pathlib import Path
from .postgres_storage import Connection,install_helpers


def digest(rows):
    def canonical(v):
        if isinstance(v,(bytes,bytearray,memoryview)):return {'bytes':bytes(v).hex()}
        if isinstance(v,float) and v.is_integer():return int(v)
        return v
    return hashlib.sha256(json.dumps([[canonical(v) for v in row] for row in rows],sort_keys=True,separators=(',',':')).encode()).hexdigest()


def migrate(source,url):
    path=Path(source).resolve()
    if not path.is_file():raise ValueError('Source database does not exist')
    snapshot=sqlite3.connect(':memory:');snapshot.row_factory=sqlite3.Row
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as original:original.backup(snapshot)
    if snapshot.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or snapshot.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Source integrity check failed')
    db=Connection(url)
    try:
        db.lock()
        if db.raw.execute("SELECT 1 FROM information_schema.tables WHERE table_schema=current_schema() LIMIT 1").fetchone():raise ValueError('Target schema must be empty; existing tables are never replaced')
        install_helpers(db)
        tables={row['name']:row['sql'] for row in snapshot.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if not tables:raise ValueError('Source has no application tables')
        ordered=[];pending=dict(tables)
        while pending:
            ready=[name for name in pending if {r['table'] for r in snapshot.execute(f'PRAGMA foreign_key_list("{name}")')} <= set(ordered)|{name}]
            if not ready:raise ValueError('Source contains cyclic table dependencies; manual migration is required')
            for name in ready:
                db.execute(pending.pop(name));ordered.append(name)
        evidence=[]
        for name in ordered:
            columns=[r['name'] for r in snapshot.execute(f'PRAGMA table_info("{name}")')]
            quoted=','.join('"'+c.replace('"','""')+'"' for c in columns)
            # Stable order over all columns covers tables with and without numeric IDs.
            query=f'SELECT {quoted} FROM "{name}" ORDER BY {quoted}'
            original=[tuple(row) for row in snapshot.execute(query)]
            for row in original:db.execute(f'INSERT INTO "{name}"({quoted}) VALUES({",".join("?" for _ in columns)})',row)
            copied=[tuple(row.values()) for row in db.execute(query)]
            if len(original)!=len(copied) or digest(original)!=digest(copied):raise ValueError(f'Row reconciliation failed for {name}')
            if 'id' in columns:
                sequence=db.raw.execute('SELECT pg_get_serial_sequence(%s,%s)',(name,'id')).fetchone()[0]
                if sequence:
                    maximum=db.raw.execute(f'SELECT MAX(id) FROM "{name}"').fetchone()[0]
                    db.raw.execute('SELECT setval(%s,%s,%s)',(sequence,max(1,maximum or 1),maximum is not None))
            evidence.append({'table':name,'rows':len(original),'checksum':digest(original)})
        for row in snapshot.execute("SELECT type,sql FROM sqlite_master WHERE type IN ('index','trigger') AND sql IS NOT NULL ORDER BY type"):
            sql=row['sql']
            if row['type']=='trigger':sql=sql.replace('CREATE TRIGGER ','CREATE TRIGGER IF NOT EXISTS ',1)
            db.execute(sql)
        db.commit()
        return {'verified':True,'tables':evidence,'source_unchanged':True}
    except Exception:
        db.rollback();raise
    finally:db.close();snapshot.close()
