import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
import os
print("🔍 DATABASE_URL loaded:", os.getenv("DATABASE_URL"))

# =====================================
# Database URL Configuration
# =====================================

# Prefer environment variable (Render/production)
DATABASE_URL = os.getenv("DATABASE_URL")

# ✅ Fallback to local PostgreSQL or SQLite
if not DATABASE_URL or not isinstance(DATABASE_URL, str) or "://" not in DATABASE_URL:
    print("⚠️ DATABASE_URL not found or invalid. Using local SQLite database instead.")
    DATABASE_URL = "sqlite:///smarttest.db"

# =====================================
# Engine Setup
# =====================================

# For SQLite, allow multi-threaded access (needed for Streamlit)
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

try:
    # Ensure Render-style PostgreSQL URLs are compatible with SQLAlchemy
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)

    engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)
except Exception as e:
    print(f"❌ Failed to create database engine: {e}")
    print("⚙️ Falling back to local SQLite database.")
    DATABASE_URL = "sqlite:///smarttest.db"
    connect_args = {"check_same_thread": False}
    engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)

# =====================================
# Session and Base
# =====================================

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# =====================================
# Helper Functions
# =====================================

def get_session():
    """Create and return a new SQLAlchemy session."""
    return SessionLocal()

def test_db_connection() -> bool:
    """
    Test database connection.
    Returns True if connection succeeds, otherwise False.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ Database connection successful.")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False
