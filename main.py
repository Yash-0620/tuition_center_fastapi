from fastapi import FastAPI, Request, Form, Depends, Body, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import SQLModel, Session, create_engine, select
from typing import Optional
from models import User, Tutor, Student, Attendance, Journal
from datetime import date, datetime
from calendar import monthrange
from models import Test
from init_db import init_db

# Run DB initialization at startup
init_db()


app = FastAPI()
templates = Jinja2Templates(directory="templates")
engine = create_engine("sqlite:///database.db")


def get_session():
    with Session(engine) as session:
        yield session

# ✅ Helper function to get logged-in user or raise 401
def get_current_user(request: Request, session: Session = Depends(get_session)) -> User:
    username = request.cookies.get("username")
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = session.exec(select(User).where(User.username == username)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid user")

    return user


# ---------------- Auth / Index ----------------
@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/signup", response_class=HTMLResponse)
def signup_form(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})


@app.post("/signup")
def signup(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session)
):
    # Check if username or email already exists
    existing_user = session.exec(
        select(User).where((User.username == username) | (User.email == email))
    ).first()
    if existing_user:
        return templates.TemplateResponse(
            "signup.html",
            {
                "request": request,
                "error": "Username or email already exists. Please choose another."
            }
        )

    # Create new user
    user = User(username=username, email=email, phone=phone, password=password)
    session.add(user)
    session.commit()

    # Redirect to dashboard after signup
    resp = RedirectResponse(url="/dashboard", status_code=303)
    resp.set_cookie("username", username)
    return resp



@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login(
    request: Request,
    username_email: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session)
):
    # ✅ Allow login with either username or email (handle None email safely)
    user = session.exec(
        select(User).where(
            ((User.username == username_email) |
             ((User.email != None) & (User.email == username_email))),
            User.password == password
        )
    ).first()

    if user:
        resp = RedirectResponse(url="/dashboard", status_code=303)
        resp.set_cookie("username", user.username)
        return resp
    else:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": True}
        )

@app.get("/logout")
def logout():
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie("username")
    return resp


# ---------------- Dashboard ----------------
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user)
):
    # ✅ Get tutors for this user
    tutors = session.exec(
        select(Tutor).where(Tutor.user_id == user.id)
    ).all()

    # ✅ Get students for this user (via tutors)
    students = session.exec(
        select(Student).where(
            Student.tutor_id.in_([t.id for t in tutors])
        )
    ).all()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "username": user.username,  # For welcome message
        "tutors": tutors,
        "students": students
    })



# ---------------- Tutors / Students ----------------
@app.get("/add-tutor", response_class=HTMLResponse)
def add_tutor_form(request: Request):
    return templates.TemplateResponse("add_tutor.html", {"request": request})


@app.post("/add-tutor")
def add_tutor(request: Request, name: str = Form(...), subject: str = Form(...), phone: str = Form(...),
              session: Session = Depends(get_session)):
    username = request.cookies.get("username")
    user = session.exec(select(User).where(User.username == username)).first()
    if not user:
        return RedirectResponse("/login", status_code=303)

    tutor = Tutor(name=name, subject=subject, phone=phone, user_id=user.id)
    session.add(tutor)
    session.commit()
    return RedirectResponse("/dashboard", status_code=303)


@app.get("/tutors", response_class=HTMLResponse)
def show_tutors(request: Request, session: Session = Depends(get_session)):
    username = request.cookies.get("username")
    user = session.exec(select(User).where(User.username == username)).first()
    if not user:
        return RedirectResponse("/login", status_code=303)
    tutors = session.exec(select(Tutor).where(Tutor.user_id == user.id)).all()
    return templates.TemplateResponse("tutors.html", {"request": request, "tutors": tutors})


@app.get("/tutor/{tutor_id}/students", response_class=HTMLResponse)
def view_students(tutor_id: int, request: Request, session: Session = Depends(get_session)):
    students = session.exec(select(Student).where(Student.tutor_id == tutor_id)).all()
    return templates.TemplateResponse("students.html", {"request": request, "students": students, "tutor_id": tutor_id})


@app.get("/tutor/{tutor_id}/add-student", response_class=HTMLResponse)
def add_student_form(tutor_id: int, request: Request):
    return templates.TemplateResponse("add_student.html", {"request": request, "tutor_id": tutor_id})


@app.post("/tutor/{tutor_id}/add-student")
def add_student(
    tutor_id: int,
    name: str = Form(...),
    grade: str = Form(...),
    school: str = Form(...),
    syllabus: str = Form(None),
    focus_subjects: str = Form(None),
    subject: str = Form(None),
    remarks: str = Form(""),
    session: Session = Depends(get_session)
):
    student = Student(
        name=name,
        grade=grade,
        school=school,
        syllabus=syllabus,
        focus_subjects=focus_subjects,
        subject=subject,
        remarks=remarks,
        tutor_id=tutor_id
    )
    session.add(student)
    session.commit()
    return RedirectResponse(f"/tutor/{tutor_id}/students", status_code=303)



# ---------- Edit Student ----------
@app.get("/student/{student_id}/edit", response_class=HTMLResponse)
def edit_student_form(student_id: int, request: Request, session: Session = Depends(get_session)):
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return templates.TemplateResponse("edit_student.html", {"request": request, "student": student})


# ---------------- Edit Student ----------------
@app.get("/student/{student_id}/edit", response_class=HTMLResponse)
def edit_student_form(student_id: int, request: Request, session: Session = Depends(get_session)):
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return templates.TemplateResponse("edit_student.html", {"request": request, "student": student})


@app.post("/student/{student_id}/edit")
def edit_student(student_id: int,
                 name: str = Form(...),
                 grade: str = Form(...),
                 school: str = Form(...),
                 syllabus: str = Form(""),
                 focus_subjects: str = Form(""),
                 subject: str = Form(""),
                 remarks: str = Form(""),
                 session: Session = Depends(get_session)):
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    student.name = name
    student.grade = grade
    student.school = school
    student.syllabus = syllabus
    student.focus_subjects = focus_subjects
    student.subject = subject
    student.remarks = remarks

    session.add(student)
    session.commit()

    return RedirectResponse(url=f"/tutor/{student.tutor_id}/students", status_code=303)




# ---------------- Journal ----------------
@app.get("/student/{student_id}/journal", response_class=HTMLResponse)
def view_journal(student_id: int, request: Request, session: Session = Depends(get_session)):
    student = session.get(Student, student_id)
    if not student:
        return RedirectResponse("/dashboard", status_code=303)

    journals = session.exec(
        select(Journal).where(Journal.student_id == student_id).order_by(Journal.entry_date.desc())
    ).all()

    return templates.TemplateResponse("journal.html", {
        "request": request,
        "student": student,
        "journals": journals
    })


@app.get("/student/{student_id}/journal/add", response_class=HTMLResponse)
def add_journal_form(student_id: int, request: Request, session: Session = Depends(get_session)):
    student = session.get(Student, student_id)
    if not student:
        return RedirectResponse("/dashboard", status_code=303)

    return templates.TemplateResponse("journal_add.html", {"request": request, "student": student, "today": date.today().isoformat()})


@app.post("/student/{student_id}/journal/add")
def add_journal(student_id: int,
                subject: str = Form(...),
                topic: str = Form(...),
                remarks: str = Form(""),
                entry_date: str = Form(...),
                session: Session = Depends(get_session)):
    # parse date safely
    try:
        parsed_date = datetime.strptime(entry_date, "%Y-%m-%d").date()
    except Exception:
        parsed_date = date.today()

    journal_entry = Journal(
        student_id=student_id,
        subject=subject,
        topic=topic,
        remarks=remarks,
        entry_date=parsed_date
    )
    session.add(journal_entry)
    session.commit()
    return RedirectResponse(f"/student/{student_id}/journal", status_code=303)


# ---------------- Attendance ----------------
# ---------- Attendance Routes ----------


from datetime import date

from datetime import datetime, date

from datetime import date, datetime

@app.get("/student/{student_id}/attendance-view", response_class=HTMLResponse)
def view_attendance(
    request: Request,
    student_id: int,
    month: int = Query(None),
    year: int = Query(None),
    session: Session = Depends(get_session)
):
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    all_records = session.exec(
        select(Attendance).where(Attendance.student_id == student_id)
    ).all()

    if not all_records:
        return templates.TemplateResponse("attendance_view.html", {
            "request": request,
            "student": student,
            "records": [],
            "months_list": [],
            "years_list": [],
            "current_month": None,
            "current_year": None
        })

    unique_months_years = sorted(
        {(rec.attendance_date.month, rec.attendance_date.year) for rec in all_records if rec.attendance_date},
        key=lambda x: (x[1], x[0]),
        reverse=True
    )

    if not month or not year:
        month, year = unique_months_years[0]

    today_date = date.today()
    records = []
    for rec in all_records:
        if rec.attendance_date and rec.attendance_date.month == month and rec.attendance_date.year == year:
            rec_date = rec.attendance_date
            if isinstance(rec_date, str):
                rec_date = datetime.strptime(rec_date, "%Y-%m-%d").date()

            records.append({
                "display_date": rec_date.strftime("%d-%m-%Y"),
                "status": rec.status,
                "is_weekend": rec_date.weekday() in (5, 6),
                "is_today": rec_date == today_date
            })

    records.sort(key=lambda r: datetime.strptime(r["display_date"], "%d-%m-%Y"), reverse=True)

    months_list = [{"value": m, "name": date(2000, m, 1).strftime("%B")} for m in range(1, 13)]
    years_list = sorted({y for _, y in unique_months_years}, reverse=True)

    return templates.TemplateResponse("attendance_view.html", {
        "request": request,
        "student": student,
        "records": records,
        "months_list": months_list,
        "years_list": years_list,
        "current_month": month,
        "current_year": year
    })



@app.get("/attendance", response_class=HTMLResponse)
def mark_attendance(
    request: Request,
    session: Session = Depends(get_session)
):
    today = date.today()

    # ✅ Identify logged-in user
    username = request.cookies.get("username")
    if not username:
        return RedirectResponse("/login", status_code=303)

    user = session.exec(select(User).where(User.username == username)).first()
    if not user:
        return RedirectResponse("/login", status_code=303)

    # ✅ Read query params safely
    month_param = request.query_params.get("month")
    year_param = request.query_params.get("year")

    try:
        month = int(month_param) if month_param else today.month
    except ValueError:
        month = today.month

    try:
        year = int(year_param) if year_param else today.year
    except ValueError:
        year = today.year

    # ✅ Get only tutors for this user
    tutors = session.exec(select(Tutor).where(Tutor.user_id == user.id)).all()
    tutor_ids = [t.id for t in tutors]

    # ✅ Get only students for these tutors
    students = session.exec(select(Student).where(Student.tutor_id.in_(tutor_ids))).all()

    # ✅ Determine earliest and latest years from DB (only these students)
    all_records = session.exec(
        select(Attendance).where(Attendance.student_id.in_([s.id for s in students]))
    ).all()

    if all_records:
        earliest_year = min(
            rec.attendance_date.year
            for rec in all_records
            if rec.attendance_date
        )
    else:
        earliest_year = today.year

    years_list = list(range(today.year, earliest_year - 1, -1))
    months_list = [
        {"value": m, "name": date(2000, m, 1).strftime("%B")}
        for m in range(1, 13)
    ]

    # ✅ Number of days in selected month/year
    import calendar
    num_days = calendar.monthrange(year, month)[1]

    # ✅ Get attendance for selected month/year only (only these students)
    filtered_records = session.exec(
        select(Attendance)
        .where(Attendance.student_id.in_([s.id for s in students]))
        .where(Attendance.attendance_date >= date(year, month, 1))
        .where(Attendance.attendance_date <= date(year, month, num_days))
    ).all()

    # ✅ Create attendance map {student_id: {date: status}}
    attendance_map = {}
    for rec in filtered_records:
        if rec.student_id not in attendance_map:
            attendance_map[rec.student_id] = {}
        attendance_map[rec.student_id][rec.attendance_date.strftime("%Y-%m-%d")] = rec.status.lower()

    return templates.TemplateResponse("mark_attendance.html", {
        "request": request,
        "students": students,
        "attendance_map": attendance_map,
        "months_list": months_list,
        "years_list": years_list,
        "current_month": month,
        "current_year": year,
        "current_month_name": date(2000, month, 1).strftime("%B"),
        "num_days": num_days
    })




@app.post("/attendance/update")
def update_attendance(data: dict, session: Session = Depends(get_session)):
    from datetime import datetime

    try:
        student_id = int(data.get("student_id"))
        date_str = data.get("date")
        status = data.get("status")

        attendance_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        existing = session.exec(
            select(Attendance)
            .where(Attendance.student_id == student_id)
            .where(Attendance.attendance_date == attendance_date)  # ✅ Fixed
        ).first()

        if existing:
            existing.status = status
            session.add(existing)
        else:
            new_attendance = Attendance(
                student_id=student_id,
                attendance_date=attendance_date,  # ✅ Fixed
                status=status
            )
            session.add(new_attendance)

        session.commit()
        return {"success": True}

    except Exception as e:
        return {"success": False, "error": str(e)}


# ---------- Add Test Record Route ----------
from fastapi import Form

@app.post("/student/{student_id}/tests/add", response_class=HTMLResponse)
def add_test(
    request: Request,
    student_id: int,
    subject: str = Form(...),
    test_date: str = Form(...),
    total_marks: int = Form(...),
    marks_attained: int = Form(...),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user)
):
    # Verify student exists
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Verify tutor owns student
    tutor = session.get(Tutor, student.tutor_id)
    if not tutor or tutor.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to add tests for this student")

    # Convert date string to date object
    from datetime import datetime
    parsed_date = datetime.strptime(test_date, "%Y-%m-%d").date()

    # Create new test entry
    new_test = Test(
        student_id=student_id,
        subject=subject,
        test_date=parsed_date,
        total_marks=total_marks,
        marks_attained=marks_attained
    )
    session.add(new_test)
    session.commit()

    # Redirect back to tests view
    return RedirectResponse(url=f"/student/{student_id}/tests", status_code=303)


# ---------- View Tests Route ----------
from fastapi import Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from sqlmodel import select, Session
from datetime import date

@app.get("/student/{student_id}/tests", response_class=HTMLResponse)
def view_tests(
    request: Request,
    student_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user)  # ✅ Make sure get_current_user exists
):
    # Get the student
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Ensure this student belongs to one of the current user's tutors
    tutor = session.get(Tutor, student.tutor_id)
    if not tutor or tutor.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this student's tests")

    # Fetch tests for this student
    tests = session.exec(
        select(Test)
        .where(Test.student_id == student_id)
        .order_by(Test.test_date.desc())
    ).all()

    return templates.TemplateResponse("view_tests.html", {
        "request": request,
        "student": student,
        "tests": tests
    })



# ---------------- Startup ----------------
@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)
