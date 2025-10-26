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
        "connect_timeout": 10,
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
