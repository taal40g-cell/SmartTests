# ==============================
# backend/database.py (FINAL STABLE)
# ==============================

import os
import time

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import NullPool

from backend import models
from backend.security import hash_password


# ==============================
# GLOBAL STATE (CRITICAL FIX)
# ==============================
_engine = None
_initialized = False


# ==============================
# DB URL RESOLVER
# ==============================
def resolve_database_url():
    url = os.getenv("DATABASE_URL")

    if not url:
        print("⚠️ DATABASE_URL missing → running without DB")
        return None

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)

    if "sslmode" not in url:
        url += "&sslmode=require" if "?" in url else "?sslmode=require"

    return url


# ==============================
# ENGINE
# ==============================
def get_engine():
    global _engine

    if _engine is not None:
        return _engine

    url = resolve_database_url()
    if not url:
        return None

    try:
        _engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_recycle=300,
            pool_size=5,
            max_overflow=2,
            future=True,
        )
        return _engine

    except Exception as e:
        print("⚠️ Engine creation failed:", e)
        return None


# ==============================
# SESSION
# ==============================
SessionLocal = sessionmaker(
    autoflush=False,
    autocommit=False,
)


def get_session():
    engine = get_engine()
    if engine is None:
        raise RuntimeError("Database engine not available")

    return SessionLocal(bind=engine)


# ==============================
# SAFE EXECUTOR
# ==============================
def db_execute(fn, retries=2):
    last_error = None

    for attempt in range(max(1, retries)):
        db = None

        try:
            db = get_session()
            return fn(db)

        except Exception as e:
            last_error = e

            if db:
                db.rollback()

            # retry only transient errors
            if (
                ("SSL" in str(e) or "connection" in str(e).lower())
                and attempt < retries - 1
            ):
                time.sleep(1)
                continue

            raise

        finally:
            if db:
                db.close()

    raise last_error


# ==============================
# INIT DB
# ==============================
def init_db(retries=3, delay=2):
    engine = get_engine()

    if not engine:
        print("⚠️ DB not available → skipping init_db")
        return

    for attempt in range(retries):
        try:
            with engine.begin() as conn:
                models.Base.metadata.create_all(bind=conn)

            print("✅ DB initialized")
            return

        except OperationalError as e:
            print(f"⚠️ init_db attempt {attempt + 1} failed:", e)
            time.sleep(delay)

    print("⚠️ init_db skipped after retries")


# ==============================
# MIGRATIONS
# ==============================
def add_missing_columns():
    engine = get_engine()
    if not engine:
        return

    try:
        inspector = inspect(engine)

        if "student_progress" not in inspector.get_table_names():
            return

        columns = {c["name"] for c in inspector.get_columns("student_progress")}

        with engine.begin() as conn:

            if "reviewed" not in columns:
                conn.execute(text(
                    "ALTER TABLE student_progress ADD COLUMN reviewed BOOLEAN DEFAULT FALSE"
                ))

            if "score" not in columns:
                conn.execute(text(
                    "ALTER TABLE student_progress ADD COLUMN score FLOAT"
                ))

            if "status" not in columns:
                conn.execute(text(
                    "ALTER TABLE student_progress ADD COLUMN status TEXT DEFAULT 'pending'"
                ))

        print("✅ migrations applied")

    except Exception as e:
        print("⚠️ migrations skipped:", e)


# ==============================
# SEED DATA
# ==============================
def ensure_default_data():
    from backend.models import School, User

    def _seed(db):
        print("🔥 ensure_default_data RUNNING")

        school = db.query(School).first()

        if not school:
            school = School(name="Default School", code="DEF001")
            db.add(school)
            db.commit()
            db.refresh(school)

        admin = db.query(User).filter_by(role="super_admin").first()

        print("👉 BEFORE FIX:", admin.school_id if admin else "NO ADMIN")

        if not admin:
            db.add(User(
                username="super_admin",
                role="super_admin",
                school_id=school.id,
                password=hash_password("admin123"),
            ))
            db.commit()
            print("✅ CREATED ADMIN")

        else:
            if admin.school_id is None:
                admin.school_id = school.id
                db.commit()
                print("✅ FIXED ADMIN school_id")

        print("👉 AFTER FIX:", admin.school_id if admin else "NO ADMIN")

    db_execute(_seed)



def seed_default_classes():
    from backend.models import School, Class

    def _seed(db):
        schools = db.query(School).all()

        defaults = ["JHS 1", "JHS 2", "JHS 3", "SHS 1", "SHS 2", "SHS 3"]

        for school in schools:
            existing = {
                c.normalized_name
                for c in db.query(Class).filter(Class.school_id == school.id)
            }

            for name in defaults:
                norm = name.lower().strip()

                if norm not in existing:
                    db.add(Class(
                        name=name,
                        normalized_name=norm,
                        school_id=school.id
                    ))

        db.commit()

    db_execute(_seed)


# ==============================
# STARTUP (IDEMPOTENT FIX)
# ==============================
def startup():
    global _initialized

    if _initialized:
        return

    try:
        init_db()
        add_missing_columns()
        ensure_default_data()
        seed_default_classes()

        _initialized = True
        print("🔥 DB startup executed ONCE")

    except Exception as e:
        print("⚠️ DB startup failed:", e)