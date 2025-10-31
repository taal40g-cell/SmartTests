import os
import time
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError

Base = declarative_base()

print("🔍 DATABASE_URL loaded:", os.getenv("DATABASE_URL"))

# =====================================
# Database URL Configuration
# =====================================
DATABASE_URL = os.getenv("DATABASE_URL")

# ✅ Fallback if no valid DATABASE_URL
if not DATABASE_URL or not isinstance(DATABASE_URL, str) or "://" not in DATABASE_URL:
    print("⚠️ DATABASE_URL not found or invalid. Using local SQLite database instead.")
    DATABASE_URL = "sqlite:///smarttest.db"

# =====================================
# Connection Arguments
# =====================================
def make_connect_args(url):
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {
        "sslmode": "require",
        "connect_timeout": 20,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    }

# =====================================
# Create Engine and Auto-Fallback
# =====================================
def create_safe_engine(url):
    try:
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg2://", 1)

        connect_args = make_connect_args(url)
        engine = create_engine(
            url,
            connect_args=connect_args,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=180,
            pool_size=5,
            max_overflow=10,
            pool_timeout=15,
            pool_use_lifo=True,
        )

        # ✅ Try connecting
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ Connected to main database.")
        return engine

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("⚙️ Falling back to local SQLite database.")
        local_url = "sqlite:///smarttest.db"
        local_engine = create_engine(local_url, connect_args={"check_same_thread": False}, echo=False)
        return local_engine

# Create the actual engine safely
engine = create_safe_engine(DATABASE_URL)

# =====================================
# Session
# =====================================
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def get_session():
    return SessionLocal()

# =====================================
# Initialize DB
# =====================================
def init_db():
    """Create all database tables."""
    import models  # ensure models.py exists
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialized successfully!")


def test_db_connection():
    """Test if database connection works."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✅ Database connection successful.")
            return True
    except OperationalError as e:
        print(f"❌ Database connection failed: {e}")
        return False
# =====================================
# Ensure Default School & Super Admin (for SQLite fallback)
# =====================================
def ensure_default_school_and_admin():
    """Create a default school and super_admin when using local SQLite DB."""
    if not str(engine.url).startswith("sqlite"):
        return  # Only run this when in SQLite fallback mode

    from models import School, User  # adjust to your model names
    from db_helpers import hash_password  # adjust if your hash function lives elsewhere

    db = get_session()
    try:
        # Ensure tables exist
        Base.metadata.create_all(bind=engine)

        # Check for at least one school
        school = db.query(School).first()
        if not school:
            school = School(name="Default School", code="DEF001")
            db.add(school)
            db.commit()
            print("🏫 Created Default School")

        # Check for at least one super_admin
        admin = db.query(User).filter_by(role="super_admin").first()
        if not admin:
            admin = User(
                username="super_admin",
                role="super_admin",
                school_id=school.id,
                password_hash=hash_password("admin123"),
            )
            db.add(admin)
            db.commit()
            print("👑 Created super_admin (username: super_admin, password: admin123)")

    except Exception as e:
        print("⚠️ Failed to ensure default data:", e)
    finally:
        db.close()


# Run automatically when using SQLite
ensure_default_school_and_admin()


# =====================================
# Test block
# =====================================
if __name__ == "__main__":
    print("🧩 Testing database connection...")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT datetime('now')")) if str(engine.url).startswith("sqlite") else conn.execute(text("SELECT NOW()"))
            print("✅ Connected successfully. Current time:", result.scalar())
    except Exception as e:
        print("❌ Final test failed:", e)
