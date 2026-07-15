import streamlit as st
import os
import base64
import json
import random
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Table, TableStyle
from datetime import datetime
from backend.models import Subject
from backend.database import get_session
from backend.database import get_session
from backend.models import StudentProgress
from sqlalchemy.orm import Session

# -----------------------------
# Cached function to read & encode image
# -----------------------------
@st.cache_data(ttl=600)
def get_base64_image(file_path: str) -> str:
    """Read a local image file and return base64-encoded string."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Background file not found: {file_path}")
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode()





# =====================================================
#
# =====================================================
def set_background(
    file_path: str = None,
    color: str = "#7abaa1",
    force_reload: bool = False
):
    """
    Sets Streamlit background image for app + sidebar.
    Mobile-safe version.
    """

    base64_image = None

    if file_path and os.path.exists(file_path):

        if force_reload:
            try:
                st.cache_data.clear()
            except:
                pass

        try:
            base64_image = get_base64_image(file_path)

        except Exception as e:

            st.warning(
                f"⚠️ Failed loading background: {e}"
            )

            base64_image = None

    else:
        base64_image = None


    # ==================================================
    # IMAGE BACKGROUND
    # ==================================================
    if base64_image:

        st.markdown(
            f"""
            <style>

            html, body {{
                background-color:#7abaa1 !important;
                margin:0;
                padding:0;
            }}

            /* Force all Streamlit containers */
            .stApp,
            [data-testid="stAppViewContainer"],
            .main,
            section.main {{
                background-image:
                    linear-gradient(
                        rgba(255,255,255,.10),
                        rgba(255,255,255,.10)
                    ),
                    url("data:image/png;base64,{base64_image}");

                background-size:cover !important;
                background-position:center !important;
                background-repeat:no-repeat !important;

                /* mobile browsers hate fixed */
                background-attachment:scroll !important;

                min-height:100vh !important;
            }}

            /* Remove hidden theme layers */
            [data-testid="stHeader"] {{
                background:transparent !important;
            }}

            [data-testid="stToolbar"] {{
                background:transparent !important;
            }}

            .block-container {{
                background:transparent !important;
            }}

            /* Sidebar */
            section[data-testid="stSidebar"] > div:first-child {{

                background-image:
                    linear-gradient(
                        rgba(255,255,255,.88),
                        rgba(255,255,255,.92)
                    ),
                    url("data:image/png;base64,{base64_image}");

                background-size:cover !important;
                background-position:center !important;
                background-repeat:no-repeat !important;

                background-attachment:scroll !important;

                color:#0f3c2e !important;
            }}

            @media(max-width:768px){{
                html, body,
                .stApp,
                [data-testid="stAppViewContainer"] {{

                    background-position:center top !important;
                    background-size:cover !important;
                }}
            }}

            </style>
            """,
            unsafe_allow_html=True
        )

    # ==================================================
    # FALLBACK
    # ==================================================
    else:

        st.markdown(
            f"""
            <style>

            .stApp {{

                background:
                linear-gradient(
                    135deg,
                    {color},
                    #9ed3b8
                );

                color:#222 !important;

                min-height:100vh;
            }}

            section[data-testid="stSidebar"] {{

                background:
                linear-gradient(
                    135deg,
                    {color},
                    #94c7ad
                );

                color:white !important;

            }}

            </style>
            """,
            unsafe_allow_html=True
        )


# =====================================================
#
# =====================================================
def generate_pdf(
    name,
    class_name,
    subject,
    correct,
    total,
    percent,
    details,
    school_name=None,
    school_id=None,
    logo_path=None,
    test_type="objective"
):

    # =====================================================
    #
    # =====================================================
    from reportlab.platypus import (
        Table,
        TableStyle,
        Paragraph
    )

    from reportlab.lib.styles import (
        getSampleStyleSheet
    )


    buffer = BytesIO()

    c = canvas.Canvas(
        buffer,
        pagesize=letter
    )

    width, height = letter

    styles = getSampleStyleSheet()

    body = styles["BodyText"]

    body.fontName = "Helvetica"
    body.fontSize = 8
    body.leading = 10

    # =========================================
    # HEADER
    # =========================================

    y_top = height - 60
    center_x = width / 2

    logo_x = 60
    logo_y = y_top - 50

    if logo_path:

        try:

            logo = ImageReader(
                logo_path
            )

            c.drawImage(
                logo,
                logo_x,
                logo_y,
                width=60,
                height=50,
                preserveAspectRatio=True,
                mask="auto"
            )

        except:

            c.setFont(
                "Helvetica-Oblique",
                9
            )

            c.drawString(
                logo_x,
                y_top-20,
                "[Logo]"
            )

    c.setFont(
        "Helvetica-Bold",
        15
    )

    c.drawCentredString(
        center_x,
        y_top,
        school_name or
        "SMART TEST SCHOOL"
    )

    c.setFont(
        "Helvetica-Bold",
        13
    )

    c.drawCentredString(
        center_x,
        y_top-20,
        "STUDENT TEST RESULT"
    )

    generated = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    c.setFont(
        "Helvetica",
        9
    )

    c.drawCentredString(
        center_x,
        y_top-38,
        f"School ID: {school_id or 'N/A'}     Generated: {generated}"
    )

    c.line(
        60,
        y_top-50,
        width-60,
        y_top-50
    )

    # =========================================
    # STUDENT INFO
    # =========================================

    y = y_top-85

    info = [

        f"Student Name: {name}",
        f"Class: {class_name or 'N/A'}",
        f"Subject: {subject}",
        f"Test Type: {test_type.title()}"

    ]

    if test_type=="objective":

        info.append(
            f"Score: {correct}/{total} ({percent:.2f}%)"
        )

    else:

        info.append(
            f"Status: Reviewed ✓"
        )


    c.setFont(
        "Helvetica",
        11
    )

    for line in info:

        c.drawString(
            70,
            y,
            line
        )

        y -=18

    y -=5

    c.line(
        60,
        y,
        width-60,
        y
    )

    y -=30

    c.setFont(
        "Helvetica-Bold",
        12
    )

    c.drawString(
        70,
        y,
        "Question Breakdown"
    )

    y-=20

    # =========================================
    # OBJECTIVE
    # =========================================

    if test_type == "objective":

        data = [[
            "#",
            "Question",
            "Your Answer",
            "Correct",
            "Result"
        ]]

        for i, d in enumerate(details, start=1):

            # -------------------------
            # Handle dict or raw text
            # -------------------------
            if isinstance(d, dict):

                question = (
                        d.get("question_text")
                        or d.get("question")
                        or f"Question {i}"
                )

                answer = (
                        d.get("selected")
                        or "—"
                )

                correct_answer = (
                        d.get("correct")
                        or d.get("correct_answer")
                        or "—"
                )

                is_correct = d.get(
                    "is_correct",
                    False
                )

            else:

                question = str(d)

                answer = "—"

                correct_answer = "—"

                is_correct = False

            # -------------------------
            # Shorten very long text
            # -------------------------
            question = (
                question[:100] + "..."
                if len(str(question)) > 100
                else str(question)
            )

            answer = (
                str(answer)[:80] + "..."
                if len(str(answer)) > 80
                else str(answer)
            )

            correct_answer = (
                str(correct_answer)[:80] + "..."
                if len(str(correct_answer)) > 80
                else str(correct_answer)
            )

            result = (
                "✔ Correct"
                if is_correct
                else "✘ Wrong"
            )

            data.append([

                str(i),

                Paragraph(
                    question,
                    body
                ),

                Paragraph(
                    answer,
                    body
                ),

                Paragraph(
                    correct_answer,
                    body
                ),

                Paragraph(
                    result,
                    body
                )

            ])

        table = Table(

            data,

            colWidths=[
                25,
                180,
                120,
                120,
                65
            ]

        )


    # =========================================
    # SUBJECTIVE
    # =========================================

    else:

        data = [[
            "#",
            "Question",
            "Student Answer",
            "Teacher Score"
        ]]

        for i, d in enumerate(details, start=1):

            if isinstance(d, dict):

                question = (
                        d.get("question")
                        or d.get("question_text")
                        or f"Question {i}"
                )

                answer = (
                        d.get("answer")
                        or d.get("selected")
                        or "No Answer"
                )

                score = (
                        d.get("teacher_score")
                        or d.get("score")
                        or "Pending"
                )

            else:

                question = str(d)
                answer = "No Answer"
                score = "Pending"

            # -------------------------
            # CLEAN BAD VALUES
            # -------------------------
            question = str(question).strip()
            answer = str(answer).strip()

            if question.lower() == "nan":
                question = "No Question"

            if answer.lower() == "nan":
                answer = "No Answer"

            # -------------------------
            # ADD ROW
            # -------------------------
            data.append([

                str(i),

                Paragraph(question, body),

                Paragraph(answer, body),

                Paragraph(str(score), body)

            ])

        table = Table(

            data,

            repeatRows=1,

            colWidths=[
                25,
                180,
                280,
                60
            ]

        )

    # =========================================
    # TABLE STYLE
    # =========================================

    table.setStyle(

        TableStyle([

            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),

            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),

            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),

            ('VALIGN', (0, 0), (-1, -1), 'TOP'),

            ('WORDWRAP', (0, 0), (-1, -1), True),

            ('LEFTPADDING', (0, 0), (-1, -1), 5),

            ('RIGHTPADDING', (0, 0), (-1, -1), 5),

            ('TOPPADDING', (0, 0), (-1, -1), 7),

            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),

            ('FONTSIZE', (0, 0), (-1, -1), 8)

        ])

    )

    table_width, table_height = table.wrap(
        width - 100,
        height
    )

    if y - table_height < 50:
        c.showPage()

        y = height - 80

    table.drawOn(
        c,
        50,
        y - table_height
    )

    # =========================================
    # FOOTER
    # =========================================

    c.setFont(
        "Helvetica-Oblique",
        9
    )

    c.drawCentredString(
        width/2,
        30,
        "Generated by Smart Test App © 2026"
    )

    c.showPage()

    c.save()

    buffer.seek(0)

    return buffer.getvalue()




# =====================================================
#
# =====================================================
from backend.models import Class
def load_classes(school_id: int, db=None):
    """
    Return a list of Class ORM objects for a given school.
    """
    if not school_id:
        return []

    close_db = False
    if db is None:
        db = get_session()
        close_db = True

    try:
        return (
            db.query(Class)
            .filter(Class.school_id == school_id)
            .order_by(Class.name.asc())
            .all()
        )
    finally:
        if close_db:
            db.close()


def style_admin_headers():
    st.markdown("""
        <style>
        /* Underline all h1/h2 headers in admin dashboard */
        .stApp h1, .stApp h2, .stApp h3 {
            text-decoration: underline;
            text-decoration-color: #ff7e5a;  /* You can change this color */
            text-underline-offset: 6px;       /* space between text and underline */
            text-decoration-thickness: 2px;   /* thickness of the underline */
        }
        </style>
    """, unsafe_allow_html=True)





def get_saved_progress(access_code: str, subject: str, school_id: int, test_type: str = "objective") -> dict:
    """
    Returns saved progress for a student based on their access code, subject, school, and test type.
    """
    db: Session = get_session()
    try:
        progress = (
            db.query(StudentProgress)
            .filter_by(
                access_code=access_code,
                subject=subject,
                school_id=school_id,
                test_type=test_type
            )
            .first()
        )
        if progress:
            return {
                "questions": progress.questions or [],
                "answers": progress.answers or [],
                "current_q": progress.current_q or 0,
                "submitted": progress.submitted or False,
                "start_time": progress.start_time,
                "duration": progress.duration,
            }
        return {}
    finally:
        db.close()






def parse_json_field(data):
    if not data:
        return []

    if isinstance(data, list):
        return data

    if isinstance(data, str):

        try:
            return json.loads(data)

        except:
            return []

    return []





import random

from datetime import datetime, timedelta

import streamlit as st

from backend.helpers import normalize_question, load_question_cache, render_test_type_selector
from backend.db_helpers import save_progress

def build_question_list(
    test_type,
    objective_questions,
    subjective_questions
):
    question_bank = (
        objective_questions
        if test_type == "objective"
        else subjective_questions
    ).copy()

    random.shuffle(question_bank)

    normalized_questions = [
        normalize_question(q)
        for q in question_bank
    ]

    return normalized_questions





def initialize_test_session(
    questions,
    duration_minutes
):
    st.session_state.questions = questions

    st.session_state.test_started = True

    st.session_state.current_q = 0

    st.session_state.start_time = datetime.now()

    st.session_state.duration = duration_minutes * 60

    st.session_state.test_end_time = (
        st.session_state.start_time +
        timedelta(seconds=st.session_state.duration)
    )

    st.session_state.marked_for_review = set()

    st.session_state.auto_submitted = False

    st.session_state.submitted = False

    st.session_state.locked = False






def save_initial_progress(
    access_code,
    subject_id,
    class_id,
    school_id,
    student_id,
    questions,
):
    save_progress(
        access_code=access_code,
        subject_id=subject_id,
        class_id=class_id,
        school_id=school_id,
        test_type=st.session_state.test_type,
        answers=st.session_state.answers,
        current_q=0,
        start_time=st.session_state.start_time,
        duration=st.session_state.duration,
        questions=[q["id"] for q in questions],
        student_id=student_id,
        submitted=False
    )




# =========================================================
# 🔄 RESET TEST STATE
# =========================================================
def reset_test_state():
    reset_keys = [
        "test_started",
        "submitted",
        "questions",
        "answers",
        "current_q",
        "current_page",
        "marked_for_review",
        "start_time",
        "test_end_time",
        "duration",
        "five_min_warned",
        "saved_to_db",
        "last_auto_save",
        "confirm_submit",
        "final_submit",
        "answered_count",
        "unanswered",
        "resumed",
        "test_action",
    ]

    for key in reset_keys:
        if key == "marked_for_review":
            st.session_state[key] = set()
        elif key == "questions":
            st.session_state[key] = []
        elif key == "answers":
            st.session_state[key] = {}
        else:
            st.session_state[key] = False


def initialize_student_session():
    defaults = {
        "test_started": False,
        "submitted": False,
        "logged_in": False,
        "student": {},
        "answers": {},
        "current_q": 0,
        "current_page": 0,
        "questions": [],
        "subject": None,
        "marked_for_review": set(),
        "duration": None,
        "start_time": None,
        "test_end_time": None,
        "five_min_warned": False,
        "saved_to_db": False,
        "last_auto_save": 0,
    }

    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

    st.session_state.setdefault("confirm_submit", False)
    st.session_state.setdefault("final_submit", False)
    st.session_state.setdefault("answered_count", 0)
    st.session_state.setdefault("unanswered", 0)

    st.session_state.setdefault("current_q", 0)
    st.session_state.setdefault("answers", {})
    st.session_state.setdefault("questions", [])

    st.session_state.setdefault("access_code", None)
    st.session_state.setdefault("student_id", None)
    st.session_state.setdefault("subject_id", None)
    st.session_state.setdefault("class_id", None)
    st.session_state.setdefault("school_id", None)





def render_student_header():

    st.markdown("""
    <div style="font-size:28px;font-weight:700;color:#1f2937;">
    🎓 Student Hub
    </div>
    <div style="
        width:180px;
        height:4px;
        background:#4CAF50;
        border-radius:4px;
        margin-top:4px;
        margin-bottom:20px;
    "></div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="
        position: sticky;
        top: 0;
        background-color: #fff8ee;
        color: #6b4f00;
        padding: 10px;
        font-weight: 600;
        text-align: center;
        z-index: 999;
        border-radius: 8px;
        border-left: 4px solid #d4a017;
        margin-bottom:15px;
    ">
    📌 Retakes are controlled by Admins. Submit your test before time runs out.
    </div>
    """, unsafe_allow_html=True)


def load_student_css():
    st.markdown("""
    <style>

    .small-input input,
    .small-input select{
        width:150px !important;
        padding:6px;
        font-size:14px;
    }

    div[data-baseweb="input"],
    div[data-baseweb="select"]{
        width:220px !important;
        margin-left:0 !important;
    }

    .card{
        padding:1rem;
        margin-top:.8rem;
        border-radius:10px;
        border:1px solid #ddd;
        background:#fafafa;
        box-shadow:1px 1px 4px rgba(0,0,0,.08);
    }

    </style>
    """, unsafe_allow_html=True)



def render_subject_selection(
    school_id_int,
    class_id_int,
    class_id,
):
    # =========================================================
    # 📚 SUBJECTS
    # =========================================================
    subjects = st.session_state.subjects

    if not subjects:
        st.info("🚫 No subjects available for your class. Contact admin.")
        st.stop()

    # =========================================================
    # 📘 SUBJECT SELECTION
    # =========================================================
    st.markdown("#### 📘 Select Subject")

    selected_subject = st.selectbox(
        "Subject",
        subjects,
        format_func=lambda s: s["name"],
        key="subject_select_box",
        disabled=st.session_state.get("test_started", False)
    )

    selected_subject_id = selected_subject.get("id")
    selected_subject_name = selected_subject.get("name")

    # Store selected subject
    st.session_state.subject_id = selected_subject_id

    # =========================================================
    # 🔄 SUBJECT SWITCH RESET
    # =========================================================
    if st.session_state.subject is None:
        st.session_state.subject = selected_subject_name

    elif st.session_state.subject != selected_subject_name:
        reset_test_state()
        st.session_state.subject = selected_subject_name
        st.rerun()

    if selected_subject_id is None:
        st.info(f"🚫 Subject ID not found for '{selected_subject_name}'")
        st.stop()

    # ---------------------------------------------------------
    # ❓ LOAD QUESTIONS (CACHED)
    # ---------------------------------------------------------
    objective_questions, subjective_questions = load_question_cache(
        selected_subject_id=selected_subject_id,
        class_id=class_id_int,
        school_id=school_id_int
    )

    # ---------------------------------------------------------
    # 🧩 TEST TYPE SELECTION
    # ---------------------------------------------------------
    selected_test_type = render_test_type_selector(
        class_id=class_id,
        subject_id=selected_subject_id
    )

    # ---------------------------------------------------------
    # KEEP EXISTING TEST TYPE DURING ACTIVE TEST
    # ---------------------------------------------------------
    if (
        st.session_state.get("test_started")
        and "test_type" in st.session_state
    ):
        test_type = st.session_state.test_type
    else:
        test_type = selected_test_type
        st.session_state.test_type = test_type

    # =========================================================
    # 🔄 TEST TYPE SWITCH RESET
    # =========================================================
    if "last_test_type" not in st.session_state:
        st.session_state.last_test_type = test_type

    elif st.session_state.last_test_type != test_type:
        reset_test_state()
        st.session_state.last_test_type = test_type
        st.rerun()

    return (
        selected_subject_id,
        selected_subject_name,
        objective_questions,
        subjective_questions,
        test_type,
    )