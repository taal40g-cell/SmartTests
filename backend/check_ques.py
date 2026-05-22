from database import SessionLocal
from models import Question

# Open DB session
db = SessionLocal()

# Fetch all rows in questions table
questions = db.query(Question).all()

print(f"✅ Found {len(questions)} question sets in DB:\n")

for q in questions:
    print(f"- {q.class_name} | {q.subject_name} | {len(q.data)} questions")

db.close()
