
from typing import Optional, List
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
    user_type: str = Field(default="admin")
    tutor_id: Optional[int] = Field(default=None, foreign_key="tutor.id")

    tutors: List["Tutor"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={
            "primaryjoin": "User.id == Tutor.user_id"
        }
    )

# -------------------- TUTOR --------------------
class Tutor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    subject: str
    phone: str
    user_id: Optional[int] = Field(foreign_key="user.id")

    user: Optional[User] = Relationship(
        back_populates="tutors",
        sa_relationship_kwargs={
            "primaryjoin": "Tutor.user_id == User.id"
        }
    )
    students: List["Student"] = Relationship(back_populates="tutor")

# -------------------- STUDENT --------------------
class Student(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    grade: str
    school: Optional[str] = None
    syllabus: Optional[str] = None
    focus_subjects: Optional[str] = None
    subject: Optional[str] = None
    remarks: Optional[str] = None
    tutor_id: int = Field(foreign_key="tutor.id")

    tutor: Optional["Tutor"] = Relationship(back_populates="students")
    journals: List["Journal"] = Relationship(back_populates="student")
    attendances: List["Attendance"] = Relationship(back_populates="student")
    tests: List["TestRecord"] = Relationship(back_populates="student")
    upcoming_tests: List["UpcomingTest"] = Relationship(back_populates="student")
    feedbacks: List["Feedback"] = Relationship(back_populates="student")


# -------------------- JOURNAL --------------------
class Journal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.id")
    tutor_name: str
    subject: str
    journal: str
    remarks: str
    entry_date: date = Field(default_factory=date.today)

    student: "Student" = Relationship(back_populates="journals")


# -------------------- ATTENDANCE --------------------
class Attendance(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.id")
    attendance_date: date = Field(default_factory=date.today, index=True)
    status: str

    student: "Student" = Relationship(back_populates="attendances")


# -------------------- TEST RECORD --------------------
class TestRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.id")
    subject: str
    topic: str
    test_date: date
    total_marks: int
    marks_attained: int
    remarks: str

    student: "Student" = Relationship(back_populates="tests")


# -------------------- UPCOMING TEST --------------------
class UpcomingTest(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.id")
    subject: str
    topics: Optional[str] = None
    test_date: date

    student: "Student" = Relationship(back_populates="upcoming_tests")

# -------------------- FEEDBACK --------------------
class Feedback(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.id")
    period: str
    start_date: date
    end_date: date
    feedback_text: str
    ai_generated: bool = Field(default=True)

    student: "Student" = Relationship(back_populates="feedbacks")