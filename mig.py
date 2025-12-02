import sqlite3
import psycopg2
import json
from datetime import datetime

# -------------------------------
# PostgreSQL connection
# -------------------------------
import psycopg2

pg_config = {
    "host": "dpg-d4gm1kili9vc73dn0d3g-a.oregon-postgres.render.com",
    "port": 5432,
    "dbname": "smarttestdb_2",
    "user": "smarttestdb_2_user",
    "password": "QZOkC4mtDk70RsMM2VgyooOU1gOmPbwh",
    "sslmode": "require"
}

try:
    pg_conn = psycopg2.connect(**pg_config)
    print("✅ Connected to new Postgres DB successfully!")
except Exception as e:
    print("❌ Failed to connect:", e)

# -------------------------------
# SQLite connection
# -------------------------------
sqlite_conn = sqlite3.connect("smarttest_db.sqlite")
sqlite_conn.row_factory = sqlite3.Row
sqlite_cursor = sqlite_conn.cursor()

# -------------------------------
# Helper to convert SQLite row to dict
# -------------------------------
def row_to_dict(row):
    return {k: row[k] for k in row.keys()}

# -------------------------------
# Tables to migrate
# -------------------------------
tables = [
    "schools",
    "students",
    "admins",
    "users",
    "subjects",
    "questions",
    "objective_questions",
    "submissions",
    "retakes",
    "leaderboard",
    "test_results",
    "student_progress",
    "archived_questions",
    "subjective_questions",
    "subjective_answers",
    "subjective_grades",
    "subjective_submissions",
    "test_duration",
    "config",
    "audit_log"
]

# -------------------------------
# Function to migrate a table
# -------------------------------
def migrate_table(table):
    sqlite_cursor.execute(f"SELECT * FROM {table}")
    rows = sqlite_cursor.fetchall()
    if not rows:
        print(f"ℹ️  No data in {table}, skipping.")
        return

    cols = rows[0].keys()
    placeholders = ", ".join([f"%({c})s" for c in cols])
    columns = ", ".join(cols)

    insert_sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"

    for row in rows:
        data = row_to_dict(row)

        # Convert JSON fields
        for key in data:
            if isinstance(data[key], str):
                val = data[key].strip()
                if val.startswith("[") or val.startswith("{"):
                    try:
                        data[key] = json.loads(val)
                    except Exception:
                        pass

        # Convert datetime fields from string if needed
        for dt_field in ["created_at", "submitted_at", "taken_at", "archived_at", "graded_on", "last_saved", "start_time"]:
            if dt_field in data and isinstance(data[dt_field], str):
                try:
                    data[dt_field] = datetime.fromisoformat(data[dt_field])
                except:
                    pass

        try:
            pg_cursor.execute(insert_sql, data)
        except Exception as e:
            print(f"❌ Failed to insert into {table}: {e}")
            continue

    pg_conn.commit()
    print(f"✅ Migrated {len(rows)} rows from {table}")

# -------------------------------
# Migrate all tables
# -------------------------------
for table in tables:
    migrate_table(table)

# -------------------------------
# Close connections
# -------------------------------
sqlite_conn.close()
pg_cursor.close()
pg_conn.close()
print("🎉 Migration complete!")
