# seed_classes.py

from backend.database import get_session
from backend.models import Class

def seed_classes():
    db = get_session()
    try:
        class_names = [
            "JHS 1", "JHS 2", "JHS 3",
            "SHS 1", "SHS 2", "SHS 3"
        ]

        for name in class_names:
            exists = db.query(Class).filter_by(name=name).first()
            if not exists:
                db.add(Class(name=name))

        db.commit()
        print("✅ Classes seeded successfully")

    finally:
        db.close()

if __name__ == "__main__":
    seed_classes()
