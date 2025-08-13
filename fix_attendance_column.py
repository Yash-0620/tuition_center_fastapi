import sqlite3

DB_PATH = "database.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("SELECT id, student_id, attendance_date, status FROM attendance ORDER BY attendance_date DESC")
rows = cursor.fetchall()

for row in rows:
    print(row)

conn.close()
