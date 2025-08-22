from sqlmodel import Session, select
from models import Attendance
from database import engine

with Session(engine) as session:
    records = session.exec(
        select(Attendance).order_by(Attendance.id.desc()).limit(5)
    ).all()

    if not records:
        print("No attendance records found.")
    else:
        for r in records:
            print(
                f"ID: {r.id}, Student ID: {r.student_id}, "
                f"Date: {r.attendance_date} ({type(r.attendance_date)}), "
                f"Status: {r.status}"
            )
