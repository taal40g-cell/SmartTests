# ==============================
# backend/database.py (OPTIMIZED FIXED)
# ==============================

import os
import time
from functools import lru_cache

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError

from backend import models
from backend.security import hash_password

# ==============================
# GLOBAL STATE
# ==============================
_engine = None
_initialized = False


# ==============================
# ENV SAFE LOADER
# ==============================
def get_env():
    return os.getenv("ENV", "local").strip().lower()


# ==============================
# DB URL RESOLVER (FAST)
# ==============================
def resolve_database_url():
    env = get_env()

    # ---------------- LOCAL ----------------
    if env == "local":
        return "sqlite:///smarttest.db"

    # ---------------- PRODUCTION ----------------
    url = os.getenv("DATABASE_URL")

    if not url:
        raise RuntimeError("DATABASE_URL missing in production")

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)

    if "sslmode" not in url:
        url += "&sslmode=require" if "?" in url else "?sslmode=require"

    return url


# ==============================
# ENGINE (CREATED ONCE ONLY)
# ==============================
def get_engine():
    global _engine

    if _engine:
        return _engine

    url = resolve_database_url()

    if url.startswith("sqlite"):
        _engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            future=True,
        )
    else:
        _engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_recycle=300,
            pool_size=3,
            max_overflow=1,
            future=True,
        )

    return _engine


# ==============================
# SESSION (FAST BIND)
# ==============================
SessionLocal = sessionmaker(
    autoflush=False,
    autocommit=False,
)


def get_session():
    return SessionLocal(bind=get_engine())


# ==============================
# LIGHTWEIGHT DB EXECUTOR
# ==============================
def db_execute(fn):
    db = get_session()
    try:
        return fn(db)
    finally:
        db.close()


# ==============================
# INIT DB (RUN ONCE ONLY)
# ==============================
def init_db():
    global _initialized

    if _initialized:
        return

    engine = get_engine()

    try:
        with engine.begin() as conn:
            models.Base.metadata.create_all(bind=conn)

        print("✅ DB initialized")
        _initialized = True

    except Exception as e:
        print("⚠️ init_db failed:", e)


# ==============================
# MIGRATIONS (SAFE)
# ==============================
def add_missing_columns():
    engine = get_engine()

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
# SEED DATA (CACHED PROTECTION)
# ==============================
@lru_cache(maxsize=1)
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





# ==============================
# STARTUP (RUN ONCE ONLY)
# ==============================
def startup():
    global _initialized

    if _initialized:
        return

    engine = get_engine()
    if engine is None:
        print("⚠️ No DB engine → skipping startup")
        return

    try:
        # ONLY RUN ONCE PER APP START
        with engine.begin() as conn:
            models.Base.metadata.create_all(bind=conn)

        add_missing_columns()

        # lightweight ping only
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        ensure_default_data()
        seed_default_classes()

        _initialized = True
        print("🔥 DB startup complete")

    except Exception as e:
        print("⚠️ DB startup failed:", e)