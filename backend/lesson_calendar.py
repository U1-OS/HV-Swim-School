"""Dated occurrences shared by family lessons, registers and public daily schedules."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

SCHEMA = """
CREATE TABLE IF NOT EXISTS calendar_closures(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 start_date TEXT NOT NULL,end_date TEXT NOT NULL,
 location_id INTEGER REFERENCES locations(id),reason TEXT NOT NULL,
 created_by INTEGER NOT NULL REFERENCES users(id),created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lesson_exceptions(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 class_id INTEGER NOT NULL REFERENCES classes(id),original_date TEXT NOT NULL,
 action TEXT NOT NULL CHECK(action IN ('cancel','move')),
 target_date TEXT,target_time TEXT,reason TEXT NOT NULL,
 created_by INTEGER NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,
 UNIQUE(class_id,original_date)
);
"""


def closed(db, location_id, day):
    return db.execute("SELECT reason FROM calendar_closures WHERE start_date<=? AND end_date>=? AND (location_id IS NULL OR location_id=?) ORDER BY id DESC LIMIT 1", (day,day,location_id)).fetchone()


def term(db, day):
    return db.execute("SELECT * FROM school_terms WHERE status IN ('active','closed') AND start_date<=? AND end_date>=? ORDER BY id DESC LIMIT 1",(day,day)).fetchone()


def on_date(db, day, instructor_id=None, class_id=None):
    day = day.isoformat() if isinstance(day,date) else day
    selected=date.fromisoformat(day)
    output=[]
    for item in db.execute("SELECT c.*,l.name location_name,l.slug location_slug,u.first_name instructor_first,u.last_name instructor_last FROM classes c JOIN locations l ON l.id=c.location_id LEFT JOIN users u ON u.id=c.instructor_id WHERE c.active=1 AND (CAST(? AS INTEGER) IS NULL OR c.id=?) ORDER BY c.start_time,c.id",(class_id,class_id)):
        if instructor_id is not None and item['instructor_id']!=instructor_id: continue
        if closed(db,item['location_id'],day): continue
        moved=db.execute("SELECT * FROM lesson_exceptions WHERE class_id=? AND action='move' AND target_date=?",(item['id'],day)).fetchall()
        occurrences=[]
        if selected.weekday()==item['weekday'] and term(db,day):
            exception=db.execute("SELECT * FROM lesson_exceptions WHERE class_id=? AND original_date=?",(item['id'],day)).fetchone()
            if not exception: occurrences.append((day,item['start_time'],None))
        occurrences.extend((m['original_date'],m['target_time'],m['reason']) for m in moved if term(db,m['original_date']))
        for original,start,reason in occurrences:
            output.append({**dict(item),'occurrence_date':day,'original_date':original,'start_time':start,'rescheduled':original!=day or reason is not None,'calendar_note':reason})
    return sorted(output,key=lambda x:(x['start_time'],x['id']))


def next_occurrence(db,class_id,after=None,days=180):
    after=after or datetime.now(ZoneInfo('Australia/Melbourne'))
    for item in dates_for_class(db,class_id,after.date(),days):
        at=datetime.fromisoformat(f"{item['occurrence_date']}T{item['start_time']}").replace(tzinfo=ZoneInfo('Australia/Melbourne'))
        if at>after: return item
    return None


def dates_for_class(db,class_id,start,days=180):
    item=db.execute('SELECT weekday FROM classes WHERE id=? AND active=1',(class_id,)).fetchone()
    if not item: return []
    end=start+timedelta(days=days)
    first=start+timedelta(days=(item['weekday']-start.weekday())%7)
    candidates={first+timedelta(days=n) for n in range(0,days+1,7) if first+timedelta(days=n)<=end}
    candidates.update(date.fromisoformat(row[0]) for row in db.execute("SELECT target_date FROM lesson_exceptions WHERE class_id=? AND action='move' AND target_date>=? AND target_date<=?",(class_id,start.isoformat(),end.isoformat())))
    return [item for day in sorted(candidates) for item in on_date(db,day,class_id=class_id)]
