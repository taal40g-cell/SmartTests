from passlib.hash import bcrypt
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from models import Admin  # Make sure your Admin model is imported

DATABASE_URL = "postgresql+psycopg2://smarttest_db_user:ED2GLylCZ59p6mKwyG4cCUNNoqOZoLET@dpg-d3837lp5pdvs7389osqg-a.oregon-postgres.render.com:5432/smarttest_db?sslmode=require"
engine = create_engine(DATABASE_URL)

def check_login(username, password):
    with Session(engine) as session:
        admin = session.execute(
            select(Admin).where(Admin.username == username)
        ).scalar_one_or_none()

        if admin:
            if bcrypt.verify(password, admin.password_hash):
                if admin.role == "super_admin":
                    return True, "super_admin"
                elif admin.school_id is not None:
                    return True, "admin"
        return False, None

# Test login
username_input = "superadmin"
password_input = "admin123"

success, role = check_login(username_input, password_input)
if success:
    print(f"✅ Login success! Role: {role}")
else:
    print("❌ Invalid username or password")
