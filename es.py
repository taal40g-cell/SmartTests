from models import Base
from database import engine  # or adjust this import if your engine is in a different module

print("🔄 Creating missing tables...")
Base.metadata.create_all(engine)
print("✅ All models are now synced with the database.")
