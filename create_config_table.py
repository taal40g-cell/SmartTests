import sqlite3

DB_FILE = "smarttest.db"

conn = sqlite3.connect(DB_FILE)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")

conn.commit()
conn.close()

print("✅ Config table created.")
