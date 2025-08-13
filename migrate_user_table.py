import sqlite3

# Path to your database file
db_path = "database.db"  # change if your DB file has a different name

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Add new columns if they don't exist
try:
    cursor.execute("ALTER TABLE user ADD COLUMN email TEXT;")
except sqlite3.OperationalError:
    print("Column 'email' already exists.")

try:
    cursor.execute("ALTER TABLE user ADD COLUMN phone TEXT;")
except sqlite3.OperationalError:
    print("Column 'phone' already exists.")

conn.commit()
conn.close()

print("✅ Migration complete — email & phone columns added.")
