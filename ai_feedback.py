from __future__ import annotations
import os
import json
import requests
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select
from starlette.templating import Jinja2Templates
from collections import defaultdict
from models import Student, Journal, Attendance, TestRecord, Feedback
from db import get_session

router = APIRouter(prefix="/insights", tags=["Insights"])

# -------- Templates wiring (set from main.py) --------
_templates: Jinja2Templates | None = None


def init_templates(templates: Jinja2Templates) -> None:
    global _templates
    _templates = templates


# Gemini API setup (using direct HTTP requests)
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"


# ---------------- Context ----------------
def get_start_end_dates(period: str) -> tuple[date, date]:
    """
    Calculates the start and end dates based on a given period.
    """
    today = date.today()
    if period == "weekly":
        # Start of the week (Monday)
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
    elif period == "last-30-days":
        end_date = today
        start_date = today - timedelta(days=30)
    elif period == "last-6-months":
        end_date = today
        start_date = today - timedelta(days=6 * 30)  # Approx 6 months
    else:
        raise HTTPException(status_code=400, detail="Invalid period specified.")
    return start_date, end_date


def collect_student_context(session: Session, student_id: int, start_date: date, end_date: date):
    """
    Collects student's academic data within a given date range.
    """
    journals = session.exec(
        select(Journal).where(
            Journal.student_id == student_id,
            Journal.entry_date >= start_date,
            Journal.entry_date <= end_date
        )
    ).all()

    tests = session.exec(
        select(TestRecord).where(
            TestRecord.student_id == student_id,
            TestRecord.test_date >= start_date,
            TestRecord.test_date <= end_date
        )
    ).all()

    attendance = session.exec(
        select(Attendance).where(
            Attendance.student_id == student_id,
            Attendance.attendance_date >= start_date,
            Attendance.attendance_date <= end_date
        )
    ).all()

    context = {
        "journals": journals,
        "tests": tests,
        "attendance": attendance
    }
    return context


def format_data_for_ai(context: dict) -> str:
    """
    Formats the collected data into a structured string for the AI model.
    """
    prompt_parts = []

    if context["journals"]:
        prompt_parts.append("Journal Entries:")
        for j in context["journals"]:
            prompt_parts.append(
                f"- Date: {j.entry_date}, Subject: {j.subject}, Journal: {j.journal}, Remarks: {j.remarks}"
            )
        prompt_parts.append("\n")

    if context["tests"]:
        prompt_parts.append("Test Records:")
        for t in context["tests"]:
            prompt_parts.append(
                f"- Date: {t.test_date}, Subject: {t.subject}, Topic: {t.topic}, Marks: {t.marks_attained}/{t.total_marks}, Remarks: {t.remarks}"
            )
        prompt_parts.append("\n")

    if context["attendance"]:
        prompt_parts.append("Attendance Records:")
        attendance_summary = defaultdict(int)
        for a in context["attendance"]:
            attendance_summary[a.status.lower()] += 1

        prompt_parts.append(f"  - Total Present: {attendance_summary['present']}")
        prompt_parts.append(f"  - Total Absent: {attendance_summary['absent']}")
        prompt_parts.append(f"  - Total Late: {attendance_summary['late']}")
        prompt_parts.append("\n")

    return "\n".join(prompt_parts)


def call_gemini_api(summary_for_ai: str):
    """
    Calls the Gemini API to get feedback based on the provided data.
    """
    if not GEMINI_API_KEY:
        return {"error": "API key not set."}

    prompt = f"""
    Based on the following student data, generate a detailed academic insight report. 
    The report should be a single JSON object with the following keys:
    1.  'overall_summary': A brief paragraph summarizing the student's overall performance.
    2.  For each subject mentioned, create a separate key (e.g., 'Mathematics', 'Science'). Each subject key should contain:
        - 'strengths': A list of key strengths.
        - 'weaknesses': A list of key weaknesses or areas for improvement.
        - 'suggestions': A list of actionable suggestions for improvement.

    Here is the student data:
    {summary_for_ai}
    """

    headers = {
        "Content-Type": "application/json"
    }

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }

    try:
        response = requests.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            headers=headers,
            json=payload
        )
        response.raise_for_status()

        feedback_data = response.json()

        # Extract the JSON string from the response
        generated_json_string = feedback_data["candidates"][0]["content"]["parts"][0]["text"]

        # Parse the string into a Python object
        parsed_data = json.loads(generated_json_string)
        return parsed_data

    except requests.exceptions.HTTPError as err:
        return {"error": f"HTTP Error: {err}"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request Error: {e}"}
    except (json.JSONDecodeError, KeyError) as e:
        return {"error": f"Failed to parse AI response: {e}"}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}


# ---------------- Endpoints ----------------
@router.get("/{student_id}", response_class=HTMLResponse)
def get_insights_page(request: Request, student_id: int, session: Session = Depends(get_session)):
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    return _templates.TemplateResponse(
        "insights.html",
        {"request": request, "student": student}
    )


@router.get("/student/{student_id}/{period}/data")
def get_student_data(student_id: int, period: str, session: Session = Depends(get_session)):
    try:
        start_date, end_date = get_start_end_dates(period)
    except HTTPException as e:
        return {"error": e.detail}

    context = collect_student_context(session, student_id, start_date, end_date)

    test_data = [
        {"subject": t.subject, "date": t.test_date.isoformat(), "marks_attained": t.marks_attained,
         "total_marks": t.total_marks}
        for t in context["tests"]
    ]

    attendance_counts = defaultdict(int)
    for a in context["attendance"]:
        attendance_counts[a.status.lower()] += 1

    return {
        "tests": test_data,
        "attendance": dict(attendance_counts)
    }


@router.post("/student/{student_id}/{period}/ai")
def get_insights_ai(student_id: int, period: str, session: Session = Depends(get_session)):
    try:
        start_date, end_date = get_start_end_dates(period)
    except HTTPException as e:
        return {"ai_feedback": e.detail}

    # Check for existing feedback
    existing_feedback = session.exec(
        select(Feedback).where(
            Feedback.student_id == student_id,
            Feedback.period == period,
            Feedback.start_date == start_date,
            Feedback.end_date == end_date
        )
    ).first()

    if existing_feedback:
        return {"ai_feedback": existing_feedback.feedback_text}

    # If no existing feedback, generate new
    context = collect_student_context(session, student_id, start_date, end_date)
    if not context or (not context["journals"] and not context["tests"] and not context["attendance"]):
        return {"ai_feedback": "No data available for this period."}

    summary_for_ai = format_data_for_ai(context)

    feedback_data = call_gemini_api(summary_for_ai)

    if "error" in feedback_data:
        return {"ai_feedback": feedback_data["error"]}

    feedback_json_text = json.dumps(feedback_data)

    new_feedback = Feedback(
        student_id=student_id,
        period=period,
        start_date=start_date,
        end_date=end_date,
        feedback_text=feedback_json_text
    )

    session.add(new_feedback)
    session.commit()
    session.refresh(new_feedback)

    return {"ai_feedback": new_feedback.feedback_text}


@router.post("/student/{student_id}/{period}/ai/refresh")
def refresh_insights_ai(student_id: int, period: str, session: Session = Depends(get_session)):
    try:
        start_date, end_date = get_start_end_dates(period)
    except HTTPException as e:
        return {"ai_feedback": e.detail}

    # Delete existing feedback to force a refresh
    existing_feedback = session.exec(
        select(Feedback).where(
            Feedback.student_id == student_id,
            Feedback.period == period,
            Feedback.start_date == start_date,
            Feedback.end_date == end_date
        )
    ).first()

    if existing_feedback:
        session.delete(existing_feedback)
        session.commit()

    # Generate new feedback and save it
    context = collect_student_context(session, student_id, start_date, end_date)
    if not context or (not context["journals"] and not context["tests"] and not context["attendance"]):
        return {"ai_feedback": "No data available for this period."}

    summary_for_ai = format_data_for_ai(context)

    feedback_data = call_gemini_api(summary_for_ai)

    if "error" in feedback_data:
        return {"ai_feedback": feedback_data["error"]}

    feedback_json_text = json.dumps(feedback_data)

    new_feedback = Feedback(
        student_id=student_id,
        period=period,
        start_date=start_date,
        end_date=end_date,
        feedback_text=feedback_json_text
    )

    session.add(new_feedback)
    session.commit()
    session.refresh(new_feedback)

    return {"ai_feedback": new_feedback.feedback_text}