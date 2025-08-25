from sqlmodel import SQLModel
from database import engine  # adjust if your engine import path is different
from models import *  # Import all your models so SQLModel knows them

def init_db():
    print("🔹 Initializing database...")
    SQLModel.metadata.create_all(engine)
    print("✅ Database initialized successfully.")

if __name__ == "__main__":
    init_db()
