# ==============================
# backend/database.py (CLEAN PRODUCTION VERSION)
# ==============================

import os
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError

from backend import models
from backend.security import hash_password


# ==============================
# GLOBAL ENGINE STATE
# ==============================
_engine = None
_initialized = False


# ==============================
# ENVIRONMENT
# ==============================
def get_env():
    return os.getenv("ENV", "local").strip().lower()


# ==============================
# DATABASE URL RESOLVER
# ==============================
def resolve_database_url():
    env = get_env()

    # ---------------- LOCAL ----------------
    if env == "local":
        return "sqlite:///smarttest.db"

    # ---------------- PRODUCTION ----------------
    url = os.getenv("DATABASE_URL")

    if not url:
        raise RuntimeError("DATABASE_URL is missing in production environment")

    # Fix legacy postgres URL format
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)

    # Ensure SSL for hosted DBs (Render, etc.)
    if "sslmode" not in url:
        url += "&sslmode=require" if "?" in url else "?sslmode=require"

    return url


# ==============================
# ENGINE (SINGLETON)
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
            pool_size=5,
            max_overflow=2,
            future=True,
        )

    return _engine


# ==============================
# SESSION FACTORY
# ==============================
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
)


def get_session():
    return SessionLocal(bind=get_engine())


# ==============================
# SAFE DB EXECUTOR
# ==============================
def db_execute(fn):
    db = get_session()
    try:
        return fn(db)
    finally:
        db.close()


# ==============================
# INIT DATABASE SCHEMA ONLY
# ==============================
def init_db():
    """
    ONLY creates tables. No seeding, no business logic.
    Safe to call multiple times.
    """
    global _initialized

    if _initialized:
        return

    engine = get_engine()

    try:
        with engine.begin() as conn:
            models.Base.metadata.create_all(bind=conn)

        _initialized = True
        print("✅ Database schema initialized")

    except Exception as e:
        print("⚠️ init_db failed:", e)


# ==============================
# LIGHTWEIGHT MIGRATIONS
# ==============================
def run_migrations():
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
# DEFAULT SYSTEM DATA (SAFE SEED ONLY)
# ==============================
def seed_core_data():
    """
    Only seeds absolute minimum system data.
    NEVER seeds classes or business logic.
    """
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
# STARTUP ORCHESTRATION
# ==============================
def startup():
    """
    Clean deterministic startup:
    - no caching tricks
    - no class seeding
    - no duplicate generators
    """

    global _initialized

    if _initialized:
        return

    try:
        # 1. Create schema
        init_db()

        # 2. Run safe migrations
        run_migrations()

        # 3. DB health check
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))

        # 4. Seed ONLY core system data
        seed_core_data()

        _initialized = True

        print("🔥 Database startup complete")

    except OperationalError as e:
        print("⚠️ Database connection error:", e)

    except Exception as e:
        print("⚠️ Startup failed:", e)