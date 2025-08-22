import sqlite3

# Path to your SQLite database
DB_PATH = "database.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 1️⃣ Check if the 'attendance_date' column already exists
cursor.execute("PRAGMA table_info(attendance)")
columns = [col[1] for col in cursor.fetchall()]

if "attendance_date" not in columns:
    print("Renaming 'date' column to 'attendance_date'...")

    # 2️⃣ Create a new table with the correct column name
    cursor.execute("""
        CREATE TABLE attendance_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            attendance_date DATE NOT NULL,
            status TEXT NOT NULL
        )
    """)

    # 3️⃣ Copy data from old table to new table
    cursor.execute("""
        INSERT INTO attendance_new (id, student_id, attendance_date, status)
        SELECT id, student_id, date, status FROM attendance
    """)

    # 4️⃣ Drop old table
    cursor.execute("DROP TABLE attendance")

    # 5️⃣ Rename new table to old name
    cursor.execute("ALTER TABLE attendance_new RENAME TO attendance")

    conn.commit()
    print("Migration completed successfully.")
else:
    print("Column 'attendance_date' already exists. No migration needed.")

conn.close()
