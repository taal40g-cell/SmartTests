import csv
import json
import os

csv_file = "users.csv"
json_file = "users.json"

# Class normalization map
class_map = {
    "jhs1": "jhs 1",
    "jhs 2": "jhs 2",
    "jhs2": "jhs 2",
    "jhs3": "jhs 3",
    "jhs 3": "jhs 3"
}

# Load CSV users
csv_users = {}
with open(csv_file, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        access_code = row['access_code'].strip()
        raw_class = row['class'].strip().lower()
        normalized_class = class_map.get(raw_class, raw_class)
        csv_users[access_code] = {
            "name": row['name'].strip(),
            "class": normalized_class,
            "can_retake": row['can_retake'].strip().lower() == "true"
        }

# Load existing JSON if exists
if os.path.exists(json_file):
    with open(json_file, "r", encoding="utf-8") as f:
        json_users = json.load(f)
else:
    json_users = {}

# Update JSON with CSV entries
for code, user in csv_users.items():
    json_users[code] = user

# Save updated JSON
with open(json_file, "w", encoding="utf-8") as f:
    json.dump(json_users, f, indent=4, ensure_ascii=False)

print(f"✅ {len(json_users)} users synced to {json_file}")
