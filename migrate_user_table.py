import sqlite3

# Path to your database file
db_path = "database.db"  # change if your DB file has a different name

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# ===== USER TABLE MIGRATION =====
try:
    cursor.execute("ALTER TABLE user ADD COLUMN email TEXT;")
except sqlite3.OperationalError:
    print("Column 'email' already exists in user table.")

try:
    cursor.execute("ALTER TABLE user ADD COLUMN phone TEXT;")
except sqlite3.OperationalError:
    print("Column 'phone' already exists in user table.")


# ===== STUDENT TABLE MIGRATION =====
try:
    cursor.execute("ALTER TABLE student ADD COLUMN syllabus TEXT;")
except sqlite3.OperationalError:
    print("Column 'syllabus' already exists in student table.")

try:
    cursor.execute("ALTER TABLE student ADD COLUMN focus_subjects TEXT;")
except sqlite3.OperationalError:
    print("Column 'focus_subjects' already exists in student table.")

try:
    cursor.execute("ALTER TABLE student ADD COLUMN subject TEXT;")
except sqlite3.OperationalError:
    print("Column 'subject' already exists in student table.")

conn.commit()
conn.close()

print("✅ Migration complete — all required columns added.")
