from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Generator, Iterable

from .config import DB_PATH, settings
from .security import business_today, now_iso, password_hash


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
  xero_employee_id TEXT,
  xero_payroll_calendar_id TEXT,
  must_change_password INTEGER NOT NULL DEFAULT 0,
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
  created_at TEXT NOT NULL
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
CREATE TABLE IF NOT EXISTS association_credentials (
  key TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  short_label TEXT NOT NULL,
  directory_url TEXT NOT NULL,
  requirements_url TEXT NOT NULL,
  membership_reference TEXT,
  valid_until TEXT,
  usage_rights_confirmed INTEGER NOT NULL DEFAULT 0,
  internal_notes TEXT,
  artwork_filename TEXT,
  artwork_sha256 TEXT,
  verified_by INTEGER REFERENCES users(id),
  verified_at TEXT,
  updated_at TEXT NOT NULL
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
CREATE TABLE IF NOT EXISTS notification_receipts (
  notification_id INTEGER NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  read_at TEXT NOT NULL,
  PRIMARY KEY (notification_id, user_id)
);
CREATE TABLE IF NOT EXISTS achievement_templates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  certificate_style TEXT NOT NULL,
  badge_symbol TEXT NOT NULL,
  brand_label TEXT NOT NULL DEFAULT 'HV Swim School Bendigo',
  sort_order INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS swimmer_achievements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  certificate_reference TEXT UNIQUE NOT NULL,
  template_id INTEGER NOT NULL REFERENCES achievement_templates(id),
  swimmer_id INTEGER NOT NULL REFERENCES swimmers(id),
  class_id INTEGER REFERENCES classes(id),
  certificate_style TEXT NOT NULL,
  evidence_note TEXT NOT NULL,
  private_staff_note TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','revoked')),
  awarded_by INTEGER NOT NULL REFERENCES users(id),
  awarded_at TEXT NOT NULL,
  revoked_by INTEGER REFERENCES users(id),
  revoked_at TEXT,
  revocation_reason TEXT,
  CHECK (
    (status='active' AND revoked_by IS NULL AND revoked_at IS NULL AND revocation_reason IS NULL)
    OR
    (status='revoked' AND revoked_by IS NOT NULL AND revoked_at IS NOT NULL AND length(revocation_reason)>=5)
  )
);
CREATE TABLE IF NOT EXISTS support_tickets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  reference TEXT UNIQUE NOT NULL,
  customer_id INTEGER REFERENCES users(id),
  category TEXT NOT NULL CHECK (category IN ('lessons','bookings','billing','merchandise','pool_conditions','accessibility_support','app_help','other')),
  name TEXT NOT NULL,
  email TEXT NOT NULL,
  phone TEXT,
  subject TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new','open','waiting_customer','resolved','closed')),
  priority TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('low','normal','high','urgent')),
  assigned_to INTEGER REFERENCES users(id),
  source TEXT NOT NULL CHECK (source IN ('public_widget','customer_portal')),
  consent_acknowledged INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  resolved_at TEXT
);
CREATE TABLE IF NOT EXISTS support_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ticket_id INTEGER NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
  author_user_id INTEGER REFERENCES users(id),
  author_role TEXT NOT NULL CHECK (author_role IN ('guest','customer','staff','admin','system')),
  message TEXT NOT NULL,
  visibility TEXT NOT NULL DEFAULT 'customer' CHECK (visibility IN ('customer','internal')),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS public_alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  severity TEXT NOT NULL CHECK (severity IN ('closure','change','reopening','information')),
  title TEXT NOT NULL,
  message TEXT NOT NULL,
  location_id INTEGER REFERENCES locations(id),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','resolved')),
  source TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual','pool_status')),
  published_by INTEGER NOT NULL REFERENCES users(id),
  published_at TEXT NOT NULL,
  updated_by INTEGER NOT NULL REFERENCES users(id),
  updated_at TEXT NOT NULL,
  resolved_by INTEGER REFERENCES users(id),
  resolved_at TEXT,
  resolution_note TEXT,
  CHECK (
    (status='active' AND resolved_by IS NULL AND resolved_at IS NULL)
    OR
    (status='resolved' AND resolved_by IS NOT NULL AND resolved_at IS NOT NULL)
  )
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
  personalisation TEXT,
  audience TEXT NOT NULL DEFAULT 'family',
  fulfilment_mode TEXT NOT NULL DEFAULT 'manual',
  printify_product_id TEXT,
  supplier_reference TEXT
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
  enquiry_type TEXT NOT NULL DEFAULT 'lesson',
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
CREATE INDEX IF NOT EXISTS idx_notification_receipts_user ON notification_receipts(user_id, read_at DESC);
CREATE INDEX IF NOT EXISTS idx_swimmer_achievements_swimmer ON swimmer_achievements(swimmer_id, status, awarded_at DESC);
CREATE INDEX IF NOT EXISTS idx_swimmer_achievements_awarded_by ON swimmer_achievements(awarded_by, awarded_at DESC);
CREATE INDEX IF NOT EXISTS idx_support_tickets_customer ON support_tickets(customer_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_support_tickets_email ON support_tickets(email COLLATE NOCASE, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_support_tickets_queue ON support_tickets(status, priority, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_support_messages_ticket ON support_messages(ticket_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_public_alerts_active ON public_alerts(status, severity, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_public_alerts_location ON public_alerts(location_id, status, source);
CREATE INDEX IF NOT EXISTS idx_time_entries_status ON time_entries(status, staff_id);
-- Both rate limits below scan on every sign-in and every public enquiry, and both tables
-- grow with traffic, so they need covering indexes.
CREATE INDEX IF NOT EXISTS idx_audit_action_ip ON audit_log(action, ip_address, created_at);
CREATE INDEX IF NOT EXISTS idx_login_attempts_lookup ON login_attempts(email, ip_address, created_at);
CREATE INDEX IF NOT EXISTS idx_login_attempts_created_at ON login_attempts(created_at);
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


def migrate_legacy_bookings_table(db: sqlite3.Connection) -> None:
    """Remove the old three-column UNIQUE constraint without losing booking history."""
    table_sql = db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='bookings'"
    ).fetchone()
    normalised = "".join((table_sql[0] if table_sql else "").lower().split())
    if "unique(class_id,swimmer_id,status)" not in normalised:
        return

    # SQLite cannot drop a table-level UNIQUE constraint. Rebuild the table in one
    # transaction, preserving primary keys so audit references and support records remain
    # meaningful. There are no inbound foreign keys to bookings, but foreign-key checks are
    # still run before startup continues.
    db.execute("PRAGMA foreign_keys=OFF")
    try:
        db.executescript(
            """
            BEGIN IMMEDIATE;
            DROP INDEX IF EXISTS idx_bookings_class;
            DROP INDEX IF EXISTS uniq_booking_confirmed;
            ALTER TABLE bookings RENAME TO bookings_legacy;
            CREATE TABLE bookings (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              class_id INTEGER NOT NULL REFERENCES classes(id),
              swimmer_id INTEGER NOT NULL REFERENCES swimmers(id),
              status TEXT NOT NULL CHECK (status IN ('confirmed','cancelled','completed')),
              created_at TEXT NOT NULL
            );
            INSERT INTO bookings(id,class_id,swimmer_id,status,created_at)
              SELECT id,class_id,swimmer_id,status,created_at FROM bookings_legacy;
            DROP TABLE bookings_legacy;
            CREATE INDEX idx_bookings_class ON bookings(class_id, status);
            COMMIT;
            """
        )
    except Exception:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise
    finally:
        db.execute("PRAGMA foreign_keys=ON")
    if list(db.execute("PRAGMA foreign_key_check")):
        raise RuntimeError("Booking history migration failed its foreign-key check")


def initialise_database() -> None:
    with db_session() as db:
        db.executescript(SCHEMA)
        migrate_legacy_bookings_table(db)
        # Rate-limit records carry email and IP data. Enforce the documented retention at
        # startup as well as during sign-in so a site receiving only failed traffic cannot
        # grow or retain these rows indefinitely.
        login_cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        db.execute("DELETE FROM login_attempts WHERE created_at<=?", (login_cutoff,))
        # Public lesson enquiries are kept for six months under the confirmed business
        # policy. Enrolled-family and ticket records have separate operational purposes.
        enquiry_cutoff = (datetime.now(timezone.utc) - timedelta(days=183)).isoformat()
        db.execute("DELETE FROM enquiries WHERE created_at<=?", (enquiry_cutoff,))
        # Database-level guards against double booking. Application code already checks,
        # but two requests arriving together can both pass that check before either writes.
        # Created defensively: an older database containing duplicates must not stop startup.
        for index_name, statement in (
            ("confirmed-booking", "CREATE UNIQUE INDEX IF NOT EXISTS uniq_booking_confirmed ON bookings(class_id, swimmer_id) WHERE status='confirmed'"),
            ("active-waitlist", "CREATE UNIQUE INDEX IF NOT EXISTS uniq_waitlist_waiting ON waitlist(class_id, swimmer_id) WHERE status='waiting'"),
            ("open-shift", "CREATE UNIQUE INDEX IF NOT EXISTS uniq_open_shift_per_staff ON time_entries(staff_id) WHERE clock_out IS NULL"),
        ):
            try:
                db.execute(statement)
            except sqlite3.IntegrityError as exc:
                # Production must not run without its safety/payroll uniqueness guards.
                # Development keeps starting so old preview data can be inspected and fixed.
                if settings.production:
                    raise RuntimeError(f"Resolve duplicate {index_name} records before production startup") from exc
        enquiry_columns = {row[1] for row in db.execute("PRAGMA table_info(enquiries)")}
        for column, definition in {
            "enquiry_type": "TEXT NOT NULL DEFAULT 'lesson'",
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
            "audience": "TEXT NOT NULL DEFAULT 'family'",
            "fulfilment_mode": "TEXT NOT NULL DEFAULT 'manual'",
            "printify_product_id": "TEXT",
            "supplier_reference": "TEXT",
        }.items():
            if column not in product_columns:
                db.execute(f"ALTER TABLE products ADD COLUMN {column} {definition}")
        user_columns = {row[1] for row in db.execute("PRAGMA table_info(users)")}
        for column, definition in {
            "xero_employee_id": "TEXT",
            "xero_payroll_calendar_id": "TEXT",
            "must_change_password": "INTEGER NOT NULL DEFAULT 0",
        }.items():
            if column not in user_columns:
                db.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")
        created = now_iso()
        association_credentials = (
            (
                "swim_schools_australia",
                "SWIM Schools Australia",
                "SWIM",
                "https://12524.locationlandingpages.com/australia/victoria/california-gully/hv-swim-school-bendigo/2807",
                "https://swim.org.au/swim-schools-membership/",
            ),
            (
                "austswim",
                "AUSTSWIM Swim School Network",
                "AUSTSWIM",
                "https://austswim.com.au/australian-swim-school-finder",
                "https://austswim.com.au/swim-school-network",
            ),
            (
                "autism_swim",
                "Autism Swim Approved Provider",
                "AUTISM SWIM",
                "https://autism-swim.org/providers/aquatic-centre-hidden-valley-swim-school-bendigo/",
                "https://autismswim.com.au/aquatic-certifications/",
            ),
        )
        db.executemany(
            """INSERT OR IGNORE INTO association_credentials(
                   key,display_name,short_label,directory_url,requirements_url,updated_at
               ) VALUES(?,?,?,?,?,?)""",
            [(*record, created) for record in association_credentials],
        )
        # Canonical labels and source links are application-controlled; evidence,
        # renewal dates and artwork remain deliberately untouched on every startup.
        db.executemany(
            """UPDATE association_credentials
               SET display_name=?,short_label=?,directory_url=?,requirements_url=?
               WHERE key=?""",
            [(name, label, directory, requirements, key) for key, name, label, directory, requirements in association_credentials],
        )
        base_products = [
            ("HV-SWIMWEAR", "HV Swim Team Swimwear", "Swimwear", "Logo-branded training swimwear for children and adults.", 5995, '["Kids 4-14","Adult XS-XL"]', "planned", "🩱"),
            ("HV-RASHIE", "HV Swim Kids Rashie", "Swimwear", "Chlorine-resistant long-sleeve swimming shirt for lessons and outdoor pool days.", 4495, '["Kids 2","Kids 4","Kids 6","Kids 8","Kids 10","Kids 12","Kids 14"]', "planned", "◊"),
            ("HV-SWIM-SHORTS", "HV Swim Kids Swim Shorts", "Swimwear", "Comfortable lesson-ready swim shorts with an adjustable waist and approved HV Swim branding.", 3995, '["Kids 2","Kids 4","Kids 6","Kids 8","Kids 10","Kids 12","Kids 14"]', "planned", "▱"),
            ("HV-TOWEL", "HV Swim Logo Towel", "Towels", "Soft pool towel with embroidered HV Swim branding.", 3495, '["One size"]', "planned", "▤"),
            ("HV-HOODED-TOWEL", "HV Swim Kids Hooded Towel", "Towels", "Warm hooded pool towel sized for children, with a supplier-approved HV Swim decoration.", 5495, '["Toddler","Junior"]', "planned", "▥"),
            ("HV-BOTTLE", "HV Swim Drink Bottle", "Bottles", "Named pool-deck bottle with HV Swim branding.", 1995, '["650ml"]', "planned", "🥤"),
            ("HV-INSULATED-TUMBLER", "HV Swim Insulated Coffee Cup", "Drinkware", "Premium reusable insulated cup for adults, with a proofed HV Swim decoration.", 3495, '["350ml","470ml"]', "planned", "◉"),
            ("HV-JUNIOR-WARM-CUP", "HV Swim Junior Warm-Drink Cup", "Drinkware", "Spill-resistant junior cup intended for parent-supervised warm, never hot, drinks.", 2995, '["300ml"]', "planned", "◎"),
            ("HV-GOGGLES", "HV Swim Goggles", "Equipment", "Comfortable training goggles for regular lessons.", 2495, '["Junior","Adult"]', "planned", "🥽"),
            ("HV-TRAINING-MITTS", "HV Swim Silicone Training Mitts", "Equipment", "Flexible webbed swim-training mitts for coach-directed technique activities.", 1995, '["Junior S","Junior M","Adult S","Adult M"]', "planned", "◈"),
            ("HV-BAG", "HV Swim Pool-Deck Bag", "Bags", "Ventilated swim bag for wet gear and lesson essentials.", 3995, '["One size"]', "planned", "🎒"),
            ("HV-CAP", "HV Swim Team Cap", "Caps", "Silicone swim cap with team branding.", 1495, '["Junior","Adult"]', "planned", "🧢"),
            ("HV-KIDS-SUN-HAT", "HV Swim Kids Sun Hat", "Caps", "Poolside sun hat with an approved embroidered or transfer HV Swim mark.", 2995, '["Kids S/M","Kids L/XL"]', "planned", "◌"),
            ("HV-STAFF-POLO", "HV Swim Staff Polo", "Uniforms", "Breathable navy performance polo with embroidered HV Swim identity.", 4495, '["XS","S","M","L","XL","2XL"]', "planned", "◈"),
            ("HV-STAFF-TEE", "HV Swim Staff Performance Shirt", "Uniforms", "Lightweight team shirt for teaching support, events and pool-deck setup.", 3995, '["XS","S","M","L","XL","2XL","3XL"]', "planned", "◇"),
            ("HV-STAFF-SHORTS", "HV Swim Staff Deck Shorts", "Uniforms", "Quick-dry staff shorts selected for safe, comfortable work around the pool deck.", 4495, '["XS","S","M","L","XL","2XL"]', "planned", "△"),
            ("HV-TEAM-HOODIE", "HV Swim Team Hoodie", "Uniforms", "Warm branded hoodie for staff, families and pool-deck arrivals.", 6495, '["Kids 6-14","Adult XS-2XL"]', "planned", "◇"),
            ("HV-STAFF-PUFFER-VEST", "HV Swim Staff Puffer Vest", "Uniforms", "Insulated sleeveless layer for arrivals, reception work and cool pool-deck conditions.", 8995, '["XS","S","M","L","XL","2XL"]', "planned", "◐"),
            ("HV-STAFF-PUFFER-JACKET", "HV Swim Staff Puffer Jacket", "Uniforms", "Warm staff outer layer with controlled logo placement and a supplier-approved size range.", 11995, '["XS","S","M","L","XL","2XL"]', "planned", "◑"),
            ("HV-STAFF-TRACKPANTS", "HV Swim Staff Track Pants", "Uniforms", "Comfortable staff track pants for travel, setup and cooler pool-deck shifts.", 6995, '["XS","S","M","L","XL","2XL"]', "planned", "▢"),
            ("HV-INSTRUCTOR-CAP", "HV Swim Instructor Cap", "Uniforms", "Lightweight branded cap for outdoor and seasonal pool work.", 2495, '["Adjustable"]', "planned", "◌"),
        ]
        db.executemany("INSERT OR IGNORE INTO products(sku,title,category,description,price_cents,sizes,status,emoji) VALUES(?,?,?,?,?,?,?,?)", base_products)
        production_defaults = {
            "HV-SWIMWEAR": ("family", "specialist_swim", "specialist_purchase_order", "HV Swim identity; name placement under review"),
            "HV-RASHIE": ("kids", "specialist_swim", "specialist_purchase_order", "HV Swim identity; optional swimmer name after chlorine testing"),
            "HV-SWIM-SHORTS": ("kids", "specialist_swim", "specialist_purchase_order", "HV Swim identity; no name placement until a wear test is approved"),
            "HV-TOWEL": ("family", "vistaprint_or_specialist", "supplier_comparison", "Embroidered identity; optional swimmer name"),
            "HV-HOODED-TOWEL": ("kids", "vistaprint_or_specialist", "supplier_comparison", "Embroidered or transfer identity; optional swimmer name"),
            "HV-BOTTLE": ("family", "vistaprint", "manual_bulk_order", "Named bottle after wash and rub testing"),
            "HV-INSULATED-TUMBLER": ("family", "vistaprint_or_specialist", "supplier_comparison", "Proofed HV Swim decoration; optional name after wash and heat-cycle testing"),
            "HV-JUNIOR-WARM-CUP": ("kids", "vistaprint_or_specialist", "supplier_comparison", "Optional name after lid, wash and rub testing; parent-supervised warm drinks only"),
            "HV-GOGGLES": ("family", "specialist_swim", "specialist_purchase_order", "No product personalisation planned"),
            "HV-TRAINING-MITTS": ("kids", "specialist_swim", "specialist_purchase_order", "No personalisation until material and safety review is complete"),
            "HV-BAG": ("family", "printify_or_vistaprint", "supplier_comparison", "HV Swim mark and swimmer name panel"),
            "HV-CAP": ("family", "specialist_swim", "specialist_purchase_order", "Durable HV Swim team print"),
            "HV-KIDS-SUN-HAT": ("kids", "printify_or_vistaprint", "supplier_comparison", "Embroidered or transfer HV Swim mark"),
            "HV-STAFF-POLO": ("staff", "vistaprint", "manual_bulk_order", "Embroidered identity; role or staff name optional"),
            "HV-STAFF-TEE": ("staff", "printify", "printify_shopify", "HV Swim decoration; staff name optional after a sample is approved"),
            "HV-STAFF-SHORTS": ("staff", "vistaprint_or_specialist", "supplier_comparison", "Small HV Swim mark; individual names not recommended"),
            "HV-TEAM-HOODIE": ("family", "printify", "printify_shopify", "HV Swim decoration; individual name optional"),
            "HV-STAFF-PUFFER-VEST": ("staff", "vistaprint_or_specialist", "manual_bulk_order", "Embroidered HV Swim identity; role optional"),
            "HV-STAFF-PUFFER-JACKET": ("staff", "vistaprint_or_specialist", "manual_bulk_order", "Embroidered HV Swim identity; role optional"),
            "HV-STAFF-TRACKPANTS": ("staff", "vistaprint_or_specialist", "manual_bulk_order", "Small HV Swim mark; no individual name planned"),
            "HV-INSTRUCTOR-CAP": ("staff", "printify_or_vistaprint", "supplier_comparison", "Embroidered identity and instructor label"),
        }
        fulfilment_by_route = {
            "specialist_swim": "specialist_purchase_order",
            "specialist_uniform": "manual_purchase_order",
            "vistaprint": "manual_bulk_order",
            "printify": "printify_shopify",
            "printify_or_vistaprint": "supplier_comparison",
            "vistaprint_or_specialist": "supplier_comparison",
            "manual_review": "manual_review",
        }
        for sku, (audience, supplier_route, seeded_fulfilment_mode, personalisation) in production_defaults.items():
            db.execute(
                """UPDATE products
                   SET audience=?,supplier_route=COALESCE(NULLIF(supplier_route,''),?),
                       personalisation=COALESCE(NULLIF(personalisation,''),?)
                   WHERE sku=?""",
                (audience, supplier_route, personalisation, sku),
            )
            selected_route = db.execute("SELECT supplier_route FROM products WHERE sku=?", (sku,)).fetchone()[0]
            db.execute(
                "UPDATE products SET fulfilment_mode=? WHERE sku=?",
                (fulfilment_by_route.get(selected_route, seeded_fulfilment_mode), sku),
            )
        # Earlier preview databases used the ambiguous specialist_uniform route for
        # aquatic products. Keep specialist_uniform valid for apparel while making the
        # seeded swim products explicit and safe for supplier routing.
        aquatic_skus = ("HV-SWIMWEAR", "HV-RASHIE", "HV-SWIM-SHORTS", "HV-GOGGLES", "HV-TRAINING-MITTS", "HV-CAP")
        db.execute(
            f"""UPDATE products
                SET supplier_route='specialist_swim',fulfilment_mode='specialist_purchase_order'
                WHERE sku IN ({','.join('?' for _ in aquatic_skus)}) AND supplier_route='specialist_uniform'""",
            aquatic_skus,
        )
        for provider in ("xero", "shopify", "printify", "vistaprint", "weather", "email", "sms", "web_push", "pool_sensor"):
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
            "feature_merch_home": "0",
            "feature_association_badges": "0",
        }
        db.executemany("INSERT OR IGNORE INTO site_settings(key,value,updated_at) VALUES(?,?,?)", [(key, value, created) for key, value in site_defaults.items()])
        achievement_templates = [
            ("first-splash", "First Splash", "Celebrating a brave, positive start and a swimmer's first confident steps with HV Swim.", "sunrise-ripple", "wave", 10, created),
            ("water-confidence", "Water Confidence", "Recognising calm, growing confidence and a positive connection with the water.", "calm-current", "spark", 20, created),
            ("bubble-breathing", "Bubble Breathing", "Awarded for controlled breathing, steady bubbles and relaxed face-in-the-water practice.", "bubble-trail", "bubbles", 30, created),
            ("floating-star", "Floating Star", "Celebrating a balanced, relaxed float with safe body position and growing independence.", "star-float", "star", 40, created),
            ("kicking-champion", "Kicking Champion", "Recognising strong, consistent kicking and determined lesson effort.", "golden-kick", "bolt", 50, created),
            ("stroke-builder", "Stroke Builder", "Awarded for bringing body position, breathing and technique together into a stronger stroke.", "lane-progress", "lanes", 60, created),
            ("water-safety-hero", "Water Safety Hero", "Recognising thoughtful water-safety choices, listening and safe pool behaviour.", "safety-shield", "shield", 70, created),
            ("personal-best", "Personal Best", "Celebrating individual progress, persistence and a result the swimmer can be proud of.", "personal-best", "ribbon", 80, created),
        ]
        db.executemany(
            """INSERT OR IGNORE INTO achievement_templates
               (code,title,description,certificate_style,badge_symbol,sort_order,created_at)
               VALUES(?,?,?,?,?,?,?)""",
            achievement_templates,
        )
        # Verified business venues are operational configuration, not demo people/data.
        # Seed them idempotently before any early return so a fresh production account can
        # immediately use pool, roster and class workflows.
        locations = [
            ("wood-street", "Wood Street Indoor Pool", "76 Wood Street, California Gully VIC 3556", -36.7339, 144.2595, "Private indoor heated pool", "On-site and nearby street parking", "Wheelchair access and public toilets listed; individual pool-entry needs should be confirmed", "Lessons running", 0),
            ("bendigo-east", "Bendigo East Swimming Pool", "31 Lansell Street, East Bendigo VIC 3550", -36.7507, 144.3018, "Heated seasonal community facility", "Off-street parking", "Contact venue before booking to confirm pool-entry assistance", "Closed for winter", 0),
        ]
        db.executemany(
            """INSERT OR IGNORE INTO locations(slug,name,address,latitude,longitude,venue_type,parking,accessibility,public_status,sensor_enabled)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            locations,
        )
        # Keep the bundled demo account aligned with the current business team.
        db.execute("UPDATE users SET first_name='Laura',last_name='' WHERE email='admin@hvswim.demo'")
        # The confirmed business fee is $22.50 for every lesson. Keep existing preview
        # databases aligned before the early return as well as seeding new databases.
        db.execute("UPDATE classes SET price_cents=2250")
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            return
        if settings.production:
            if not settings.bootstrap_admin_email or len(settings.bootstrap_admin_password) < 12:
                raise RuntimeError(
                    "An empty production database needs HV_BOOTSTRAP_ADMIN_EMAIL and a unique "
                    "HV_BOOTSTRAP_ADMIN_PASSWORD of at least 12 characters for its first start"
                )
            first_name, _, last_name = settings.bootstrap_admin_name.partition(" ")
            db.execute(
                "INSERT INTO users(email,password_hash,role,first_name,last_name,created_at) VALUES(?,?,?,?,?,?)",
                (
                    settings.bootstrap_admin_email,
                    password_hash(settings.bootstrap_admin_password),
                    "admin",
                    first_name or "HV",
                    last_name or "Swim Admin",
                    created,
                ),
            )
            audit(db, None, "bootstrap_admin", "user", db.execute("SELECT last_insert_rowid()").fetchone()[0])
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
            ("INF-A-MON", "Infant Aquatics", "Infant Aquatics", location_ids["wood-street"], user_ids["staff@hvswim.demo"], 0, "09:00", 30, 5, 2250),
            ("LTS1-TUE", "Learn to Swim 1", "Beginner", location_ids["wood-street"], user_ids["casey@hvswim.demo"], 1, "15:45", 30, 5, 2250),
            ("LTS3-THU", "Learn to Swim 3", "Learn to Swim 3", location_ids["wood-street"], user_ids["staff@hvswim.demo"], 3, "16:15", 45, 5, 2250),
            ("PRIV-FRI", "Private Lesson", "All levels", location_ids["wood-street"], user_ids["staff@hvswim.demo"], 4, "17:10", 30, 1, 2250),
            ("STROKE-SAT", "Stroke Development", "Stroke Development", location_ids["wood-street"], user_ids["casey@hvswim.demo"], 5, "10:30", 45, 6, 2250),
        ]
        db.executemany("INSERT INTO classes(code,title,level,location_id,instructor_id,weekday,start_time,duration_minutes,capacity,price_cents) VALUES(?,?,?,?,?,?,?,?,?,?)", classes)
        swimmer_ids = {row["first_name"]: row["id"] for row in db.execute("SELECT id,first_name FROM swimmers")}
        class_ids = {row["code"]: row["id"] for row in db.execute("SELECT id,code FROM classes")}
        db.execute("INSERT INTO bookings(class_id,swimmer_id,status,created_at) VALUES(?,?,?,?)", (class_ids["LTS3-THU"], swimmer_ids["Mia"], "confirmed", created))
        db.execute("INSERT INTO bookings(class_id,swimmer_id,status,created_at) VALUES(?,?,?,?)", (class_ids["INF-A-MON"], swimmer_ids["Noah"], "confirmed", created))
        db.execute("INSERT INTO waitlist(class_id,swimmer_id,position,status,created_at) VALUES(?,?,?,?,?)", (class_ids["LTS1-TUE"], swimmer_ids["Mia"], 1, "waiting", created))
        today = business_today()
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
