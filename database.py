import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
import models  # <-- import all models here

# =====================================
# Load DATABASE_URL
# =====================================
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL or "://" not in DATABASE_URL:
    print("⚠️ DATABASE_URL missing — using SQLite fallback")
    DATABASE_URL = "sqlite:///smarttest.db"

# Fix old-style URLs
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)

# =====================================
# Render SSL-safe connect args
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
# Create safe engine
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
    # Test connection
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ Connected to database")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        raise  # Raise instead of falling back
    return engine

engine = create_safe_engine(DATABASE_URL)

# =====================================
# Session
# =====================================
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
def get_session():
    return SessionLocal()

# =====================================
# Init DB
# =====================================
def init_db():
    """Create all tables defined in models.py"""
    models.Base.metadata.create_all(bind=engine)
    print("✅ Database tables created")

# =====================================
# Test DB connection
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
# SQLite fallback: default school & super admin
# =====================================
def ensure_default_school_and_admin():
    """Only used if SQLite fallback is active"""
    if not str(engine.url).startswith("sqlite"):
        return

    from db_helpers import hash_password
    db = get_session()
    try:
        # Ensure tables exist
        models.Base.metadata.create_all(bind=engine)

        # Default school
        from models import School, User
        school = db.query(School).first()
        if not school:
            school = School(name="Default School", code="DEF001")
            db.add(school)
            db.commit()
            print("🏫 Default school created")

        # Default super admin
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
            print("👑 SQLite super_admin ready (username: super_admin, password: admin123)")
    except Exception as e:
        print("⚠️ SQLite default setup failed:", e)
    finally:
        db.close()

ensure_default_school_and_admin()

# =====================================
# Test block
# =====================================
if __name__ == "__main__":
    print("🧩 Testing database...")
    init_db()
    test_db_connection()
