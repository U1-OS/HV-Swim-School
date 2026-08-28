from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Generator, Iterable

from .config import DB_PATH
from .security import now_iso, password_hash


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('customer','staff','admin')),
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL DEFAULT '',
  phone TEXT,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  csrf_token TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS login_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL,
  ip_address TEXT NOT NULL,
  success INTEGER NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS swimmers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  customer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  date_of_birth TEXT,
  level TEXT NOT NULL,
  emergency_contact TEXT,
  medical_notes TEXT,
  photo_consent INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS locations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  address TEXT NOT NULL,
  latitude REAL,
  longitude REAL,
  venue_type TEXT NOT NULL,
  parking TEXT NOT NULL,
  accessibility TEXT NOT NULL,
  public_status TEXT NOT NULL,
  sensor_enabled INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS pool_readings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  location_id INTEGER NOT NULL REFERENCES locations(id),
  temperature REAL,
  status TEXT NOT NULL CHECK (status IN ('open','changed','closed')),
  note TEXT,
  verified_by INTEGER REFERENCES users(id),
  source TEXT NOT NULL DEFAULT 'manual',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pool_checklists (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  location_id INTEGER NOT NULL REFERENCES locations(id),
  staff_id INTEGER NOT NULL REFERENCES users(id),
  deck_safe INTEGER NOT NULL,
  first_aid_ready INTEGER NOT NULL,
  equipment_ready INTEGER NOT NULL,
  water_checked INTEGER NOT NULL,
  notes TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS classes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  level TEXT NOT NULL,
  location_id INTEGER NOT NULL REFERENCES locations(id),
  instructor_id INTEGER REFERENCES users(id),
  weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
  start_time TEXT NOT NULL,
  duration_minutes INTEGER NOT NULL,
  capacity INTEGER NOT NULL,
  price_cents INTEGER NOT NULL,
  active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS bookings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  class_id INTEGER NOT NULL REFERENCES classes(id),
  swimmer_id INTEGER NOT NULL REFERENCES swimmers(id),
  status TEXT NOT NULL CHECK (status IN ('confirmed','cancelled','completed')),
  created_at TEXT NOT NULL,
  UNIQUE(class_id, swimmer_id, status)
);
CREATE TABLE IF NOT EXISTS waitlist (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  class_id INTEGER NOT NULL REFERENCES classes(id),
  swimmer_id INTEGER NOT NULL REFERENCES swimmers(id),
  position INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'waiting',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rosters (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  staff_id INTEGER NOT NULL REFERENCES users(id),
  location_id INTEGER NOT NULL REFERENCES locations(id),
  shift_date TEXT NOT NULL,
  start_time TEXT NOT NULL,
  end_time TEXT NOT NULL,
  role_label TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'published'
);
CREATE TABLE IF NOT EXISTS time_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  staff_id INTEGER NOT NULL REFERENCES users(id),
  location_id INTEGER NOT NULL REFERENCES locations(id),
  clock_in TEXT NOT NULL,
  clock_out TEXT,
  latitude REAL,
  longitude REAL,
  accuracy_metres REAL,
  hours REAL,
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','submitted','approved','exported')),
  approved_by INTEGER REFERENCES users(id),
  approved_at TEXT,
  xero_timesheet_id TEXT
);
CREATE TABLE IF NOT EXISTS qualifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  staff_id INTEGER NOT NULL REFERENCES users(id),
  qualification_type TEXT NOT NULL,
  reference_number TEXT,
  expiry_date TEXT,
  status TEXT NOT NULL DEFAULT 'current',
  verified_at TEXT
);
CREATE TABLE IF NOT EXISTS notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER REFERENCES users(id),
  audience_role TEXT,
  title TEXT NOT NULL,
  message TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'info',
  delivery_channels TEXT NOT NULL DEFAULT '["in_app"]',
  read_at TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sku TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  category TEXT NOT NULL,
  description TEXT NOT NULL,
  price_cents INTEGER NOT NULL,
  sizes TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'planned',
  emoji TEXT NOT NULL,
  shopify_gid TEXT,
  sample_status TEXT NOT NULL DEFAULT 'not_ordered',
  cost_cents INTEGER,
  supplier_route TEXT,
  personalisation TEXT
);
CREATE TABLE IF NOT EXISTS integration_connections (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  provider TEXT UNIQUE NOT NULL,
  status TEXT NOT NULL DEFAULT 'not_connected',
  encrypted_tokens BLOB,
  metadata TEXT NOT NULL DEFAULT '{}',
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS oauth_states (
  state TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  user_id INTEGER NOT NULL REFERENCES users(id),
  expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS enquiries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT NOT NULL,
  phone TEXT,
  swimmer_age TEXT,
  experience TEXT,
  support_needs TEXT,
  status TEXT NOT NULL DEFAULT 'new',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS site_settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_by INTEGER REFERENCES users(id),
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER REFERENCES users(id),
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT,
  detail TEXT NOT NULL DEFAULT '{}',
  ip_address TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_bookings_class ON bookings(class_id, status);
CREATE INDEX IF NOT EXISTS idx_pool_readings_location ON pool_readings(location_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_time_entries_status ON time_entries(status, staff_id);
-- Both rate limits below scan on every sign-in and every public enquiry, and both tables
-- grow with traffic, so they need covering indexes.
CREATE INDEX IF NOT EXISTS idx_audit_action_ip ON audit_log(action, ip_address, created_at);
CREATE INDEX IF NOT EXISTS idx_login_attempts_lookup ON login_attempts(email, ip_address, created_at);
"""


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


@contextmanager
def db_session() -> Generator[sqlite3.Connection, None, None]:
    db = connect()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def audit(db: sqlite3.Connection, user_id: int | None, action: str, entity_type: str, entity_id: str | int | None = None, detail: dict | None = None, ip_address: str | None = None) -> None:
    db.execute(
        "INSERT INTO audit_log(user_id,action,entity_type,entity_id,detail,ip_address,created_at) VALUES(?,?,?,?,?,?,?)",
        (user_id, action, entity_type, str(entity_id) if entity_id is not None else None, json.dumps(detail or {}), ip_address, now_iso()),
    )


def rows(rows: Iterable[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]


def initialise_database() -> None:
    with db_session() as db:
        db.executescript(SCHEMA)
        # Database-level guards against double booking. Application code already checks,
        # but two requests arriving together can both pass that check before either writes.
        # Created defensively: an older database containing duplicates must not stop startup.
        for statement in (
            "CREATE UNIQUE INDEX IF NOT EXISTS uniq_booking_confirmed ON bookings(class_id, swimmer_id) WHERE status='confirmed'",
            "CREATE UNIQUE INDEX IF NOT EXISTS uniq_waitlist_waiting ON waitlist(class_id, swimmer_id) WHERE status='waiting'",
        ):
            try:
                db.execute(statement)
            except sqlite3.IntegrityError:
                # Existing duplicates need clearing by hand before the guard can apply.
                pass
        enquiry_columns = {row[1] for row in db.execute("PRAGMA table_info(enquiries)")}
        for column, definition in {
            "swimmer_name": "TEXT",
            "program_interest": "TEXT",
            "preferred_class": "TEXT",
            "preferred_days": "TEXT",
            "contact_method": "TEXT NOT NULL DEFAULT 'email'",
        }.items():
            if column not in enquiry_columns:
                db.execute(f"ALTER TABLE enquiries ADD COLUMN {column} {definition}")
        product_columns = {row[1] for row in db.execute("PRAGMA table_info(products)")}
        for column, definition in {
            "sample_status": "TEXT NOT NULL DEFAULT 'not_ordered'",
            "cost_cents": "INTEGER",
            "supplier_route": "TEXT",
            "personalisation": "TEXT",
        }.items():
            if column not in product_columns:
                db.execute(f"ALTER TABLE products ADD COLUMN {column} {definition}")
        created = now_iso()
        base_products = [
            ("HV-SWIMWEAR", "HV Swim Team Swimwear", "Swimwear", "Logo-branded training swimwear for children and adults.", 5995, '["Kids 4-14","Adult XS-XL"]', "planned", "🩱"),
            ("HV-TOWEL", "HV Swim Logo Towel", "Towels", "Soft pool towel with embroidered HV Swim branding.", 3495, '["One size"]', "planned", "▤"),
            ("HV-BOTTLE", "HV Swim Drink Bottle", "Bottles", "Named pool-deck bottle with HV Swim branding.", 1995, '["650ml"]', "planned", "🥤"),
            ("HV-GOGGLES", "HV Swim Goggles", "Equipment", "Comfortable training goggles for regular lessons.", 2495, '["Junior","Adult"]', "planned", "🥽"),
            ("HV-BAG", "HV Swim Pool-Deck Bag", "Bags", "Ventilated swim bag for wet gear and lesson essentials.", 3995, '["One size"]', "planned", "🎒"),
            ("HV-CAP", "HV Swim Team Cap", "Caps", "Silicone swim cap with team branding.", 1495, '["Junior","Adult"]', "planned", "🧢"),
            ("HV-STAFF-POLO", "HV Swim Staff Polo", "Uniforms", "Breathable navy performance polo with embroidered HV Swim identity.", 4495, '["XS","S","M","L","XL","2XL"]', "planned", "◈"),
            ("HV-TEAM-HOODIE", "HV Swim Team Hoodie", "Uniforms", "Warm branded hoodie for staff, families and pool-deck arrivals.", 6495, '["Kids 6-14","Adult XS-2XL"]', "planned", "◇"),
            ("HV-INSTRUCTOR-CAP", "HV Swim Instructor Cap", "Uniforms", "Lightweight branded cap for outdoor and seasonal pool work.", 2495, '["Adjustable"]', "planned", "◌"),
        ]
        db.executemany("INSERT OR IGNORE INTO products(sku,title,category,description,price_cents,sizes,status,emoji) VALUES(?,?,?,?,?,?,?,?)", base_products)
        production_defaults = {
            "HV-SWIMWEAR": ("specialist_uniform", "HV Swim identity; name placement under review"),
            "HV-TOWEL": ("vistaprint_or_specialist", "Embroidered identity; optional swimmer name"),
            "HV-BOTTLE": ("vistaprint", "Named bottle after wash and rub testing"),
            "HV-GOGGLES": ("specialist_uniform", "No product personalisation planned"),
            "HV-BAG": ("printify_or_vistaprint", "HV Swim mark and swimmer name panel"),
            "HV-CAP": ("specialist_uniform", "Durable HV Swim team print"),
            "HV-STAFF-POLO": ("vistaprint", "Embroidered identity; role or staff name optional"),
            "HV-TEAM-HOODIE": ("printify", "HV Swim decoration; individual name optional"),
            "HV-INSTRUCTOR-CAP": ("printify_or_vistaprint", "Embroidered identity and instructor label"),
        }
        for sku, (supplier_route, personalisation) in production_defaults.items():
            db.execute(
                "UPDATE products SET supplier_route=COALESCE(NULLIF(supplier_route,''),?),personalisation=COALESCE(NULLIF(personalisation,''),?) WHERE sku=?",
                (supplier_route, personalisation, sku),
            )
        for provider in ("xero", "shopify", "printify", "vistaprint", "email", "sms", "web_push", "pool_sensor"):
            db.execute("INSERT OR IGNORE INTO integration_connections(provider,status,metadata,updated_at) VALUES(?,?,?,?)", (provider, "not_connected", "{}", created))
        site_defaults = {
            "announcement_enabled": "0",
            "announcement_text": "Enrolments are open — ask about the best lesson for your swimmer.",
            "enrolment_status": "open",
            "hero_eyebrow": "Bendigo's confidence-first swim school",
            "hero_heading": "Confidence starts",
            "hero_accent": "in the water.",
            "hero_intro": "Personal, inclusive swimming lessons from four months to adults — taught with patience, safety and genuine care by a team that knows every swimmer is different.",
            "primary_cta": "Find the right lesson",
        }
        db.executemany("INSERT OR IGNORE INTO site_settings(key,value,updated_at) VALUES(?,?,?)", [(key, value, created) for key, value in site_defaults.items()])
        # Keep the bundled demo account aligned with the current business team.
        db.execute("UPDATE users SET first_name='Laura',last_name='' WHERE email='admin@hvswim.demo'")
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            return
        demo_users = [
            ("parent@hvswim.demo", "FamilyDemo!26", "customer", "Jordan", "Smith", "0413 000 101"),
            ("staff@hvswim.demo", "StaffDemo!26", "staff", "Alex", "Lee", "0413 000 102"),
            ("admin@hvswim.demo", "AdminDemo!26", "admin", "Laura", "", "0413 462 112"),
            ("casey@hvswim.demo", "StaffDemo!26", "staff", "Casey", "Morgan", "0413 000 103"),
        ]
        for email, password, role, first, last, phone in demo_users:
            db.execute(
                "INSERT INTO users(email,password_hash,role,first_name,last_name,phone,created_at) VALUES(?,?,?,?,?,?,?)",
                (email, password_hash(password), role, first, last, phone, created),
            )
        user_ids = {row["email"]: row["id"] for row in db.execute("SELECT id,email FROM users")}
        locations = [
            ("wood-street", "Wood Street Indoor Pool", "76 Wood Street, California Gully VIC 3556", -36.7339, 144.2595, "Private indoor heated pool", "On-site and nearby street parking", "Wheelchair access and public toilets listed; individual pool-entry needs should be confirmed", "Lessons running", 0),
            ("bendigo-east", "Bendigo East Swimming Pool", "31 Lansell Street, East Bendigo VIC 3550", -36.7507, 144.3018, "Heated seasonal community facility", "Off-street parking", "Contact venue before booking to confirm pool-entry assistance", "Closed for winter", 0),
        ]
        db.executemany("INSERT INTO locations(slug,name,address,latitude,longitude,venue_type,parking,accessibility,public_status,sensor_enabled) VALUES(?,?,?,?,?,?,?,?,?,?)", locations)
        location_ids = {row["slug"]: row["id"] for row in db.execute("SELECT id,slug FROM locations")}
        db.execute(
            "INSERT INTO swimmers(customer_id,first_name,last_name,date_of_birth,level,emergency_contact,medical_notes,photo_consent,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (user_ids["parent@hvswim.demo"], "Mia", "Smith", "2018-05-14", "Learn to Swim 3", "Jordan Smith · 0413 000 101", "No medical alerts in demo record", 1, created),
        )
        db.execute(
            "INSERT INTO swimmers(customer_id,first_name,last_name,date_of_birth,level,emergency_contact,medical_notes,photo_consent,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (user_ids["parent@hvswim.demo"], "Noah", "Smith", "2024-01-22", "Infant Aquatics", "Jordan Smith · 0413 000 101", "No medical alerts in demo record", 0, created),
        )
        classes = [
            ("INF-A-MON", "Infant Aquatics", "Infant Aquatics", location_ids["wood-street"], user_ids["staff@hvswim.demo"], 0, "09:00", 30, 5, 2200),
            ("LTS1-TUE", "Learn to Swim 1", "Beginner", location_ids["wood-street"], user_ids["casey@hvswim.demo"], 1, "15:45", 30, 5, 2400),
            ("LTS3-THU", "Learn to Swim 3", "Learn to Swim 3", location_ids["wood-street"], user_ids["staff@hvswim.demo"], 3, "16:15", 45, 5, 2600),
            ("PRIV-FRI", "Private Lesson", "All levels", location_ids["wood-street"], user_ids["staff@hvswim.demo"], 4, "17:10", 30, 1, 5200),
            ("STROKE-SAT", "Stroke Development", "Stroke Development", location_ids["wood-street"], user_ids["casey@hvswim.demo"], 5, "10:30", 45, 6, 2800),
        ]
        db.executemany("INSERT INTO classes(code,title,level,location_id,instructor_id,weekday,start_time,duration_minutes,capacity,price_cents) VALUES(?,?,?,?,?,?,?,?,?,?)", classes)
        swimmer_ids = {row["first_name"]: row["id"] for row in db.execute("SELECT id,first_name FROM swimmers")}
        class_ids = {row["code"]: row["id"] for row in db.execute("SELECT id,code FROM classes")}
        db.execute("INSERT INTO bookings(class_id,swimmer_id,status,created_at) VALUES(?,?,?,?)", (class_ids["LTS3-THU"], swimmer_ids["Mia"], "confirmed", created))
        db.execute("INSERT INTO bookings(class_id,swimmer_id,status,created_at) VALUES(?,?,?,?)", (class_ids["INF-A-MON"], swimmer_ids["Noah"], "confirmed", created))
        db.execute("INSERT INTO waitlist(class_id,swimmer_id,position,status,created_at) VALUES(?,?,?,?,?)", (class_ids["LTS1-TUE"], swimmer_ids["Mia"], 1, "waiting", created))
        today = date.today()
        for offset in range(0, 7):
            shift_day = today + timedelta(days=offset)
            if shift_day.weekday() < 6:
                db.execute("INSERT INTO rosters(staff_id,location_id,shift_date,start_time,end_time,role_label) VALUES(?,?,?,?,?,?)", (user_ids["staff@hvswim.demo"], location_ids["wood-street"], shift_day.isoformat(), "08:45", "17:45", "Instructor"))
        submitted_in = (datetime.now(timezone.utc) - timedelta(days=1, hours=8)).isoformat()
        submitted_out = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        db.execute("INSERT INTO time_entries(staff_id,location_id,clock_in,clock_out,hours,status) VALUES(?,?,?,?,?,?)", (user_ids["staff@hvswim.demo"], location_ids["wood-street"], submitted_in, submitted_out, 8.0, "submitted"))
        qualifications = [
            (user_ids["staff@hvswim.demo"], "Working With Children Check", "DEMO-WWCC-102", (today + timedelta(days=210)).isoformat(), "current", created),
            (user_ids["staff@hvswim.demo"], "CPR", "DEMO-CPR-208", (today + timedelta(days=42)).isoformat(), "expiring", created),
            (user_ids["staff@hvswim.demo"], "Swim Teacher Accreditation", "DEMO-STA-414", (today + timedelta(days=330)).isoformat(), "current", created),
        ]
        db.executemany("INSERT INTO qualifications(staff_id,qualification_type,reference_number,expiry_date,status,verified_at) VALUES(?,?,?,?,?,?)", qualifications)
        notifications = [
            (user_ids["parent@hvswim.demo"], None, "Thursday lesson confirmed", "Mia's Learn to Swim 3 lesson is confirmed for 4:15 pm at Wood Street.", "booking", '["in_app","email"]', created),
            (user_ids["staff@hvswim.demo"], None, "Daily pool check due", "Publish today's Wood Street water temperature before the first lesson.", "safety", '["in_app","push"]', created),
            (None, "admin", "One qualification expires soon", "Alex Lee's CPR record expires within 60 days.", "compliance", '["in_app"]', created),
        ]
        db.executemany("INSERT INTO notifications(user_id,audience_role,title,message,kind,delivery_channels,created_at) VALUES(?,?,?,?,?,?,?)", notifications)
        audit(db, user_ids["admin@hvswim.demo"], "seed_database", "system", detail={"mode": "demo"})
