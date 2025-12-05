import os
import threading
import time
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError, DBAPIError
import models  # <-- Load all SQLAlchemy models

# =====================================
# Load DATABASE_URL (with fallback)
# =====================================
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL or "://" not in DATABASE_URL:
    print("⚠️ DATABASE_URL missing — using SQLite fallback")
    DATABASE_URL = "sqlite:///smarttest.db"

# Fix heroku-style URLs
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)


# -------------------------------------
# Global DB readiness flag
# -------------------------------------
DB_READY = False
DB_IS_SQLITE = DATABASE_URL.startswith("sqlite")


# =====================================
# Render-safe connect args (FAIL-FAST)
# =====================================
def make_connect_args(url):
    if url.startswith("sqlite"):
        return {"check_same_thread": False}

    # For production Postgres we use a short per-connection timeout so
    # calls fail fast and UI stays responsive while warm-up runs in background
    return {
        "sslmode": "require",
        "connect_timeout": 5,   # <- FAIL FAST per-connection
        "keepalives": 1,
        "keepalives_idle": 20,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    }


# =====================================
# Create engine (LAZY)
# =====================================
def create_safe_engine(url):
    connect_args = make_connect_args(url)

    engine = create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=True,
        pool_recycle=180,
        pool_size=5,
        max_overflow=10,
        pool_timeout=5,    # <- fail faster when pool exhausted
        echo=False,
    )

    print("✅ Engine created (lazy mode, fail-fast connections)")
    return engine


engine = create_safe_engine(DATABASE_URL)


# =====================================
# Background warm-up (non-blocking)
# =====================================
def warm_db(retries: int = 6, initial_delay: float = 0.5):
    """
    Try to wake the remote DB in the background with exponential backoff.
    When successful sets DB_READY = True.
    """
    global DB_READY
    if DB_IS_SQLITE:
        DB_READY = True
        print("✅ SQLite detected — DB ready")
        return

    delay = initial_delay
    for attempt in range(1, retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            DB_READY = True
            print(f"🔥 Background DB warm-up complete (attempt {attempt})")
            return
        except Exception as e:
            # Print short message and sleep, retry with backoff
            print(f"🛌 DB warm-up attempt {attempt} failed: {e!r} — retrying in {delay:.1f}s")
            time.sleep(delay)
            delay = min(delay * 2, 10.0)

    # if we get here DB is not ready yet
    DB_READY = False
    print("⚠️ Background DB warm-up finished: DB still not reachable")


# Start warm-up without blocking UI
threading.Thread(target=warm_db, daemon=True).start()


# =====================================
# Sessions (get_session returns None if DB unavailable)
# =====================================
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session():
    """
    Returns a SQLAlchemy Session or None if DB is not ready.
    Callers must handle None (returning safe fallback).
    """
    # If using SQLite we always return a session immediately
    if DB_IS_SQLITE:
        return SessionLocal()

    # If background warm-up hasn't marked DB ready, return None quickly
    if not DB_READY:
        return None

    # DB_READY True => create regular session but guard against runtime errors
    try:
        return SessionLocal()
    except (OperationalError, DBAPIError) as e:
        print("⚠️ get_session failed to create a session:", e)
        return None


# =====================================
# Init DB (manual)
# =====================================
def init_db():
    models.Base.metadata.create_all(bind=engine)
    print("✅ Database tables initialized")


# =====================================
# Manual DB test
# =====================================
def test_db_connection():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ Database connection OK")
        return True
    except OperationalError as e:
        print(f"❌ Database connection failed: {e}")
        return False


# =====================================
# SQLite fallback defaults (safe)
# =====================================
def ensure_default_school_and_admin():
    if not str(engine.url).startswith("sqlite"):
        # don't run expensive creation logic on Postgres startup
        return

    from db_helpers import hash_password
    from models import School, User

    db = get_session()
    try:
        models.Base.metadata.create_all(bind=engine)

        school = db.query(School).first()
        if not school:
            school = School(name="Default School", code="DEF001")
            db.add(school)
            db.commit()
            print("🏫 Default SQLite school created")

        admin = db.query(User).filter_by(role="super_admin").first()
        if not admin:
            admin = User(
                username="super_admin",
                role="super_admin",
                school_id=school.id,
                password=hash_password("admin123"),
            )
            db.add(admin)
            db.commit()
            print("👑 SQLite super_admin ready (super_admin / admin123)")

    except Exception as e:
        print("⚠️ SQLite default setup failed:", e)
    finally:
        # safe close only if session returned
        try:
            db.close()
        except Exception:
            pass


ensure_default_school_and_admin()


# =====================================
# Standalone test
# =====================================
if __name__ == "__main__":
    print("🧩 Testing database...")
    init_db()
    test_db_connection()
