from backend.models import Base
from backend.db_helpers import ensure_super_admin_exists
from backend.database import engine
from backend.database import seed_default_classes
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
print("🔥 Initializing database...")
from backend.db_helpers import ensure_super_admin_exists
Base.metadata.create_all(bind=engine)

ensure_super_admin_exists()
seed_default_classes()

print("✅ Database ready.")