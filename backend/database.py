from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Generator, Iterable

from .config import DB_PATH, settings
from .filesystem import ensure_private_directory, harden_database_files
from .security import SENSITIVE_VALUE_PREFIX, business_today, encrypt_sensitive, now_iso, password_hash


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
  customer_number TEXT,
  staff_number TEXT,
  xero_contact_id TEXT,
  shopify_customer_gid TEXT,
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
CREATE TABLE IF NOT EXISTS oauth_login_attempts (
  state_hash TEXT PRIMARY KEY,
  provider TEXT NOT NULL CHECK (provider IN ('google','apple')),
  ip_address TEXT NOT NULL,
  code_verifier TEXT NOT NULL,
  nonce TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS oauth_identities (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  provider TEXT NOT NULL CHECK (provider IN ('google','apple')),
  subject TEXT NOT NULL,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  created_at TEXT NOT NULL,
  last_login_at TEXT NOT NULL,
  UNIQUE(provider, subject),
  UNIQUE(provider, user_id)
);
CREATE TABLE IF NOT EXISTS swimmers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  customer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  swimmer_number TEXT,
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  date_of_birth TEXT,
  level TEXT NOT NULL,
  emergency_contact TEXT,
  medical_notes TEXT,
  allergies TEXT,
  medications TEXT,
  support_notes TEXT,
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
CREATE TABLE IF NOT EXISTS school_terms (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  absence_credit_limit INTEGER NOT NULL DEFAULT 2 CHECK (absence_credit_limit BETWEEN 0 AND 10),
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','closed')),
  source TEXT NOT NULL DEFAULT 'management' CHECK (source IN ('management','preview')),
  created_by INTEGER REFERENCES users(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK (end_date >= start_date)
);
CREATE TABLE IF NOT EXISTS absence_reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  booking_id INTEGER NOT NULL REFERENCES bookings(id),
  term_id INTEGER NOT NULL REFERENCES school_terms(id),
  occurrence_date TEXT NOT NULL,
  reason_category TEXT NOT NULL CHECK (reason_category IN ('illness','family','school','other')),
  credit_status TEXT NOT NULL CHECK (credit_status IN ('credited','recorded_no_credit','withdrawn')),
  reported_by INTEGER NOT NULL REFERENCES users(id),
  reported_at TEXT NOT NULL,
  UNIQUE (booking_id, occurrence_date)
);
CREATE TABLE IF NOT EXISTS lesson_attendance (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  booking_id INTEGER NOT NULL REFERENCES bookings(id),
  term_id INTEGER NOT NULL REFERENCES school_terms(id),
  occurrence_date TEXT NOT NULL,
  attendance_status TEXT NOT NULL CHECK (attendance_status IN ('present','absent','late','excused')),
  parent_onsite_confirmed INTEGER,
  photo_clearance_snapshot INTEGER NOT NULL DEFAULT 0,
  private_note TEXT,
  recorded_by INTEGER NOT NULL REFERENCES users(id),
  recorded_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (booking_id, occurrence_date)
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
  xero_timesheet_id TEXT,
  work_date TEXT,
  week_start TEXT,
  entry_scope TEXT NOT NULL DEFAULT 'daily' CHECK (entry_scope IN ('daily','weekly')),
  notes TEXT,
  break_started_at TEXT,
  break_minutes INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS qualifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  staff_id INTEGER NOT NULL REFERENCES users(id),
  qualification_type TEXT NOT NULL,
  reference_number TEXT,
  expiry_date TEXT,
  status TEXT NOT NULL DEFAULT 'current',
  verified_at TEXT,
  document_filename TEXT,
  original_filename TEXT,
  document_media_type TEXT,
  document_sha256 TEXT,
  uploaded_at TEXT,
  reminder_days INTEGER NOT NULL DEFAULT 60
);
CREATE TABLE IF NOT EXISTS qualification_reminder_dispatches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  qualification_id INTEGER NOT NULL REFERENCES qualifications(id) ON DELETE CASCADE,
  expiry_date TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(qualification_id, expiry_date)
);
CREATE TABLE IF NOT EXISTS incident_reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  reference TEXT UNIQUE NOT NULL,
  swimmer_id INTEGER NOT NULL REFERENCES swimmers(id),
  family_user_id INTEGER NOT NULL REFERENCES users(id),
  reported_by INTEGER NOT NULL REFERENCES users(id),
  location_id INTEGER NOT NULL REFERENCES locations(id),
  incident_at TEXT NOT NULL,
  incident_type TEXT NOT NULL,
  what_happened TEXT NOT NULL,
  injury_observed TEXT,
  first_aid_applied TEXT,
  further_action TEXT,
  witnesses TEXT,
  parent_notified INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','follow_up','closed')),
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_incidents_family ON incident_reports(family_user_id,incident_at);
CREATE INDEX IF NOT EXISTS idx_incidents_reporter ON incident_reports(reported_by,incident_at);
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
CREATE TABLE IF NOT EXISTS reminder_preferences (
  user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  enabled INTEGER NOT NULL DEFAULT 1,
  hours_before INTEGER NOT NULL DEFAULT 24 CHECK (hours_before BETWEEN 2 AND 72),
  channels TEXT NOT NULL DEFAULT '["in_app"]',
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lesson_reminder_dispatches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  booking_id INTEGER NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  occurrence_date TEXT NOT NULL,
  notification_id INTEGER REFERENCES notifications(id) ON DELETE SET NULL,
  status TEXT NOT NULL DEFAULT 'delivered_in_app' CHECK (status IN ('delivered_in_app','external_pending','cancelled')),
  created_at TEXT NOT NULL,
  UNIQUE(booking_id, occurrence_date, user_id)
);
CREATE TABLE IF NOT EXISTS lesson_charges (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  reference TEXT UNIQUE NOT NULL,
  booking_id INTEGER UNIQUE NOT NULL REFERENCES bookings(id),
  customer_id INTEGER NOT NULL REFERENCES users(id),
  term_id INTEGER NOT NULL REFERENCES school_terms(id),
  provider TEXT NOT NULL DEFAULT 'xero' CHECK (provider='xero'),
  per_lesson_cents INTEGER NOT NULL CHECK (per_lesson_cents>=0),
  lesson_count INTEGER NOT NULL CHECK (lesson_count>=1),
  amount_cents INTEGER NOT NULL CHECK (amount_cents>=0),
  family_customer_number TEXT,
  swimmer_number TEXT,
  xero_contact_id TEXT,
  invoice_description TEXT,
  status TEXT NOT NULL DEFAULT 'pending_xero_invoice' CHECK (status IN ('pending_xero_invoice','invoiced','paid','cancelled_no_refund')),
  xero_invoice_id TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS billing_invoices (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  invoice_number TEXT UNIQUE NOT NULL,
  customer_id INTEGER NOT NULL REFERENCES users(id),
  term_id INTEGER REFERENCES school_terms(id),
  provider TEXT NOT NULL DEFAULT 'xero' CHECK (provider='xero'),
  currency TEXT NOT NULL DEFAULT 'AUD' CHECK (currency='AUD'),
  customer_number TEXT NOT NULL,
  xero_contact_id TEXT,
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','approved','sync_review','synced','sent','paid','voided')),
  issue_date TEXT NOT NULL,
  due_date TEXT NOT NULL,
  subtotal_cents INTEGER NOT NULL CHECK (subtotal_cents>=0),
  total_cents INTEGER NOT NULL CHECK (total_cents>=0),
  amount_paid_cents INTEGER NOT NULL DEFAULT 0 CHECK (amount_paid_cents>=0),
  amount_due_cents INTEGER NOT NULL CHECK (amount_due_cents>=0),
  management_note TEXT NOT NULL DEFAULT '',
  idempotency_key TEXT UNIQUE NOT NULL,
  xero_invoice_id TEXT UNIQUE,
  xero_invoice_number TEXT,
  xero_status TEXT,
  online_invoice_url TEXT,
  last_sync_error TEXT,
  approved_by INTEGER REFERENCES users(id),
  approved_at TEXT,
  synced_at TEXT,
  created_by INTEGER NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK (due_date>=issue_date),
  CHECK (amount_paid_cents<=total_cents),
  CHECK (amount_due_cents<=total_cents)
);
CREATE TABLE IF NOT EXISTS billing_invoice_lines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  invoice_id INTEGER NOT NULL REFERENCES billing_invoices(id) ON DELETE CASCADE,
  lesson_charge_id INTEGER UNIQUE NOT NULL REFERENCES lesson_charges(id),
  description TEXT NOT NULL,
  quantity INTEGER NOT NULL CHECK (quantity>=1),
  unit_amount_cents INTEGER NOT NULL CHECK (unit_amount_cents>=0),
  line_amount_cents INTEGER NOT NULL CHECK (line_amount_cents>=0),
  student_number TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS billing_invoice_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  invoice_id INTEGER NOT NULL REFERENCES billing_invoices(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,
  from_status TEXT,
  to_status TEXT,
  detail TEXT NOT NULL DEFAULT '{}',
  created_by INTEGER REFERENCES users(id),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notification_receipts (
  notification_id INTEGER NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  read_at TEXT NOT NULL,
  PRIMARY KEY (notification_id, user_id)
);
CREATE TABLE IF NOT EXISTS swimmer_skill_updates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  swimmer_id INTEGER NOT NULL REFERENCES swimmers(id),
  skill_name TEXT NOT NULL,
  skill_status TEXT NOT NULL CHECK (skill_status IN ('practising','developing','achieved')),
  feedback TEXT NOT NULL,
  next_step TEXT NOT NULL,
  recorded_by INTEGER NOT NULL REFERENCES users(id),
  recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_skill_progress ON swimmer_skill_updates(swimmer_id,skill_name,id);
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
CREATE INDEX IF NOT EXISTS idx_oauth_attempts_expiry ON oauth_login_attempts(expires_at);
CREATE INDEX IF NOT EXISTS idx_oauth_identity_user ON oauth_identities(user_id);
CREATE INDEX IF NOT EXISTS idx_bookings_class ON bookings(class_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS uniq_active_school_term ON school_terms(status) WHERE status='active';
CREATE INDEX IF NOT EXISTS idx_school_terms_dates ON school_terms(start_date,end_date,status);
CREATE INDEX IF NOT EXISTS idx_absence_reports_term ON absence_reports(term_id,credit_status,occurrence_date);
CREATE INDEX IF NOT EXISTS idx_lesson_attendance_date ON lesson_attendance(occurrence_date,booking_id);
CREATE INDEX IF NOT EXISTS idx_pool_readings_location ON pool_readings(location_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_lesson_reminders_user ON lesson_reminder_dispatches(user_id, occurrence_date DESC);
CREATE INDEX IF NOT EXISTS idx_lesson_charges_status ON lesson_charges(status, created_at);
CREATE INDEX IF NOT EXISTS idx_billing_invoices_customer ON billing_invoices(customer_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_billing_invoices_status ON billing_invoices(status, due_date, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_billing_invoice_lines_invoice ON billing_invoice_lines(invoice_id, id);
CREATE INDEX IF NOT EXISTS idx_billing_invoice_events_invoice ON billing_invoice_events(invoice_id, created_at, id);
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
CREATE INDEX IF NOT EXISTS idx_qualifications_expiry ON qualifications(expiry_date, staff_id);
-- Both rate limits below scan on every sign-in and every public enquiry, and both tables
-- grow with traffic, so they need covering indexes.
CREATE INDEX IF NOT EXISTS idx_audit_action_ip ON audit_log(action, ip_address, created_at);
CREATE INDEX IF NOT EXISTS idx_login_attempts_lookup ON login_attempts(email, ip_address, created_at);
CREATE INDEX IF NOT EXISTS idx_login_attempts_ip ON login_attempts(ip_address, created_at);
CREATE INDEX IF NOT EXISTS idx_login_attempts_created_at ON login_attempts(created_at);
"""


def connect() -> sqlite3.Connection:
    ensure_private_directory(DB_PATH.parent)
    connection = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
    harden_database_files(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=15000")
    connection.execute("PRAGMA synchronous=NORMAL")
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


def purge_expired_enquiries(db: sqlite3.Connection) -> int:
    """Delete public enquiries past the six-month retention window. Returns rows removed."""
    from .security import ENQUIRY_RETENTION_DAYS

    cutoff = (datetime.now(timezone.utc) - timedelta(days=ENQUIRY_RETENTION_DAYS)).isoformat()
    cursor = db.execute("DELETE FROM enquiries WHERE created_at<=?", (cutoff,))
    return cursor.rowcount


def initialise_database() -> None:
    ensure_private_directory(DB_PATH.parent)
    with db_session() as db:
        # WAL allows readers to continue while a short management write is committed.
        # The explicit busy timeout above turns brief write contention into a bounded wait
        # instead of an immediate operational error.
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript(SCHEMA)
        migrate_legacy_bookings_table(db)
        # Rate-limit records carry email and IP data. Enforce the documented retention at
        # startup as well as during sign-in so a site receiving only failed traffic cannot
        # grow or retain these rows indefinitely.
        login_cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        db.execute("DELETE FROM login_attempts WHERE created_at<=?", (login_cutoff,))
        purge_expired_enquiries(db)
        session_columns = {row[1] for row in db.execute("PRAGMA table_info(sessions)")}
        if "last_seen_at" not in session_columns:
            db.execute("ALTER TABLE sessions ADD COLUMN last_seen_at TEXT")
            db.execute("UPDATE sessions SET last_seen_at=created_at WHERE last_seen_at IS NULL")
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
            "assigned_to": "INTEGER REFERENCES users(id)",
            "next_action": "TEXT NOT NULL DEFAULT 'review'",
            "follow_up_on": "TEXT",
            "revision": "INTEGER NOT NULL DEFAULT 0",

        }.items():
            if column not in enquiry_columns:
                db.execute(f"ALTER TABLE enquiries ADD COLUMN {column} {definition}")
        incident_columns = {row[1] for row in db.execute("PRAGMA table_info(incident_reports)")}
        for column, definition in {
            "severity": "TEXT NOT NULL DEFAULT 'unassessed'",
            "first_aider": "TEXT",
            "emergency_services": "INTEGER NOT NULL DEFAULT 0",
            "supporting_notes": "TEXT",
            "manager_review": "TEXT",
            "reviewed_by": "INTEGER REFERENCES users(id)",
            "reviewed_at": "TEXT",
        }.items():
            if column not in incident_columns:
                db.execute(f"ALTER TABLE incident_reports ADD COLUMN {column} {definition}")
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
            # Product photography. Left empty until a real render or photograph exists —
            # the shop falls back to its monogram tile, which is honest, where a path
            # pointing at a missing file would show every product as a broken image.
            "image": "TEXT",
            "image_alt": "TEXT",
        }.items():
            if column not in product_columns:
                db.execute(f"ALTER TABLE products ADD COLUMN {column} {definition}")
        user_columns = {row[1] for row in db.execute("PRAGMA table_info(users)")}
        for column, definition in {
            "customer_number": "TEXT",
            "staff_number": "TEXT",
            "xero_contact_id": "TEXT",
            "shopify_customer_gid": "TEXT",
            "xero_employee_id": "TEXT",
            "xero_payroll_calendar_id": "TEXT",
            "must_change_password": "INTEGER NOT NULL DEFAULT 0",
        }.items():
            if column not in user_columns:
                db.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS uniq_customer_number ON users(customer_number) WHERE customer_number IS NOT NULL")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS uniq_staff_number ON users(staff_number) WHERE staff_number IS NOT NULL")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS uniq_xero_contact_id ON users(xero_contact_id) WHERE xero_contact_id IS NOT NULL")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS uniq_shopify_customer_gid ON users(shopify_customer_gid) WHERE shopify_customer_gid IS NOT NULL")
        db.execute(
            """UPDATE users SET customer_number=printf('HVS-%06d',id)
               WHERE role='customer' AND (customer_number IS NULL OR customer_number='')"""
        )
        db.execute(
            """UPDATE users SET staff_number=printf('HVS-W-%06d',id)
               WHERE role IN ('staff','admin') AND (staff_number IS NULL OR staff_number='')"""
        )
        time_entry_columns = {row[1] for row in db.execute("PRAGMA table_info(time_entries)")}
        for column, definition in {
            "work_date": "TEXT",
            "week_start": "TEXT",
            "entry_scope": "TEXT NOT NULL DEFAULT 'daily'",
            "notes": "TEXT",
            "break_started_at": "TEXT",
            "break_minutes": "INTEGER NOT NULL DEFAULT 0",
        }.items():
            if column not in time_entry_columns:
                db.execute(f"ALTER TABLE time_entries ADD COLUMN {column} {definition}")
        db.execute(
            """UPDATE time_entries
               SET work_date=COALESCE(work_date,substr(clock_in,1,10)),
                   week_start=COALESCE(week_start,date(substr(clock_in,1,10),printf('-%d days',(CAST(strftime('%w',substr(clock_in,1,10)) AS INTEGER)+6)%7))),
                   entry_scope=COALESCE(NULLIF(entry_scope,''),'daily')"""
        )
        db.execute("CREATE INDEX IF NOT EXISTS idx_time_entries_week ON time_entries(staff_id,week_start,status)")
        qualification_columns = {row[1] for row in db.execute("PRAGMA table_info(qualifications)")}
        for column, definition in {
            "document_filename": "TEXT",
            "original_filename": "TEXT",
            "document_media_type": "TEXT",
            "document_sha256": "TEXT",
            "uploaded_at": "TEXT",
            "reminder_days": "INTEGER NOT NULL DEFAULT 60",
        }.items():
            if column not in qualification_columns:
                db.execute(f"ALTER TABLE qualifications ADD COLUMN {column} {definition}")
        lesson_charge_columns = {row[1] for row in db.execute("PRAGMA table_info(lesson_charges)")}
        for column, definition in {
            "family_customer_number": "TEXT",
            "swimmer_number": "TEXT",
            "xero_contact_id": "TEXT",
            "invoice_description": "TEXT",
        }.items():
            if column not in lesson_charge_columns:
                db.execute(f"ALTER TABLE lesson_charges ADD COLUMN {column} {definition}")
        oauth_attempt_columns = {row[1] for row in db.execute("PRAGMA table_info(oauth_login_attempts)")}
        if "ip_address" not in oauth_attempt_columns:
            db.execute("ALTER TABLE oauth_login_attempts ADD COLUMN ip_address TEXT NOT NULL DEFAULT 'legacy'")
        db.execute("CREATE INDEX IF NOT EXISTS idx_oauth_attempts_ip ON oauth_login_attempts(ip_address, created_at)")
        swimmer_columns = {row[1] for row in db.execute("PRAGMA table_info(swimmers)")}
        for column, definition in {
            "swimmer_number": "TEXT",
            "allergies": "TEXT",
            "medications": "TEXT",
            "support_notes": "TEXT",
        }.items():
            if column not in swimmer_columns:
                db.execute(f"ALTER TABLE swimmers ADD COLUMN {column} {definition}")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS uniq_swimmer_number ON swimmers(swimmer_number) WHERE swimmer_number IS NOT NULL")
        db.execute(
            """UPDATE swimmers SET swimmer_number=printf('HVS-S-%06d',id)
               WHERE swimmer_number IS NULL OR swimmer_number=''"""
        )
        # Safety-critical child details are authenticated-encrypted at field level. Older
        # preview databases migrate in place; the prefix makes the migration idempotent.
        sensitive_fields = ("emergency_contact", "medical_notes", "allergies", "medications", "support_notes")
        for swimmer in db.execute(
            "SELECT id,emergency_contact,medical_notes,allergies,medications,support_notes FROM swimmers"
        ).fetchall():
            values = [swimmer[field] for field in sensitive_fields]
            if any(value and not value.startswith(SENSITIVE_VALUE_PREFIX) for value in values):
                db.execute(
                    """UPDATE swimmers SET emergency_contact=?,medical_notes=?,allergies=?,medications=?,support_notes=?
                       WHERE id=?""",
                    (*(encrypt_sensitive(value) for value in values), swimmer["id"]),
                )
        attendance_columns = {row[1] for row in db.execute("PRAGMA table_info(lesson_attendance)")}
        if "term_id" not in attendance_columns:
            # V5.7 preview databases created during development may have register rows
            # without this historical link. New writes always supply it; a production
            # migration can reconcile any pre-release rows before enforcing NOT NULL.
            db.execute("ALTER TABLE lesson_attendance ADD COLUMN term_id INTEGER REFERENCES school_terms(id)")
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
            ("HV-TOWEL", "HV Swim Premium Embroidered Towel", "Towels", "Plush pool towel with a stitched HV Swim crest and an optional embroidered swimmer name.", 3995, '["Pool 75 × 150cm","Bath sheet 90 × 170cm"]', "planned", "▤"),
            ("HV-HOODED-TOWEL", "HV Swim Embroidered Hooded Towel Poncho", "Towels", "Warm pull-on hooded towel for quick poolside changes, finished with a supplier-approved embroidered HV Swim crest.", 5995, '["Toddler 2-4","Junior 5-8","Youth 9-12"]', "planned", "▥"),
            ("HV-MINI-HOODED-TOWEL", "HV Swim Mini Hooded Towel", "Towels", "Soft wrap-style hooded towel for little swimmers, with comfortable embroidery backing and optional first-name stitching.", 4995, '["Little swimmer 1-3","Little swimmer 3-5"]', "planned", "▥"),
            ("HV-BOTTLE", "HV Swim Named Insulated Bottle", "Bottles", "Premium pool-deck bottle with a leak-resistant lid, HV Swim branding and an optional swimmer name.", 2995, '["500ml junior","750ml family"]', "planned", "🥤"),
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
            ("HV-FAMILY-TEE", "HV Swim Family Club Tee", "Lifestyle", "Soft premium club tee for families, events and lesson-day arrivals, prepared for approved Printify-to-Shopify fulfilment.", 3495, '["Kids 6-14","Adult XS-3XL"]', "planned", "◇"),
            ("HV-FAMILY-CREW", "HV Swim Family Club Crew", "Lifestyle", "Premium embroidered-look crew layer for cool Bendigo mornings, families and team events.", 6495, '["Kids 8-14","Adult XS-3XL"]', "planned", "◇"),
        ]
        db.executemany("INSERT OR IGNORE INTO products(sku,title,category,description,price_cents,sizes,status,emoji) VALUES(?,?,?,?,?,?,?,?)", base_products)
        # Untouched preview records receive the clearer premium copy and options. Once
        # management has sampled, mapped or otherwise progressed a product, their exact
        # commercial record is preserved on later starts.
        canonical_product_copy = {
            row[0]: row[1:7]
            for row in base_products
        }
        db.executemany(
            """UPDATE products
               SET title=?,category=?,description=?,price_cents=?,sizes=?,status=?
               WHERE sku=? AND status='planned' AND sample_status='not_ordered'
                 AND supplier_reference IS NULL AND shopify_gid IS NULL""",
            [(*values, sku) for sku, values in canonical_product_copy.items()],
        )
        production_defaults = {
            "HV-SWIMWEAR": ("family", "specialist_swim", "specialist_purchase_order", "HV Swim identity; name placement under review"),
            "HV-RASHIE": ("kids", "specialist_swim", "specialist_purchase_order", "HV Swim identity; optional swimmer name after chlorine testing"),
            "HV-SWIM-SHORTS": ("kids", "specialist_swim", "specialist_purchase_order", "HV Swim identity; no name placement until a wear test is approved"),
            "HV-TOWEL": ("family", "vistaprint_or_specialist", "supplier_comparison", "Embroidered identity; optional swimmer name"),
            "HV-HOODED-TOWEL": ("kids", "vistaprint_or_specialist", "supplier_comparison", "Embroidered or transfer identity; optional swimmer name"),
            "HV-MINI-HOODED-TOWEL": ("kids", "vistaprint_or_specialist", "supplier_comparison", "Comfort-backed embroidery; optional first-name stitching"),
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
            "HV-TEAM-HOODIE": ("staff", "printify", "printify_shopify", "HV Swim decoration; staff name optional after sample approval"),
            "HV-STAFF-PUFFER-VEST": ("staff", "vistaprint_or_specialist", "manual_bulk_order", "Embroidered HV Swim identity; role optional"),
            "HV-STAFF-PUFFER-JACKET": ("staff", "vistaprint_or_specialist", "manual_bulk_order", "Embroidered HV Swim identity; role optional"),
            "HV-STAFF-TRACKPANTS": ("staff", "vistaprint_or_specialist", "manual_bulk_order", "Small HV Swim mark; no individual name planned"),
            "HV-INSTRUCTOR-CAP": ("staff", "printify_or_vistaprint", "supplier_comparison", "Embroidered identity and instructor label"),
            "HV-FAMILY-TEE": ("family", "printify", "printify_shopify", "HV Swim front mark; optional family surname only after sample approval"),
            "HV-FAMILY-CREW": ("family", "printify", "printify_shopify", "Premium HV Swim chest decoration; no individual name by default"),
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
            "announcement_text": "Lesson enquiries are open — ask about the best class for your swimmer.",
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
        db.execute(
            """UPDATE site_settings SET value=?,updated_at=?
               WHERE key='announcement_text' AND value='Enrolments are open — ask about the best lesson for your swimmer.'""",
            (site_defaults["announcement_text"], created),
        )
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
        # Development needs enough calendar data to exercise absence and lesson-register
        # workflows, but invented term dates must never appear as production truth. The
        # preview term is deliberately labelled and is only created outside production.
        if not settings.production and not db.execute("SELECT 1 FROM school_terms LIMIT 1").fetchone():
            today = business_today()
            db.execute(
                """INSERT INTO school_terms(
                       name,start_date,end_date,absence_credit_limit,status,source,created_at,updated_at
                   ) VALUES(?,?,?,?,?,?,?,?)""",
                (
                    "Preview operating term",
                    (today - timedelta(days=7)).isoformat(),
                    (today + timedelta(days=84)).isoformat(),
                    2,
                    "active",
                    "preview",
                    created,
                    created,
                ),
            )
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            return
        if settings.production:
            if not settings.bootstrap_admin_email or len(settings.bootstrap_admin_password) < 12:
                raise RuntimeError(
                    "An empty production database needs HV_BOOTSTRAP_ADMIN_EMAIL and a unique "
                    "HV_BOOTSTRAP_ADMIN_PASSWORD of at least 12 characters for its first start"
                )
            first_name, _, last_name = settings.bootstrap_admin_name.partition(" ")
            bootstrap_id = db.execute(
                "INSERT INTO users(email,password_hash,role,first_name,last_name,created_at) VALUES(?,?,?,?,?,?)",
                (
                    settings.bootstrap_admin_email,
                    password_hash(settings.bootstrap_admin_password),
                    "admin",
                    first_name or "HV",
                    last_name or "Swim Admin",
                    created,
                ),
            ).lastrowid
            db.execute("UPDATE users SET staff_number=printf('HVS-W-%06d',id) WHERE id=?", (bootstrap_id,))
            audit(db, None, "bootstrap_admin", "user", bootstrap_id)
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
        db.execute(
            """UPDATE users SET customer_number=printf('HVS-%06d',id)
               WHERE role='customer' AND (customer_number IS NULL OR customer_number='')"""
        )
        db.execute(
            """UPDATE users SET staff_number=printf('HVS-W-%06d',id)
               WHERE role IN ('staff','admin') AND (staff_number IS NULL OR staff_number='')"""
        )
        user_ids = {row["email"]: row["id"] for row in db.execute("SELECT id,email FROM users")}
        location_ids = {row["slug"]: row["id"] for row in db.execute("SELECT id,slug FROM locations")}
        db.execute(
            "INSERT INTO swimmers(customer_id,first_name,last_name,date_of_birth,level,emergency_contact,medical_notes,allergies,medications,support_notes,photo_consent,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (user_ids["parent@hvswim.demo"], "Mia", "Smith", "2018-05-14", "Learn to Swim 3", encrypt_sensitive("Jordan Smith · 0413 000 101"), encrypt_sensitive("No medical conditions recorded in this demo profile"), encrypt_sensitive("No known allergies"), encrypt_sensitive("No medications recorded"), encrypt_sensitive("Responds well to calm, step-by-step instructions"), 1, created),
        )
        db.execute(
            """UPDATE swimmers SET swimmer_number=printf('HVS-S-%06d',id)
               WHERE swimmer_number IS NULL OR swimmer_number=''"""
        )
        db.execute(
            "INSERT INTO swimmers(customer_id,first_name,last_name,date_of_birth,level,emergency_contact,medical_notes,allergies,medications,support_notes,photo_consent,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (user_ids["parent@hvswim.demo"], "Noah", "Smith", "2024-01-22", "Infant Aquatics", encrypt_sensitive("Jordan Smith · 0413 000 101"), encrypt_sensitive("No medical conditions recorded in this demo profile"), encrypt_sensitive("No known allergies"), encrypt_sensitive("No medications recorded"), encrypt_sensitive("Parent participates in every infant lesson"), 0, created),
        )
        db.execute(
            """UPDATE swimmers SET swimmer_number=printf('HVS-S-%06d',id)
               WHERE swimmer_number IS NULL OR swimmer_number=''"""
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
