# create_tables.py
from models import Base
from database import engine

print("🔄 Creating all database tables on connected database...")
Base.metadata.create_all(bind=engine)
print("✅ All tables created successfully!")
