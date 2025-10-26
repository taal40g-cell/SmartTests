# add_schools.py
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from models import School

DATABASE_URL = "postgresql://smarttest_db_user:ED2GLylCZ59p6mKwyG4cCUNNoqOZoLET@dpg-d3837lp5pdvs7389osqg-a.oregon-postgres.render.com/smarttest_db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def add_schools(schools_list):
    """
    Adds multiple schools to the database.
    Skips schools that already exist (by unique 'code').

    schools_list: List of dicts with keys: name, code, address
    """
    session = Session()
    try:
        for s in schools_list:
            existing = session.query(School).filter_by(code=s["code"]).first()
            if existing:
                print(f"⚠️ School already exists: {existing.id} {existing.name}")
            else:
                new_school = School(
                    name=s["name"],
                    code=s["code"],
                    address=s.get("address", "")
                )
                session.add(new_school)
                session.commit()
                print(f"✅ School added successfully! ID: {new_school.id} {new_school.name}")
    except Exception as e:
        session.rollback()
        print("❌ Error:", e)
    finally:
        session.close()

# =============================
# ✅ Example Usage
# =============================
if __name__ == "__main__":
    schools_to_add = [
        {"name": "Bright Future Academy", "code": "bfa2025", "address": "Tamale"},
        {"name": "King of Kings", "code": "kok2025", "address": "Koforidua"},
        {"name": "Sunrise International", "code": "sun2025", "address": "Accra"},
    ]

    add_schools(schools_to_add)
