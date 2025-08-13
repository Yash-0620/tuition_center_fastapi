from sqlmodel import SQLModel
from main import engine, Attendance  # Import the Attendance model & engine from your main.py

# Drop only the Attendance table
Attendance.__table__.drop(engine, checkfirst=True)

# Recreate the Attendance table
Attendance.__table__.create(engine, checkfirst=True)

print("✅ Attendance table reset successfully!")
