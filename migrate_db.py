import os
from sqlalchemy import create_engine, text
from sqlmodel import SQLModel, Session
from models import User

# This will re-use your database engine from db.py
from db import engine

# Make sure you import the new models to create their metadata
from models import Tutor, Student, Journal, Attendance, TestRecord, UpcomingTest, Feedback

def run_migration():
    """Adds missing columns to the User table."""
    try:
        # Check if the columns already exist to avoid errors
        with Session(engine) as session:
            result = session.exec(text("PRAGMA table_info(user)")).all()
            columns = [col[1] for col in result]

            if 'user_type' not in columns:
                print("Adding 'user_type' column to the 'user' table...")
                session.exec(text("ALTER TABLE user ADD COLUMN user_type VARCHAR(255) DEFAULT 'admin' NOT NULL"))
                session.commit()
                print("'user_type' column added successfully.")

            if 'tutor_id' not in columns:
                print("Adding 'tutor_id' column to the 'user' table...")
                session.exec(text("ALTER TABLE user ADD COLUMN tutor_id INTEGER REFERENCES tutor(id)"))
                session.commit()
                print("'tutor_id' column added successfully.")

    except Exception as e:
        print(f"An error occurred during migration: {e}")
        # Rollback in case of error
        session.rollback()

if __name__ == "__main__":
    print("Starting database migration...")
    run_migration()
    print("Migration script finished.")