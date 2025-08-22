# migrate_feedback_table.py
from sqlmodel import SQLModel, create_engine
from models import Feedback  # noqa: F401 (import ensures model is registered)

DATABASE_URL = "sqlite:///./database.db"  # adjust if yours differs
engine = create_engine(DATABASE_URL, echo=True)

if __name__ == "__main__":
    # creates only missing tables; won't drop anything
    SQLModel.metadata.create_all(engine)
    print("Feedback table ensured ✅")
