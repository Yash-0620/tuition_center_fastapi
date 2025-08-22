# cleanup_recreate_db.py
from sqlmodel import SQLModel
from sqlalchemy import create_engine
import models  # ✅ Ensure all models are loaded

DATABASE_URL = "sqlite:///database.db"
engine = create_engine(DATABASE_URL, echo=True)

print("⚠️ This will delete ALL existing data!")
confirm = input("Type 'YES' to continue: ")
if confirm.strip().upper() == "YES":
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    print("✅ Database reset complete.")
else:
    print("❌ Cancelled.")
