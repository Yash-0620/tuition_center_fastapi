from sqlmodel import SQLModel, create_engine
from sqlalchemy import inspect, text

# ✅ Use your actual database URL here
DATABASE_URL = "sqlite:///database.db"  # Adjust path if needed
engine = create_engine(DATABASE_URL, echo=True)

# ------------------------------
# DROP OLD `test` TABLE IF EXISTS
# ------------------------------
with engine.connect() as conn:
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    if "test" in tables:  # Old table name
        print("⚠ Found old `test` table. Dropping...")
        conn.execute(text("DROP TABLE test"))
        conn.commit()
        print("✅ Dropped old `test` table.")
    else:
        print("✅ No old `test` table found.")

# ------------------------------
# CREATE ALL TABLES FROM MODELS
# ------------------------------
# Import your models so SQLModel knows about them
from models import User, Tutor, Student, Attendance, Journal, TestRecord

SQLModel.metadata.create_all(engine)
print("✅ Database schema synced with latest models.")