from helpers import _load_unified_data, _save_unified_data, _hash_password

def create_default_super_admin():
    data = _load_unified_data()
    data.setdefault("admins", {})
    data["admins"]["super_admin"] = {
        "password": _hash_password("1234"),
        "role": "super_admin"
    }
    _save_unified_data(data)
    print("✅ Default super_admin created (username: super_admin, password: 1234)")

create_default_super_admin()
