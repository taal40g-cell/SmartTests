# view_db.py
import sqlite3

conn = sqlite3.connect("smarttest.db")
cursor = conn.cursor()

print("\nAvailable tables:")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
for row in cursor.fetchall():
    print(" -", row[0])

print("\nSample users:")
for row in cursor.execute("SELECT * FROM users LIMIT 5;"):
    print(row)

print("\nSample questions:")
for row in cursor.execute("SELECT * FROM questions LIMIT 3;"):
    print(row)

conn.close()
