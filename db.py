# db.py
import os
from sqlmodel import SQLModel, create_engine, Session

# Fallback keeps local dev working with SQLite if DATABASE_URL not set
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///database.db")

# Add sslmode for Render PG if not already present
if DATABASE_URL.startswith("postgres") and "sslmode=" not in DATABASE_URL:
    sep = "&" if "?" in DATABASE_URL else "?"
    DATABASE_URL = f"{DATABASE_URL}{sep}sslmode=require"

# For SQLite we need check_same_thread
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    echo=False,            # flip to True if you want SQL logs
    pool_pre_ping=True,
    connect_args=connect_args
)

def init_db():
    from models import SQLModel  # ensure models are imported
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
