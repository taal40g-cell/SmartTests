"""
Initialize the PostgreSQL database for SmartTests.
Creates all tables (admins, students, results, etc.)
and ensures the default super admin exists.
"""

from models import Base
from database import engine
from db_helpers import ensure_super_admin_exists

print("🔄 Creating all database tables...")

# Create all tables in PostgreSQL
Base.metadata.create_all(bind=engine)

# Ensure default admin user
print("👑 Checking or creating super admin...")
ensure_super_admin_exists()

print("✅ Database initialization complete! All tables ready.")
