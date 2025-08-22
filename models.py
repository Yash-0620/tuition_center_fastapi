from typing import Optional, List
from datetime import date
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import date, datetime
from sqlmodel import SQLModel, Field


# -------------------- USER --------------------
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str
    email: Optional[str] = None
    phone: Optional[str] = None
    password: str

    tutors: List["Tutor"] = Relationship(back_populates="user")


# -------------------- TUTOR --------------------
class Tutor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    subject: str
    phone: str
    user_id: int = Field(foreign_key="user.id")

    user: Optional[User] = Relationship(back_populates="tutors")
    students: List["Student"] = Relationship(back_populates="tutor")


# -------------------- STUDENT --------------------
class Student(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    grade: str
    school: Optional[str] = None

    # Newly added fields
    syllabus: Optional[str] = None
    focus_subjects: Optional[str] = None
    subject: Optional[str] = None
    remarks: Optional[str] = None

    tutor_id: int = Field(foreign_key="tutor.id")

    tutor: "Tutor" = Relationship(back_populates="students")
    journals: List["Journal"] = Relationship(back_populates="student")
    attendance_records: List["Attendance"] = Relationship(back_populates="student")
    tests: List["TestRecord"] = Relationship(back_populates="student")
    upcoming_tests: List["UpcomingTest"] = Relationship(back_populates="student")



# -------------------- ATTENDANCE --------------------
class Attendance(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.id")
    attendance_date: date
    status: str

    student: Optional[Student] = Relationship(back_populates="attendance_records")


# -------------------- JOURNAL --------------------
class Journal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.id")
    entry_date: date
    tutor_name:str
    subject: str
    journal: str
    remarks: str

    student: Optional[Student] = Relationship(back_populates="journals")


# -------------------- TEST RECORD --------------------
class TestRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.id")
    subject: str
    topic: str
    test_date: date
    total_marks: int                   # ✅ changed score → total_marks
    marks_attained: int                # ✅ newly added
    remarks: str

    student: "Student" = Relationship(back_populates="tests")

# -------------------- UPCOMING TEST --------------------
class UpcomingTest(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.id")
    subject: str
    topics: Optional[str] = None
    test_date: date

    # Relationship back to Student
    student: "Student" = Relationship(back_populates="upcoming_tests")

# -------------------- FEEDBACK --------------------
class Feedback(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.id", index=True)

    # 'daily' | 'weekly' | 'monthly'
    period: str

    start_date: date
    end_date: date
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    # store the AI output; keep it simple & robust
    summary: str
    strengths: Optional[str] = None
    areas_for_improvement: Optional[str] = None
    actions: Optional[str] = None


