# ==============================
# backend/database.py
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
# DATABASE URL RESOLVER
# ==============================
def resolve_database_url():
    url = os.getenv("DATABASE_URL")

    if not url:
        raise Exception("❌ DATABASE_URL not set")

    # Fix old Render format
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)

    # Ensure SSL (required on Render)
    if "sslmode" not in url:
        url += "&sslmode=require" if "?" in url else "?sslmode=require"

    return url


# ==============================
# ENGINE (LAZY INIT)
# ==============================
_engine = None


def get_engine():
    global _engine

    if _engine is None:
        url = resolve_database_url()

        _engine = create_engine(
            url,
            poolclass=NullPool,
            connect_args={"connect_timeout": 10},
            future=True,
        )

    return _engine


# ==============================
# SESSION
# ==============================
SessionLocal = sessionmaker(
    autoflush=False,
    autocommit=False,
)


def get_session():
    return SessionLocal(bind=get_engine())


# ==============================
# SAFE DB EXECUTOR
# ==============================
def db_execute(fn, retries=3):
    last_error = None

    for attempt in range(retries):
        db = get_session()
        try:
            return fn(db)

        except Exception as e:
            db.rollback()
            last_error = e

            # retry only network/SSL issues
            if "SSL connection has been closed" in str(e):
                if attempt < retries - 1:
                    time.sleep(1)
                    continue

            raise

        finally:
            db.close()

    raise last_error


# ==============================
# INIT DB
# ==============================
def init_db(retries=5, delay=2):
    for attempt in range(retries):
        try:
            engine = get_engine()

            with engine.begin() as conn:
                models.Base.metadata.create_all(bind=conn)

            print("✅ DB initialized successfully")
            return

        except OperationalError as e:
            print(f"⚠️ DB init attempt {attempt + 1} failed: {e}")

            if attempt == retries - 1:
                raise

            time.sleep(delay)


# ==============================
# MIGRATIONS
# ==============================
def add_missing_columns():
    engine = get_engine()
    inspector = inspect(engine)

    if "student_progress" not in inspector.get_table_names():
        return

    columns = [c["name"] for c in inspector.get_columns("student_progress")]

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

    print("✅ migrations completed")


# ==============================
# SEED DATA
# ==============================
def ensure_default_data():
    from backend.models import School, User

    def _seed(db):
        school = db.query(School).first()

        if not school:
            school = School(name="Default School", code="DEF001")
            db.add(school)
            db.commit()
            db.refresh(school)

        admin = db.query(User).filter_by(role="super_admin").first()

        if not admin:
            db.add(User(
                username="super_admin",
                role="super_admin",
                school_id=school.id,
                password=hash_password("admin123"),
            ))
            db.commit()

    db_execute(_seed)


def seed_default_classes():
    from backend.models import School, Class

    def _seed(db):
        schools = db.query(School).all()

        default_classes = ["JHS 1", "JHS 2", "JHS 3", "SHS 1", "SHS 2", "SHS 3"]

        for school in schools:

            existing = {
                c.normalized_name
                for c in db.query(Class).filter(Class.school_id == school.id)
            }

            for name in default_classes:
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
# STARTUP
# ==============================
def startup():
    init_db()
    add_missing_columns()
    ensure_default_data()
    seed_default_classes()