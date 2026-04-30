import os
from pathlib import Path
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

from backend import models
from backend.security import hash_password

# =====================================
# DATABASE URL RESOLUTION
# =====================================
RAW_DATABASE_URL = os.getenv("DATABASE_URL")


def resolve_database_url():
    if not RAW_DATABASE_URL:
        return "sqlite:///smarttest.db"

    if RAW_DATABASE_URL.startswith("postgres://"):
        return RAW_DATABASE_URL.replace(
            "postgres://",
            "postgresql+psycopg2://",
            1
        )

    return RAW_DATABASE_URL


# =====================================
# ENGINE FACTORY
# =====================================
def make_engine(url: str):
    if url.startswith("sqlite"):
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            echo=False,
        )

    return create_engine(
        url,
        connect_args={"sslmode": "require", "connect_timeout": 5},
        pool_pre_ping=True,
        echo=False,
    )


def create_engine_with_fallback():
    primary_url = resolve_database_url()

    try:
        engine = make_engine(primary_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        print("✅ Connected to primary DB")
        return engine

    except Exception as e:
        print("❌ Primary DB unreachable — using SQLite fallback")
        print(e)

        db_path = Path("C:/Users/User/Desktop/SmartTests/smarttest.db").absolute()
        sqlite_url = f"sqlite:///{db_path}"

        engine = make_engine(sqlite_url)
        print(f"✅ SQLite fallback connected at: {db_path}")
        return engine


# =====================================
# ENGINE + SESSION
# =====================================
engine = create_engine_with_fallback()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

DB_IS_SQLITE = str(engine.url).startswith("sqlite")


def get_session():
    return SessionLocal()


# =====================================
# HELPERS
# =====================================
def normalize_name(name: str) -> str:
    return name.strip().lower().replace(" ", "")


# =====================================
# MIGRATIONS
# =====================================
def add_missing_columns():
    inspector = inspect(engine)

    if "student_progress" not in inspector.get_table_names():
        return

    columns = [c["name"] for c in inspector.get_columns("student_progress")]

    with engine.connect() as conn:

        if "reviewed" not in columns:
            conn.execute(text(
                "ALTER TABLE student_progress ADD COLUMN reviewed BOOLEAN DEFAULT 0"
            ))

        if "score" not in columns:
            conn.execute(text(
                "ALTER TABLE student_progress ADD COLUMN score FLOAT"
            ))

        if "review_comment" not in columns:
            conn.execute(text(
                "ALTER TABLE student_progress ADD COLUMN review_comment TEXT"
            ))

        if "status" not in columns:
            conn.execute(text(
                "ALTER TABLE student_progress ADD COLUMN status TEXT DEFAULT 'pending'"
            ))

        if "reviewed_at" not in columns:
            conn.execute(text(
                "ALTER TABLE student_progress ADD COLUMN reviewed_at DATETIME"
            ))

        if "reviewed_by" not in columns:
            conn.execute(text(
                "ALTER TABLE student_progress ADD COLUMN reviewed_by TEXT"
            ))

        conn.commit()

    print("✅ Migration complete (review columns ensured)")


# =====================================
# INIT DB (SCHEMA ONLY)
# =====================================
def init_db():
    models.Base.metadata.create_all(bind=engine)
    add_missing_columns()
    print("✅ Database initialized")


# =====================================
# SEED DATA (DEV ONLY)
# =====================================
def ensure_default_sqlite_data():
    if not DB_IS_SQLITE:
        return

    from backend.models import School, User

    db = get_session()

    try:
        school = db.query(School).first()
        if not school:
            school = School(name="Default School", code="DEF001")
            db.add(school)
            db.commit()
            print("🏫 Default school created")

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
            print("👑 super_admin created (admin123)")

    finally:
        db.close()


def seed_default_classes():
    from backend.models import School, Class

    db = get_session()

    try:
        schools = db.query(School).all()
        if not schools:
            print("❌ No schools found. Skipping class seeding.")
            return

        default_classes = [
            "JHS 1", "JHS 2", "JHS 3",
            "SHS 1", "SHS 2", "SHS 3",
        ]

        for school in schools:

            existing = {
                c.normalized_name
                for c in db.query(Class)
                .filter(Class.school_id == school.id)
                .all()
            }

            for name in default_classes:
                norm = normalize_name(name)

                if norm in existing:
                    continue

                db.add(Class(
                    name=name,
                    normalized_name=norm,
                    school_id=school.id
                ))

        db.commit()
        print("✅ Default classes seeded (JHS & SHS).")

    except Exception as e:
        db.rollback()
        print("❌ Failed to seed classes:", e)

    finally:
        db.close()


# =====================================
# STARTUP ORCHESTRATOR (ONLY ENTRY POINT)
# =====================================
def startup():
    init_db()
    ensure_default_sqlite_data()
    seed_default_classes()