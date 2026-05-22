import os
import sys

# ==============================
# PATH FIX (must come first)
# ==============================
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

# ==============================
# CORE IMPORTS
# ==============================
from backend.models import Base
from backend.database import get_engine, seed_default_classes
from backend.db_helpers import ensure_super_admin_exists
from sqlalchemy import text


# ==============================
# INIT ENGINE (IMPORTANT FIX)
# ==============================
engine = get_engine()


# ==============================
# INIT DB
# ==============================
def init_database():
    print("🔥 Initializing database...")

    try:
        # Create tables
        Base.metadata.create_all(bind=engine)

        # Sanity check connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        print("✅ Database connection OK")

        # Seed data safely
        ensure_super_admin_exists()
        seed_default_classes()

        print("✅ Database ready.")

    except Exception as e:
        print("❌ Database initialization failed:")
        print(e)
        raise


# ==============================
# RUN
# ==============================
if __name__ == "__main__":
    init_database()