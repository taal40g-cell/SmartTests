import os
import threading
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
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


# =====================================
# Render-safe connect args
# =====================================
def make_connect_args(url):
    if url.startswith("sqlite"):
        return {"check_same_thread": False}

    # Render free PostgreSQL sleeps → need long timeout
    return {
        "sslmode": "require",
        "connect_timeout": 60,   # <<< INCREASED (important)
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    }


# =====================================
# Create engine (FAST + LAZY mode)
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
        pool_timeout=20,
        echo=False,
    )

    print("✅ Engine created (lazy mode, no forced connect)")
    return engine


engine = create_safe_engine(DATABASE_URL)


# =====================================
# Background warm-up (fixes slow startup)
# =====================================
def warm_db():
    """Render takes 10–25 seconds to wake DB → wake in background."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("🔥 Background DB warm-up complete")
    except Exception as e:
        print("🛌 DB still sleeping (will wake later):", e)


# Start warm-up without blocking UI
threading.Thread(target=warm_db, daemon=True).start()


# =====================================
# Sessions
# =====================================
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def get_session():
    return SessionLocal()


# =====================================
# Init DB
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
# SQLite fallback defaults
# =====================================
def ensure_default_school_and_admin():
    if not str(engine.url).startswith("sqlite"):
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
        db.close()


ensure_default_school_and_admin()


# =====================================
# Standalone test
# =====================================
if __name__ == "__main__":
    print("🧩 Testing database...")
    init_db()
    test_db_connection()
