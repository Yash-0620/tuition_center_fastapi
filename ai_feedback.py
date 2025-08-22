from __future__ import annotations
import os, requests
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select
from starlette.templating import Jinja2Templates

from models import Student, Journal, Attendance, TestRecord
from db import get_session

router = APIRouter(prefix="/insights", tags=["Insights"])

# -------- Templates wiring (set from main.py) --------
_templates: Jinja2Templates | None = None
def init_templates(templates: Jinja2Templates) -> None:
    global _templates
    _templates = templates

# Hugging Face setup
HF_API_KEY = os.getenv("OPENAI_API_KEY")
HF_MODEL = "google/flan-t5-base"


# ---------------- Context ----------------
def collect_student_context(session: Session, student_id: int, start_date: date, end_date: date):
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

    return {"journals": journals, "tests": tests, "attendance": attendance}


# ---------------- Rule-Based Summary ----------------
def rule_based_summary(journals, tests, attendance):
    summary = []
    if not journals and not tests and not attendance:
        return "No activity recorded in this period."

    if journals:
        summary.append(f"📝 {len(journals)} journal entries recorded.")
        remarks = [j.remarks for j in journals if j.remarks]
        if remarks:
            summary.append("Remarks: " + "; ".join(remarks))

    if tests:
        scores = [t.marks_attained for t in tests if t.marks_attained is not None]
        if scores:
            avg = sum(scores) / len(scores)
            summary.append(f"📊 {len(scores)} tests taken, avg score {avg:.1f}/{tests[0].total_marks}.")

    if attendance:
        present_days = sum(1 for a in attendance if a.status.lower() == "present")
        summary.append(f"📅 Attendance: {present_days}/{len(attendance)} days present.")

    return " ".join(summary)


# ---------------- Hugging Face AI ----------------
def call_ai(context: dict) -> str:
    url = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}

    # Serialize context into readable format
    journals = "\n".join([f"- {j.entry_date}: {j.journal} (Remarks: {j.remarks or 'None'})" for j in context["journals"]])
    tests = "\n".join([f"- {t.test_date}: {t.marks_attained}/{t.total_marks}" for t in context["tests"]])
    attendance = "\n".join([f"- {a.attendance_date}: {a.status}" for a in context["attendance"]])

    prompt = f"""
Analyze the student's academic performance and provide a detailed evaluation.

📘 Journals & Tutor Notes:
{journals or 'No journals recorded'}

📊 Test Results:
{tests or 'No tests available'}

📅 Attendance:
{attendance or 'No attendance recorded'}

Return the analysis with these sections:
- Strengths
- Weaknesses
- Advice
- Overall Trend
"""

    payload = {"inputs": prompt}
    response = requests.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        return f"(HF Error {response.status_code}) {response.text}"

    result = response.json()
    print("🔍 HF Raw Response:", result)  # 👈 debug log

    # Extract text safely
    if isinstance(result, list) and "generated_text" in result[0]:
        return result[0]["generated_text"]
    if isinstance(result, list) and "summary_text" in result[0]:
        return result[0]["summary_text"]

    return "(AI feedback unavailable)"





# ---------------- Main Insights Page ----------------
@router.get("/student/{student_id}/{period}", response_class=HTMLResponse)
def insights_page(request: Request, student_id: int, period: str, session: Session = Depends(get_session)):
    today = date.today()
    if period == "daily":
        start_date, end_date = today, today
    elif period == "weekly":
        start_date, end_date = today - timedelta(days=7), today
    elif period == "monthly":
        start_date, end_date = today - timedelta(days=30), today
    else:
        start_date, end_date = today, today

    student = session.get(Student, student_id)
    context = collect_student_context(session, student_id, start_date, end_date)

    summary = rule_based_summary(context["journals"], context["tests"], context["attendance"])

    return _templates.TemplateResponse("insights.html", {
        "request": request,
        "student": student,
        "period": period,
        "rule_based_summary": summary,
        "ai_feedback": "Loading feedback..."
    })


# ---------------- Separate AI Endpoint ----------------
@router.get("/student/{student_id}/{period}/ai")
def insights_ai(student_id: int, period: str, session: Session = Depends(get_session)):
    today = date.today()
    if period == "daily":
        start_date, end_date = today, today
    elif period == "weekly":
        start_date, end_date = today - timedelta(days=7), today
    elif period == "monthly":
        start_date, end_date = today - timedelta(days=30), today
    else:
        return {"ai_feedback": "Invalid period"}

    context = collect_student_context(session, student_id, start_date, end_date)
    if not context:
        return {"ai_feedback": "No context available"}

    ai_text = call_ai(context)
    return {"ai_feedback": ai_text}
