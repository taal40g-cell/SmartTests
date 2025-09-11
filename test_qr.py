import json, os, hashlib

UNIFIED_FILE = "unified_data.json"

def _hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def _load_unified_data():
    if not os.path.exists(UNIFIED_FILE):
        return {"admins": {}}
    with open(UNIFIED_FILE, "r") as f:
        return json.load(f)

def _save_unified_data(data):
    with open(UNIFIED_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = _load_unified_data()
data.setdefault("admins", {})
data["admins"]["Admin"] = {
    "password": _hash_password("1234"),
    "role": "superadmin"
}
_save_unified_data(data)
print("✅ Admin password forcibly reset to 1234")
print(f"🔑 New hash: {_hash_password('1234')}")
