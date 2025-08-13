from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import date

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str
    email: Optional[str] = None  # ✅ New field
    phone: Optional[str] = None  # ✅ New field
    password: str



class Tutor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    subject: str
    phone: str
    user_id: int

class Student(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    grade: str
    school: str
    syllabus: Optional[str] = None
    focus_subjects: Optional[str] = None
    subject: Optional[str] = None
    remarks: Optional[str] = None
    tutor_id: int


class Attendance(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int
    attendance_date: date  # ✅ Renamed from `date` to avoid clash
    status: str  # "Present" or "Absent"

class Journal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int
    subject: str
    topic: str
    remarks: Optional[str] = ""
    entry_date: date = Field(default_factory=date.today)

class Test(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int
    subject: str
    test_date: date
    total_marks: int
    marks_attained: int

