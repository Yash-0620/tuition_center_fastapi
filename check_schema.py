import sqlite3

# Path to your SQLite DB file (adjust if needed)
db_path = "app.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("\n📌 Tables in database:")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
print(cursor.fetchall())

print("\n📌 Schema for testrecord table:")
cursor.execute("PRAGMA table_info(testrecord);")
for col in cursor.fetchall():
    print(col)

conn.close()
