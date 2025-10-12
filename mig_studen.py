from database import SessionLocal, engine
from models import Base, User

# Ensure tables exist
Base.metadata.create_all(bind=engine)
session = SessionLocal()

# ✅ Add some sample students
students = [
    {"name": "John Doe", "student_class": "jhs1", "access_code": "abc123"},
    {"name": "Jane Smith", "student_class": "jhs2", "access_code": "xyz789"},
    {"name": "Ali Taal", "student_class": "jhs3", "access_code": "taal001"},
]

for s in students:
    exists = session.query(User).filter_by(access_code=s["access_code"]).first()
    if not exists:
        u = User(
            name=s["name"],
            student_class=s["student_class"],
            access_code=s["access_code"]
        )
        session.add(u)

session.commit()
print("✅ Sample students added.")
session.close()
