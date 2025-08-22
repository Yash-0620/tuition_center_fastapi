# migrate_student.py
import sqlite3

db_path = "database.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Expected new columns for student
new_columns = {
    "syllabus": "TEXT",
    "focus_subjects": "TEXT",
    "subject": "TEXT",
    "remarks": "TEXT"
}

# Get existing columns
cursor.execute("PRAGMA table_info(student)")
existing_cols = [col[1] for col in cursor.fetchall()]

# Add missing columns
for col, col_type in new_columns.items():
    if col not in existing_cols:
        print(f"Adding column {col} to student...")
        cursor.execute(f"ALTER TABLE student ADD COLUMN {col} {col_type}")

conn.commit()
conn.close()

print("✅ Student table migration complete")
