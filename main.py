from dotenv import load_dotenv

load_dotenv()

from datetime import date, timedelta, datetime
from fastapi import Body, Query, FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlmodel import SQLModel, create_engine, Session, select
from starlette.responses import RedirectResponse
import json

from init_db import init_db
from models import Student, Journal, Attendance, TestRecord, User, Tutor, UpcomingTest, Feedback
from db import engine  # shared engine
from init_db import init_db
from ai_feedback import router as ai_feedback_router, init_templates
from fastapi.staticfiles import StaticFiles
import os


# ---------------- Helper to prevent caching ----------------
def no_cache_response(template_response: HTMLResponse):
    template_response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    template_response.headers["Pragma"] = "no-cache"
    template_response.headers["Expires"] = "0"
    return template_response


# ---------------- App Setup ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(debug=True)
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(BASE_DIR, "static")),
    name="static",
)
templates = Jinja2Templates(directory="templates")
app.state.templates = templates

# Initialize DB (only once!)
init_db()
SQLModel.metadata.create_all(engine)

# Pass templates to subrouter & include AI Feedback router
init_templates(templates)
app.include_router(ai_feedback_router)


def get_session():
    with Session(engine) as session:
        yield session


# Helper function to get logged-in user or raise 401
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
def signup_page(request: Request):
    username = request.cookies.get("username")
    if username:
        return RedirectResponse("/dashboard", status_code=303)
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

    user = User(username=username, email=email, phone=phone, password=password, user_type="admin")
    session.add(user)
    session.commit()

    resp = RedirectResponse(url="/dashboard", status_code=303)
    resp.set_cookie("username", username)
    return resp


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    username = request.cookies.get("username")
    if username:
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login(
        request: Request,
        username_email: str = Form(...),
        password: str = Form(...),
        session: Session = Depends(get_session)
):
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

@app.route('/diagnostics')
def diagnostics():
    return render_template('diagnostics.html')


@app.get("/attendance-today-count")
def attendance_today_count(session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    today = date.today()

    if user.user_type == "admin":
        students_query = select(Student.id).where(Student.tutor_id.in_(
            select(Tutor.id).where(Tutor.user_id == user.id)
        ))
    else:
        students_query = select(Student.id).where(Student.tutor_id == user.tutor_id)

    student_ids = session.exec(students_query).all()

    count = session.exec(
        select(func.count(Attendance.id))
        .where(Attendance.attendance_date == today)
        .where(Attendance.student_id.in_(student_ids))
    ).first()
    return {"count": count or 0}


@app.get("/upcoming-tests-count")
def upcoming_tests_count(session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    today = date.today()
    if user.user_type == "admin":
        students_query = select(Student.id).where(Student.tutor_id.in_(
            select(Tutor.id).where(Tutor.user_id == user.id)
        ))
    else:
        students_query = select(Student.id).where(Student.tutor_id == user.tutor_id)

    student_ids = session.exec(students_query).all()

    count = session.exec(
        select(func.count(UpcomingTest.id))
        .where(UpcomingTest.test_date >= today)
        .where(UpcomingTest.student_id.in_(student_ids))
    ).first()
    return {"count": count or 0}


# ---------------- Dashboard ----------------
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_redirect(request: Request, user: User = Depends(get_current_user)):
    if user.user_type == "admin":
        return RedirectResponse("/admin-dashboard", status_code=303)
    elif user.user_type == "tutor":
        return RedirectResponse("/tutor-dashboard", status_code=303)
    else:
        return RedirectResponse("/login", status_code=303)


@app.get("/admin-dashboard", response_class=HTMLResponse)
def admin_dashboard(request: Request, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    if user.user_type != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    tutors = session.exec(select(Tutor).where(Tutor.user_id == user.id)).all()
    students = session.exec(
        select(Student).where(Student.tutor_id.in_([t.id for t in tutors]))
    ).all()
    print(f"Admin Dashboard: Found {len(students)} students.")

    today = date.today()

    presents_today = session.exec(
        select(func.count(Attendance.id))
        .where(Attendance.attendance_date == today)
        .where(Attendance.student_id.in_([s.id for s in students]))
        .where(func.lower(Attendance.status) == "present")
    ).first() or 0

    absents_today = session.exec(
        select(func.count(Attendance.id))
        .where(Attendance.attendance_date == today)
        .where(Attendance.student_id.in_([s.id for s in students]))
        .where(func.lower(Attendance.status) == "absent")
    ).first() or 0

    record_tests = session.exec(
        select(TestRecord, Student)
        .join(Student)
        .where(TestRecord.student_id.in_([s.id for s in students]))
        .order_by(TestRecord.test_date.desc())
        .limit(5)
    ).all()

    upcoming_tests = session.exec(
        select(UpcomingTest, Student)
        .join(Student)
        .where(UpcomingTest.student_id.in_([s.id for s in students]))
        .order_by(UpcomingTest.test_date.asc())
        .limit(5)
    ).all()

    return no_cache_response(
        templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "username": user.username,
                "user_type": user.user_type,
                "tutors": tutors,
                "students": students,
                "presents_today": presents_today,
                "absents_today": absents_today,
                "record_tests": record_tests,
                "upcoming_tests": upcoming_tests,
            }
        )
    )


@app.get("/tutor-dashboard", response_class=HTMLResponse)
def tutor_dashboard(request: Request, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    if user.user_type != "tutor":
        raise HTTPException(status_code=403, detail="Not authorized")

    tutor = session.get(Tutor, user.tutor_id)
    students = session.exec(select(Student).where(Student.tutor_id == tutor.id)).all()
    print(f"Tutor Dashboard: Found {len(students)} students.")

    today = date.today()

    presents_today = session.exec(
        select(func.count(Attendance.id))
        .where(Attendance.attendance_date == today)
        .where(Attendance.student_id.in_([s.id for s in students]))
        .where(func.lower(Attendance.status) == "present")
    ).first() or 0

    absents_today = session.exec(
        select(func.count(Attendance.id))
        .where(Attendance.attendance_date == today)
        .where(Attendance.student_id.in_([s.id for s in students]))
        .where(func.lower(Attendance.status) == "absent")
    ).first() or 0

    record_tests = session.exec(
        select(TestRecord, Student)
        .join(Student)
        .where(TestRecord.student_id.in_([s.id for s in students]))
        .order_by(TestRecord.test_date.desc())
        .limit(5)
    ).all()

    upcoming_tests = session.exec(
        select(UpcomingTest, Student)
        .join(Student)
        .where(UpcomingTest.student_id.in_([s.id for s in students]))
        .order_by(UpcomingTest.test_date.asc())
        .limit(5)
    ).all()

    return no_cache_response(
        templates.TemplateResponse(
            "tutor_dashboard.html",
            {
                "request": request,
                "username": user.username,
                "user_type": user.user_type,
                "tutor": tutor,
                "students": students,
                "presents_today": presents_today,
                "absents_today": absents_today,
                "record_tests": record_tests,
                "upcoming_tests": upcoming_tests,
            }
        )
    )


# ---------------- Reports ----------------
@app.get("/reports", response_class=HTMLResponse)
def get_reports_page(request: Request, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    tutor_ids = []
    if user.user_type == "admin":
        tutors = session.exec(select(Tutor).where(Tutor.user_id == user.id)).all()
        tutor_ids = [t.id for t in tutors]
    elif user.user_type == "tutor":
        if user.tutor_id:
            tutor_ids.append(user.tutor_id)

    students = []
    if tutor_ids:
        students = session.exec(
            select(Student).where(Student.tutor_id.in_(tutor_ids))
        ).all()

    return templates.TemplateResponse(
        "reports.html",
        {"request": request, "students": students, "user_type": user.user_type}
    )


# ---------------- Tutors / Students ----------------
@app.get("/add-tutor", response_class=HTMLResponse)
def add_tutor_form(request: Request, user: User = Depends(get_current_user)):
    if user.user_type != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    return templates.TemplateResponse("add_tutor.html", {"request": request})


@app.post("/add-tutor")
def add_tutor(request: Request, name: str = Form(...), subject: str = Form(...), phone: str = Form(...),
              session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    if user.user_type != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    new_tutor = Tutor(name=name, subject=subject, phone=phone, user_id=user.id)
    session.add(new_tutor)
    session.commit()
    session.refresh(new_tutor)

    # Create a new user for the tutor
    tutor_user = User(
        username=f"tutor_{new_tutor.id}",
        email=None,
        phone=None,
        password="password",  # Default password, should be changed
        user_type="tutor",
        tutor_id=new_tutor.id
    )
    session.add(tutor_user)
    session.commit()

    return RedirectResponse("/admin-dashboard", status_code=303)


@app.get("/tutors", response_class=HTMLResponse)
def show_tutors(request: Request, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    if user.user_type != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    tutors = session.exec(select(Tutor).where(Tutor.user_id == user.id)).all()
    return templates.TemplateResponse("tutors.html", {"request": request, "tutors": tutors})


@app.get("/tutor/{tutor_id}/students", response_class=HTMLResponse)
def view_students(tutor_id: int, request: Request, session: Session = Depends(get_session),
                  user: User = Depends(get_current_user)):
    tutor = session.get(Tutor, tutor_id)
    if not tutor or (user.user_type == "tutor" and tutor.id != user.tutor_id):
        raise HTTPException(status_code=403, detail="Not authorized to view these students")

    students = session.exec(select(Student).where(Student.tutor_id == tutor_id)).all()
    return templates.TemplateResponse(
        "students.html",
        {"request": request, "students": students, "tutor_id": tutor_id, "tutor_name": tutor.name}
    )


@app.get("/tutor/{tutor_id}/add-student", response_class=HTMLResponse)
def add_student_form(tutor_id: int, request: Request, session: Session = Depends(get_session),
                     user: User = Depends(get_current_user)):
    tutor = session.get(Tutor, tutor_id)
    if not tutor or (user.user_type == "tutor" and tutor.id != user.tutor_id):
        raise HTTPException(status_code=403, detail="Not authorized")
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
        session: Session = Depends(get_session),
        user: User = Depends(get_current_user)
):
    tutor = session.get(Tutor, tutor_id)
    if not tutor or (user.user_type == "tutor" and tutor.id != user.tutor_id):
        raise HTTPException(status_code=403, detail="Not authorized")

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


# ---------------- Student Report ----------------
@app.get("/reports/student/{student_id}", response_class=HTMLResponse)
def get_student_report(
        student_id: int,
        request: Request,
        session: Session = Depends(get_session),
        user: User = Depends(get_current_user)
):
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    tutor = session.get(Tutor, student.tutor_id)
    if not tutor or (user.user_type == "tutor" and tutor.id != user.tutor_id):
        raise HTTPException(status_code=403, detail="Not authorized to view this student's report")

    # Fetch all related data
    attendance_records = session.exec(
        select(Attendance)
        .where(Attendance.student_id == student_id)
        .order_by(Attendance.attendance_date.desc())
    ).all()

    journal_entries = session.exec(
        select(Journal)
        .where(Journal.student_id == student_id)
        .order_by(Journal.entry_date.desc())
    ).all()

    test_records = session.exec(
        select(TestRecord)
        .where(TestRecord.student_id == student_id)
        .order_by(TestRecord.test_date.desc())
    ).all()

    upcoming_tests = session.exec(
        select(UpcomingTest)
        .where(UpcomingTest.student_id == student_id)
        .where(UpcomingTest.test_date >= date.today())
        .order_by(UpcomingTest.test_date.asc())
    ).all()

    # Temporary placeholder for AI Feedback
    ai_feedback_data = "AI Feedback not yet implemented."

    return templates.TemplateResponse(
        "student_report.html",
        {
            "request": request,
            "student": student,
            "attendance_records": attendance_records,
            "journal_entries": journal_entries,
            "test_records": test_records,
            "upcoming_tests": upcoming_tests,
            "ai_feedback": ai_feedback_data
        }
    )

# ---------------- Download Reports ----------------
from fastapi.responses import StreamingResponse
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER
from fastapi import Request, Depends, HTTPException
from sqlmodel import Session, select
from models import Student, Tutor, TestRecord  # Make sure these are imported


@app.get("/reports/student/{student_id}/download")
def download_student_report(
        student_id: int,
        request: Request,
        format: str = "pdf",
        session: Session = Depends(get_session),
        user: User = Depends(get_current_user)
):
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    tutor = session.get(Tutor, student.tutor_id)
    if not tutor or (user.user_type == "tutor" and tutor.id != user.tutor_id):
        raise HTTPException(status_code=403, detail="Not authorized to download this student's report")

    test_records = session.exec(
        select(TestRecord)
        .where(TestRecord.student_id == student_id)
        .order_by(TestRecord.test_date.desc())
    ).all()

    if format.lower() == "pdf":
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        title_style = ParagraphStyle('Title', parent=styles['Normal'])
        title_style.fontSize = 18
        title_style.fontName = 'Helvetica-Bold'
        title_style.alignment = TA_CENTER

        # Add title and student details
        story.append(Paragraph(f"{student.name}'s Academic Report", title_style))
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph(f"<b>Grade:</b> {student.grade}", styles['Normal']))
        story.append(Paragraph(f"<b>School:</b> {student.school}", styles['Normal']))
        story.append(Paragraph(f"<b>Syllabus:</b> {student.syllabus if student.syllabus else 'N/A'}", styles['Normal']))
        story.append(Paragraph(f"<b>Remarks:</b> {student.remarks}", styles['Normal']))
        story.append(Spacer(1, 0.5 * inch))

        # Add Test Records section
        story.append(Paragraph("Test Records", styles['h2']))
        story.append(Spacer(1, 0.2 * inch))

        # Prepare data for the table with added safety checks
        data = [['Date', 'Subject', 'Topic', 'Score']]
        if test_records:
            for test in test_records:
                # Add checks for each field to prevent AttributeErrors
                test_date = test.test_date.strftime('%Y-%m-%d') if test.test_date else 'N/A'
                subject = test.subject if test.subject else 'N/A'
                topic = test.topic if test.topic else 'N/A'

                # Handle potential None values for marks
                marks_attained = test.marks_attained if test.marks_attained is not None else 'N/A'
                total_marks = test.total_marks if test.total_marks is not None else 'N/A'
                score = f"{marks_attained}/{total_marks}"

                data.append([test_date, subject, topic, score])
        else:
            data.append(['N/A', 'N/A', 'No test records found', 'N/A'])

        # Create and style the table
        table = Table(data, colWidths=[1.5 * inch, 1.5 * inch, 2.0 * inch, 1.0 * inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4A90E2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F5F7FA')),
        ]))
        story.append(table)

        # Build the document
        doc.build(story)

        # Move the buffer's cursor to the beginning
        buffer.seek(0)

        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=report_{student.name.replace(' ', '_')}.pdf"}
        )

    elif format.lower() == "googlesheets":
        return {"message": "Google Sheets integration requires API setup and is not yet implemented."}

    raise HTTPException(status_code=400, detail="Invalid format specified. Must be 'pdf' or 'googlesheets'")


@app.get("/reports/all/download")
def download_all_reports(
        request: Request,
        format: str = "pdf",
        session: Session = Depends(get_session),
        user: User = Depends(get_current_user)
):
    if user.user_type != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    if format.lower() == "pdf":
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph("All Students' Test Reports", styles['Title']))
        story.append(Spacer(1, 0.5 * inch))

        students = session.exec(select(Student)).all()

        for student in students:
            test_records = session.exec(
                select(TestRecord)
                .where(TestRecord.student_id == student.id)
                .order_by(TestRecord.test_date.desc())
            ).all()

            if test_records:
                story.append(Paragraph(f"Report for {student.name}", styles['h2']))
                story.append(Spacer(1, 0.2 * inch))

                data = [['Date', 'Subject', 'Topic', 'Score']]
                for test in test_records:
                    data.append([
                        test.test_date.strftime('%Y-%m-%d'),
                        test.subject,
                        test.topic,
                        f"{test.marks_attained}/{test.total_marks}"
                    ])

                table = Table(data, colWidths=[1.5 * inch, 1.5 * inch, 2.0 * inch, 1.0 * inch])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4A90E2')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('BOX', (0, 0), (-1, -1), 1, colors.black),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F5F7FA')),
                ]))
                story.append(table)
                story.append(Spacer(1, 0.5 * inch))

        doc.build(story)
        buffer.seek(0)

        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=all_student_reports.pdf"}
        )

    return {"message": "Download for all reports not yet implemented."}


# ---------------- Student Report ----------------
@app.get("/reports/student/{student_id}", response_class=HTMLResponse)
def get_student_report(
        student_id: int,
        request: Request,
        session: Session = Depends(get_session),
        user: User = Depends(get_current_user)
):
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    tutor = session.get(Tutor, student.tutor_id)
    if not tutor or (user.user_type == "tutor" and tutor.id != user.tutor_id):
        raise HTTPException(status_code=403, detail="Not authorized to view this student's report")

    # Fetch all related data
    attendance_records = session.exec(
        select(Attendance)
        .where(Attendance.student_id == student_id)
        .order_by(Attendance.attendance_date.desc())
    ).all()

    journal_entries = session.exec(
        select(Journal)
        .where(Journal.student_id == student_id)
        .order_by(Journal.entry_date.desc())
    ).all()

    test_records = session.exec(
        select(TestRecord)
        .where(TestRecord.student_id == student_id)
        .order_by(TestRecord.test_date.desc())
    ).all()

    upcoming_tests = session.exec(
        select(UpcomingTest)
        .where(UpcomingTest.student_id == student_id)
        .where(UpcomingTest.test_date >= date.today())
        .order_by(UpcomingTest.test_date.asc())
    ).all()

    # Fetch AI Feedback
    feedback_router = app.router.routes[1].app.routes[1]  # A bit of a hack to get the feedback router
    ai_feedback_data = ""
    try:
        feedback_response = feedback_router.get_ai_feedback(student_id, "overall", session)
        ai_feedback_data = feedback_response.get("ai_feedback", "No AI feedback available.")
    except Exception as e:
        ai_feedback_data = f"Failed to fetch AI feedback: {str(e)}"

    return templates.TemplateResponse(
        "student_report.html",
        {
            "request": request,
            "student": student,
            "attendance_records": attendance_records,
            "journal_entries": journal_entries,
            "test_records": test_records,
            "upcoming_tests": upcoming_tests,
            "ai_feedback": ai_feedback_data
        }
    )


# ---------- Edit Tutor ----------
@app.get("/tutor/{tutor_id}/edit", response_class=HTMLResponse)
def edit_tutor_form(tutor_id: int, request: Request, session: Session = Depends(get_session),
                    user: User = Depends(get_current_user)):
    if user.user_type != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    tutor = session.get(Tutor, tutor_id)
    if not tutor:
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse("edit_tutor.html", {"request": request, "tutor": tutor})


@app.post("/tutor/{tutor_id}/edit")
def edit_tutor(tutor_id: int, name: str = Form(...), subject: str = Form(...), phone: str = Form(...),
               session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    if user.user_type != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    tutor = session.get(Tutor, tutor_id)
    if tutor:
        tutor.name = name
        tutor.subject = subject
        tutor.phone = phone
        session.add(tutor)
        session.commit()
    return RedirectResponse("/admin-dashboard", status_code=303)


# ---------- Delete Tutor ----------
@app.post("/tutor/{tutor_id}/delete")
def delete_tutor(tutor_id: int, request: Request, session: Session = Depends(get_session),
                 user: User = Depends(get_current_user)):
    if user.user_type != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    tutor = session.get(Tutor, tutor_id)
    if not tutor:
        raise HTTPException(status_code=404, detail="Tutor not found")

    tutor_user = session.exec(select(User).where(User.tutor_id == tutor_id)).first()
    if tutor_user:
        session.delete(tutor_user)

    students = session.exec(select(Student).where(Student.tutor_id == tutor_id)).all()
    for student in students:
        session.delete(student)

    session.delete(tutor)
    session.commit()
    return RedirectResponse("/admin-dashboard", status_code=303)


# ---------- Edit Student ----------
@app.get("/student/{student_id}/edit", response_class=HTMLResponse)
def edit_student_form(student_id: int, request: Request, session: Session = Depends(get_session),
                      user: User = Depends(get_current_user)):
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    tutor = session.get(Tutor, student.tutor_id)
    if not tutor or (user.user_type == "tutor" and tutor.id != user.tutor_id):
        raise HTTPException(status_code=403, detail="Not authorized")

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
                 session: Session = Depends(get_session),
                 user: User = Depends(get_current_user)):
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    tutor = session.get(Tutor, student.tutor_id)
    if not tutor or (user.user_type == "tutor" and tutor.id != user.tutor_id):
        raise HTTPException(status_code=403, detail="Not authorized")

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


# --- Student delete route ---
@app.post("/student/{student_id}/delete")
def delete_student(
        student_id: int,
        request: Request,
        session: Session = Depends(get_session),
        user: User = Depends(get_current_user)
):
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    tutor = session.get(Tutor, student.tutor_id)
    if not tutor or (user.user_type == "tutor" and tutor.id != user.tutor_id):
        raise HTTPException(status_code=403, detail="Not authorized")

    # delete related rows (attendance, journals, tests)
    for rec in session.exec(select(Attendance).where(Attendance.student_id == student_id)).all():
        session.delete(rec)

    for j in session.exec(select(Journal).where(Journal.student_id == student_id)).all():
        session.delete(j)

    for t in session.exec(select(TestRecord).where(TestRecord.student_id == student_id)).all():
        session.delete(t)

    for ut in session.exec(select(UpcomingTest).where(UpcomingTest.student_id == student_id)).all():
        session.delete(ut)

    session.delete(student)
    session.commit()

    return RedirectResponse(f"/tutor/{tutor.id}/students", status_code=303)


# ---------------- Journal ----------------
@app.get("/student/{student_id}/journal", response_class=HTMLResponse)
def view_journal(student_id: int, request: Request, session: Session = Depends(get_session),
                 user: User = Depends(get_current_user)):
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    tutor = session.get(Tutor, student.tutor_id)
    if not tutor or (user.user_type == "tutor" and tutor.id != user.tutor_id):
        raise HTTPException(status_code=403, detail="Not authorized")

    journals = session.exec(
        select(Journal).where(Journal.student_id == student_id).order_by(Journal.entry_date.desc())
    ).all()

    return templates.TemplateResponse("journal.html", {
        "request": request,
        "student": student,
        "journals": journals
    })


@app.get("/student/{student_id}/journal/add", response_class=HTMLResponse)
def add_journal_form(student_id: int, request: Request, session: Session = Depends(get_session),
                     user: User = Depends(get_current_user)):
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    tutor = session.get(Tutor, student.tutor_id)
    if not tutor or (user.user_type == "tutor" and tutor.id != user.tutor_id):
        raise HTTPException(status_code=403, detail="Not authorized")

    return templates.TemplateResponse(
        "journal_add.html",
        {"request": request, "student": student, "today": date.today().isoformat()}
    )


@app.post("/student/{student_id}/journal/add")
def add_journal(student_id: int,
                tutor_name: str = Form(...),
                subject: str = Form(...),
                journal: str = Form(...),
                remarks: str = Form(...),
                entry_date: str = Form(...),
                session: Session = Depends(get_session),
                user: User = Depends(get_current_user)):
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    tutor = session.get(Tutor, student.tutor_id)
    if not tutor or (user.user_type == "tutor" and tutor.id != user.tutor_id):
        raise HTTPException(status_code=403, detail="Not authorized")

    try:
        parsed_date = datetime.strptime(entry_date, "%Y-%m-%d").date()
    except Exception:
        parsed_date = date.today()

    journal_entry = Journal(
        student_id=student_id,
        tutor_name=tutor_name,
        subject=subject,
        journal=journal,
        remarks=remarks,
        entry_date=parsed_date
    )
    session.add(journal_entry)
    session.commit()
    return RedirectResponse(f"/student/{student_id}/journal", status_code=303)


# ---------------- Attendance ----------------
@app.get("/student/{student_id}/attendance-view", response_class=HTMLResponse)
def view_attendance(
        request: Request,
        student_id: int,
        month: int = Query(None),
        year: int = Query(None),
        session: Session = Depends(get_session),
        user: User = Depends(get_current_user)
):
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    tutor = session.get(Tutor, student.tutor_id)
    if not tutor or (user.user_type == "tutor" and tutor.id != user.tutor_id):
        raise HTTPException(status_code=403, detail="Not authorized")

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
        session: Session = Depends(get_session),
        user: User = Depends(get_current_user)
):
    today = date.today()

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

    if user.user_type == "admin":
        tutors = session.exec(select(Tutor).where(Tutor.user_id == user.id)).all()
        tutor_ids = [t.id for t in tutors]
    else:
        tutors = session.exec(select(Tutor).where(Tutor.id == user.tutor_id)).all()
        tutor_ids = [user.tutor_id]

    students = session.exec(select(Student).where(Student.tutor_id.in_(tutor_ids))).all()

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

    import calendar
    num_days = calendar.monthrange(year, month)[1]

    filtered_records = session.exec(
        select(Attendance)
        .where(Attendance.student_id.in_([s.id for s in students]))
        .where(Attendance.attendance_date >= date(year, month, 1))
        .where(Attendance.attendance_date <= date(year, month, num_days))
    ).all()

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
def update_attendance(data: dict = Body(...), session: Session = Depends(get_session),
                      user: User = Depends(get_current_user)):
    from datetime import datetime

    student_id = int(data.get("student_id"))
    date_str = data.get("date")
    status = data.get("status")

    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    tutor = session.get(Tutor, student.tutor_id)
    if not tutor or (user.user_type == "tutor" and tutor.id != user.tutor_id):
        raise HTTPException(status_code=403, detail="Not authorized")

    try:
        attendance_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        existing = session.exec(
            select(Attendance)
            .where(Attendance.student_id == student_id)
            .where(Attendance.attendance_date == attendance_date)
        ).first()

        if existing:
            existing.status = status
            session.add(existing)
        else:
            new_attendance = Attendance(
                student_id=student_id,
                attendance_date=attendance_date,
                status=status
            )
            session.add(new_attendance)

        session.commit()
        return {"success": True}

    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/attendance-today", response_class=HTMLResponse)
def attendance_today_filtered(request: Request, session: Session = Depends(get_session),
                              user: User = Depends(get_current_user)):
    today = date.today()

    if user.user_type == "admin":
        students = session.exec(
            select(Student)
            .where(Student.tutor_id.in_(
                select(Tutor.id).where(Tutor.user_id == user.id)
            ))
        ).all()
    else:
        students = session.exec(
            select(Student)
            .where(Student.tutor_id == user.tutor_id)
        ).all()

    student_ids = [s.id for s in students]

    records = session.exec(
        select(Attendance).where(Attendance.attendance_date == today).where(Attendance.student_id.in_(student_ids))
    ).all()

    return templates.TemplateResponse("attendance_today_filtered.html", {
        "request": request,
        "records": records,
        "today": today.strftime("%d-%m-%Y")
    })


# ---------- Add Test Record Route ----------
@app.post("/student/{student_id}/tests/add")
def add_test(
        request: Request,
        student_id: int,
        subject: str = Form(...),
        topic: str = Form(...),
        test_date: str = Form(...),
        total_marks: int = Form(...),
        marks_attained: int = Form(...),
        remarks: str = Form(...),
        session: Session = Depends(get_session),
        user: User = Depends(get_current_user)
):
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    tutor = session.get(Tutor, student.tutor_id)
    if not tutor or (user.user_type == "tutor" and tutor.id != user.tutor_id):
        raise HTTPException(status_code=403, detail="Not authorized to add tests for this student")

    parsed_date = datetime.strptime(test_date, "%Y-%m-%d").date()

    new_test = TestRecord(
        student_id=student_id,
        subject=subject,
        topic=topic,
        test_date=parsed_date,
        total_marks=total_marks,
        marks_attained=marks_attained,
        remarks=remarks
    )
    session.add(new_test)
    session.commit()

    return RedirectResponse(url=f"/student/{student_id}/tests", status_code=303)


# ---------- View Tests Route ----------
@app.get("/student/{student_id}/tests", response_class=HTMLResponse)
def view_tests(
        request: Request,
        student_id: int,
        session: Session = Depends(get_session),
        user: User = Depends(get_current_user)
):
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    tutor = session.get(Tutor, student.tutor_id)
    if not tutor or (user.user_type == "tutor" and tutor.id != user.tutor_id):
        raise HTTPException(status_code=403, detail="Not authorized to view this student's tests")

    tests = session.exec(
        select(TestRecord)
        .where(TestRecord.student_id == student_id)
        .order_by(TestRecord.test_date.desc())
    ).all()

    return templates.TemplateResponse("view_tests.html", {
        "request": request,
        "student": student,
        "tests": tests
    })


# ---------------- Upcoming Tests ----------------
@app.get("/upcoming-tests", response_class=HTMLResponse)
def list_upcoming_tests(
        request: Request,
        session: Session = Depends(get_session),
        user: User = Depends(get_current_user)
):
    if user.user_type == "admin":
        tutors = session.exec(select(Tutor).where(Tutor.user_id == user.id)).all()
        tutor_ids = [t.id for t in tutors]
    else:
        tutor_ids = [user.tutor_id]

    students = session.exec(
        select(Student).where(Student.tutor_id.in_(tutor_ids))
    ).all()
    student_ids = [s.id for s in students]

    upcoming_tests = session.exec(
        select(UpcomingTest, Student)
        .join(Student)
        .where(UpcomingTest.student_id.in_(student_ids))
        .order_by(UpcomingTest.test_date.asc())
    ).all()

    return templates.TemplateResponse(
        "upcoming_tests.html",
        {
            "request": request,
            "upcoming_tests": upcoming_tests
        }
    )


@app.get("/upcoming-tests/add", response_class=HTMLResponse)
def add_upcoming_test_form(
        request: Request,
        session: Session = Depends(get_session),
        user: User = Depends(get_current_user)
):
    if user.user_type == "admin":
        tutors = session.exec(select(Tutor).where(Tutor.user_id == user.id)).all()
    else:
        tutors = session.exec(select(Tutor).where(Tutor.id == user.tutor_id)).all()

    students = session.exec(
        select(Student).where(Student.tutor_id.in_([t.id for t in tutors]))
    ).all()

    return templates.TemplateResponse("upcoming_test_add.html", {
        "request": request,
        "students": students,
        "today": date.today().isoformat()
    })


@app.post("/upcoming-tests/add")
def add_upcoming_test(
        request: Request,
        student_id: int = Form(...),
        subject: str = Form(...),
        topics: str = Form(...),
        test_date: str = Form(...),
        session: Session = Depends(get_session),
        user: User = Depends(get_current_user)
):
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    tutor = session.get(Tutor, student.tutor_id)
    if not tutor or (user.user_type == "tutor" and tutor.id != user.tutor_id):
        raise HTTPException(status_code=403, detail="Not authorized")

    parsed_date = datetime.strptime(test_date, "%Y-%m-%d").date()

    new_test = UpcomingTest(
        student_id=student_id,
        subject=subject,
        topics=topics,
        test_date=parsed_date
    )
    session.add(new_test)
    session.commit()

    return RedirectResponse(url="/upcoming-tests", status_code=303)


# ---------------- Student Insights ----------------
@app.get("/student/{student_id}/insights", response_class=HTMLResponse)
def student_insights(student_id: int, request: Request, session: Session = Depends(get_session),
                     user: User = Depends(get_current_user)):
    print(f"Attempting to fetch insights for student_id: {student_id}")
    student = session.get(Student, student_id)
    if not student:
        print(f"Error: Student with ID {student_id} not found.")
        raise HTTPException(status_code=404, detail="Student not found")

    tutor = session.get(Tutor, student.tutor_id)
    if not tutor or (user.user_type == "tutor" and tutor.id != user.tutor_id and not user.user_type == "admin"):
        print(f"Error: User {user.username} is not authorized to view insights for student ID {student_id}")
        raise HTTPException(status_code=403, detail="Not authorized")

    # Fetch all relevant data for the insights page
    journals = session.exec(
        select(Journal).where(Journal.student_id == student_id).order_by(Journal.entry_date.desc())
    ).all()

    tests = session.exec(
        select(TestRecord).where(TestRecord.student_id == student_id).order_by(TestRecord.test_date.desc())
    ).all()

    # Calculate attendance counts for the summary
    total_days = session.exec(
        select(func.count(Attendance.id)).where(Attendance.student_id == student_id)
    ).first() or 0
    present_days = session.exec(
        select(func.count(Attendance.id)).where(Attendance.student_id == student_id,
                                                func.lower(Attendance.status) == "present")
    ).first() or 0
    absent_days = session.exec(
        select(func.count(Attendance.id)).where(Attendance.student_id == student_id,
                                                func.lower(Attendance.status) == "absent")
    ).first() or 0

    attendance_counts = {
        "total": total_days,
        "present": present_days,
        "absent": absent_days,
    }

    return templates.TemplateResponse(
        "insights.html",
        {
            "request": request,
            "student": student,
            "journals": journals,  # Added this
            "tests": tests,  # Added this
            "attendance_counts": attendance_counts
        }
    )


# ---------------- Startup ----------------
@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)
