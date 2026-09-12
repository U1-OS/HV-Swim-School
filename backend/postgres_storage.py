"""PostgreSQL adapter for the application's parameterised DB-API calls.

Preserves row access and statement-level constraint recovery. Writes are serialised with
an advisory transaction lock during this migration phase; no connection string is logged.
"""
import re,sqlite3
import psycopg

class Row(dict):
    def __getitem__(self,key):return list(self.values())[key] if isinstance(key,int) else super().__getitem__(key)

class Result:
    def __init__(self,rows=(),rowcount=-1,lastrowid=None):self.rows=list(rows);self.rowcount=rowcount;self.lastrowid=lastrowid
    def fetchone(self):return self.rows.pop(0) if self.rows else None
    def fetchall(self):out=self.rows;self.rows=[];return out
    def __iter__(self):return iter(self.fetchall())


def parameters(sql,has_params):
    # Replace placeholders outside SQL literals; never interpolate parameter values.
    tokens=re.split(r"('(?:''|[^'])*'|\"(?:\"\"|[^\"])*\")",sql)
    return ''.join((part.replace('%','%%') if has_params else part) if i%2 else ((part.replace('%','%%') if has_params else part).replace('?','%s')) for i,part in enumerate(tokens))

class Connection:
    backend='postgresql'
    def __init__(self,url):
        self.raw=psycopg.connect(url,connect_timeout=10)
        self.raw.execute("SET statement_timeout='30s'");self.raw.execute("SET lock_timeout='15s'")
        self.raw.commit();self.locked=False
    def lock(self):
        if not self.locked:self.raw.execute('SELECT pg_advisory_xact_lock(73194026)');self.locked=True
    def commit(self):self.raw.commit();self.locked=False
    def rollback(self):self.raw.rollback();self.locked=False
    def close(self):self.raw.close()
    def _result(self,cursor,last=False):
        rows=[Row(zip([c.name for c in cursor.description],r)) for r in cursor.fetchall()] if cursor.description else []
        return Result(rows,cursor.rowcount,rows[0].get('id') if last and rows else None)
    def execute(self,sql,params=()):
        sql=sql.strip().rstrip(';')
        if sql.upper()=='BEGIN IMMEDIATE':self.lock();return Result()
        pragma=re.fullmatch(r'PRAGMA table_info\((\w+)\)',sql,re.I)
        if pragma:
            result=self.raw.execute("SELECT ordinal_position-1 cid,column_name name,data_type type,CASE is_nullable WHEN 'NO' THEN 1 ELSE 0 END notnull,column_default dflt_value,0 pk FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=%s ORDER BY ordinal_position",(pragma[1],))
            return self._result(result)
        if 'sqlite_master' in sql:return Result([Row(sql='')])
        if sql.lower() in ('pragma quick_check','pragma integrity_check'):
            value=self.raw.execute("SELECT count(*) FROM pg_index WHERE NOT indisvalid").fetchone()[0]
            return Result([Row(integrity='ok' if value==0 else 'invalid_index')])
        if sql.lower()=='pragma foreign_key_check':
            return self._result(self.raw.execute("SELECT conname FROM pg_constraint WHERE contype='f' AND NOT convalidated"))
        if sql.lower()=='pragma journal_mode':return Result([Row(journal_mode='postgresql')])
        if sql.upper().startswith('PRAGMA'):return Result()
        if sql.upper() in ('BEGIN','COMMIT','ROLLBACK'):
            if sql.upper()=='COMMIT':self.commit()
            elif sql.upper()=='ROLLBACK':self.rollback()
            else:self.lock()
            return Result()
        mutation=bool(re.match(r'(INSERT|UPDATE|DELETE|CREATE|ALTER|DROP)',sql,re.I))
        if mutation:self.lock()
        trigger=re.fullmatch(r"CREATE TRIGGER IF NOT EXISTS (\w+) BEFORE (UPDATE(?: OF [a-z_,]+)?|DELETE) ON (\w+) BEGIN SELECT RAISE\(ABORT,'[^']*'\); END",sql,re.I)
        if trigger:
            name,operation,table=trigger.groups()
            self.raw.execute("CREATE OR REPLACE FUNCTION hv_immutable_history() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN RAISE EXCEPTION 'Accounting history is immutable' USING ERRCODE='23514'; END$$")
            self.raw.execute(f"DROP TRIGGER IF EXISTS {name} ON {table}")
            self.raw.execute(f"CREATE TRIGGER {name} BEFORE {operation} ON {table} FOR EACH ROW EXECUTE FUNCTION hv_immutable_history()")
            return Result()
        sql=re.sub(r'\bINTEGER PRIMARY KEY(?: AUTOINCREMENT)?', 'BIGSERIAL PRIMARY KEY',sql).replace('COLLATE NOCASE','').replace(' BLOB',' BYTEA').replace(' REAL',' DOUBLE PRECISION')
        sql=sql.replace("date(week_start,'+6 days')","to_char(week_start::date+6,'YYYY-MM-DD')")
        legacy="date(substr(clock_in,1,10),printf('-%d days',(CAST(strftime('%w',substr(clock_in,1,10)) AS INTEGER)+6)%7))"
        sql=sql.replace(legacy,"to_char(date_trunc('week',left(clock_in,10)::date),'YYYY-MM-DD')")
        sql=re.sub(r'\bprintf\(', 'hv_printf(',sql,flags=re.I)
        if re.match(r'INSERT OR IGNORE',sql,re.I):sql=re.sub(r'INSERT OR IGNORE','INSERT',sql,flags=re.I)+' ON CONFLICT DO NOTHING'
        insert=re.match(r'INSERT INTO\s+(\w+)',sql,re.I)
        returning=False
        if insert and 'RETURNING' not in sql.upper():
            has_id=self.raw.execute("SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=%s AND column_name='id'",(insert[1],)).fetchone()
            if has_id:sql+=' RETURNING id';returning=True
        try:
            with self.raw.transaction():
                return self._result(self.raw.execute(parameters(sql,bool(params)),tuple(int(v) if isinstance(v,bool) else v for v in params) or None),returning)
        except psycopg.IntegrityError as exc:raise sqlite3.IntegrityError(str(exc).split('\n')[0]) from exc
    def executemany(self,sql,values):
        result=None
        for value in values:result=self.execute(sql,value)
        return result or Result()
    def executescript(self,sql):
        for statement in sql.split(';'):
            if statement.strip():self.execute(statement)


def install_helpers(connection):
    connection.lock()
    connection.raw.execute("""CREATE OR REPLACE FUNCTION instr(haystack text,needle text) RETURNS integer LANGUAGE sql IMMUTABLE AS $$ SELECT strpos(haystack,needle) $$""")
    connection.raw.execute("""CREATE OR REPLACE FUNCTION hv_printf(pattern text,value bigint) RETURNS text LANGUAGE plpgsql IMMUTABLE AS $$
    DECLARE digits text;
    BEGIN
      IF position('%06d' in pattern)>0 THEN digits:=lpad(value::text,6,'0');RETURN replace(pattern,'%06d',digits);END IF;
      IF position('%04d' in pattern)>0 THEN digits:=lpad(value::text,4,'0');RETURN replace(pattern,'%04d',digits);END IF;
      RETURN replace(pattern,'%d',value::text);
    END $$""")
