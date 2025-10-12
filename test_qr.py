# upgrade_students.py
from helpers import _load_unified_data, _save_unified_data
import random
import string

def generate_student_id(existing_ids):
    while True:
        student_id = "STU" + "".join(random.choices(string.digits, k=4))
        if student_id not in existing_ids:
            return student_id

def upgrade_students():
    data = _load_unified_data()
    users = data.get("users", {})
    existing_ids = {u.get("student_id") for u in users.values() if u.get("student_id")}
    updated = False

    for user in users.values():
        if "student_id" not in user:
            user["student_id"] = generate_student_id(existing_ids)
            existing_ids.add(user["student_id"])
            updated = True

    if updated:
        data["users"] = users
        _save_unified_data(data)
        print(f"✅ Added student_id to {len(users)} users.")
    else:
        print("ℹ️ All users already have student_id. No changes made.")

if __name__ == "__main__":
    upgrade_students()
