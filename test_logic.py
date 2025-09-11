# reset_admin.py
from helpers import _load_unified_data, _save_unified_data, _hash_password

NEW_PASSWORD = "1234"  # Change to any password you want

data = _load_unified_data()
data.setdefault("admins", {})
data["admins"]["Admin"] = {
    "password": _hash_password(NEW_PASSWORD),
    "role": "superadmin"
}
_save_unified_data(data)


