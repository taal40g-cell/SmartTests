import streamlit as st
import os
import base64
import json
import pandas as pd
import io
import time
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Table, TableStyle
from datetime import datetime
from backend.models import Subject
from backend.database import get_session


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





def set_background(file_path: str = None, color: str = "#7abaa1", force_reload: bool = False):
    """
    Sets a Streamlit app background using a shared image for both
    main page and sidebar, with a soft translucent overlay for readability.
    """
    base64_image = None

    if file_path and os.path.exists(file_path):
        # Optionally clear cache
        if force_reload:
            try:
                st.cache_data.clear()
            except AttributeError:
                pass

        try:
            base64_image = get_base64_image(file_path)
        except Exception as e:
            st.warning(f"⚠️ Failed to load background image: {e}. Using color background instead.")
            base64_image = None
    else:
        base64_image = None

    if base64_image:
        st.markdown(
            f"""
            <style>
            /* 🌄 Main background */
            .stApp {{
                background: url("data:image/png;base64,{base64_image}") center/cover no-repeat fixed;
                background-attachment: fixed;
                background-position: center;
            }}

            /* 🌄 Sidebar uses same background image with a light frosted overlay */
            section[data-testid="stSidebar"] > div:first-child {{
                background: 
                    linear-gradient(rgba(255,255,255,0.85), rgba(255,255,255,0.9)),
                    url("data:image/png;base64,{base64_image}") center/cover no-repeat fixed !important;
                color: #0f3c2e !important;
                backdrop-filter: blur(6px);
            }}

            /* Sidebar titles/text */
            section[data-testid="stSidebar"] h1,
            section[data-testid="stSidebar"] h2,
            section[data-testid="stSidebar"] h3,
            section[data-testid="stSidebar"] p,
            section[data-testid="stSidebar"] span {{
                color: #0f3c2e !important;
                font-weight: 500;
            }}

            /* Sidebar buttons (soft mint style on image) */
            .stSidebar button {{
                background: linear-gradient(145deg, #9edbbb, #7bc8a2) !important;
                color: #fff !important;
                border: none !important;
                border-radius: 10px !important;
                transition: 0.3s ease-in-out;
                margin-bottom: 6px;
            }}
            .stSidebar button:hover {{
                transform: translateY(-2px);
                background: linear-gradient(145deg, #7bc8a2, #9edbbb) !important;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )
    else:
        # Fallback: gradient color background
        st.markdown(
            f"""
            <style>
            .stApp {{
                background: linear-gradient(135deg, {color}, #9ed3b8);
                color: #222 !important;
            }}
            section[data-testid="stSidebar"] {{
                background: linear-gradient(135deg, {color}, #94c7ad);
                color: #fff !important;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )


def render_test(questions, subject):
    """Render a stable one-question-per-page test with synced pagination."""
    st.subheader(f"⏳ {subject} Test In Progress")

    # === Initialize session vars ===
    st.session_state.setdefault("page", 1)
    total_questions = len(questions)
    st.session_state.setdefault("answers", [-1] * total_questions)

    # === Ensure correct length of answers ===
    if len(st.session_state.answers) != total_questions:
        st.session_state.answers = st.session_state.answers[:total_questions] + [-1] * (total_questions - len(st.session_state.answers))

    # === Pagination ===
    per_page = 1
    total_pages = (total_questions - 1) // per_page + 1
    page = max(1, min(st.session_state.page, total_pages))
    st.session_state.page = page
    q_index = page - 1

    # === Get question ===
    q = questions[q_index]
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f"**Q{q_index + 1}. {q.get('question','')}**")

    # === Parse options ===
    opts = []
    raw_opts = q.get("options", [])
    if isinstance(raw_opts, str):
        try:
            opts = json.loads(raw_opts)
        except Exception:
            opts = [o.strip() for o in raw_opts.split(",") if o.strip()]
    elif isinstance(raw_opts, list):
        opts = [str(o) for o in raw_opts]
    else:
        opts = [str(raw_opts)]

    # === Get current answer ===
    saved_answer = st.session_state.answers[q_index]
    current_selection = opts[saved_answer] if 0 <= saved_answer < len(opts) else None

    # === Radio with persistent key ===
    choice = st.radio(
        "Choose an answer:",
        options=[""] + opts,
        index=(opts.index(current_selection) + 1) if current_selection in opts else 0,
        key=f"choice_q_{q_index}_{st.session_state.get('test_id', '')}",
    )

    # === Save selected answer ===
    st.session_state.answers[q_index] = opts.index(choice) if choice in opts else -1

    st.markdown('</div>', unsafe_allow_html=True)

    # === Navigation Controls ===
    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if page > 1:
            if st.button("⬅ Previous", key=f"prev_btn_{q_index}"):
                st.session_state.page -= 1
                st.rerun()

    with col2:
        st.markdown(
            f"<div style='text-align:center; font-weight:600;'>Question {q_index+1} of {total_questions}</div>",
            unsafe_allow_html=True
        )

    with col3:
        if page < total_pages:
            if st.button("Next ➡", key=f"next_btn_{q_index}"):
                st.session_state.page += 1
                st.rerun()
        else:
            if st.button("✅ Submit Test", key="submit_btn_final"):
                st.session_state.submitted = True
                st.rerun()






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
    """
    Generate a clean and structured PDF result.

    Supports:
    - objective tests
    - subjective tests
    """

    from io import BytesIO
    from datetime import datetime

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Table, TableStyle
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader

    buffer = BytesIO()

    c = canvas.Canvas(buffer, pagesize=letter)

    width, height = letter

    # =====================================================
    # 🧠 HEADER SECTION
    # =====================================================
    y_top = height - 60
    center_x = width / 2

    # -----------------------------------------------------
    # 🏫 LOGO
    # -----------------------------------------------------
    logo_x = 60
    logo_y = y_top - 50

    if logo_path:

        try:
            logo = ImageReader(logo_path)

            c.drawImage(
                logo,
                logo_x,
                logo_y,
                width=60,
                height=50,
                preserveAspectRatio=True,
                mask='auto'
            )

        except Exception:

            c.setFont("Helvetica-Oblique", 9)
            c.drawString(logo_x, y_top - 20, "[Logo not found]")

    else:

        c.setFont("Helvetica-Oblique", 9)
        c.drawString(logo_x, y_top - 20, "[LOGO PLACEHOLDER]")

    # -----------------------------------------------------
    # 🏫 SCHOOL NAME
    # -----------------------------------------------------
    display_school = school_name or "SMART TEST SCHOOL"

    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(center_x, y_top, display_school)

    # -----------------------------------------------------
    # 📄 TITLE
    # -----------------------------------------------------
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(center_x, y_top - 20, "STUDENT TEST RESULT")

    # -----------------------------------------------------
    # 📅 META INFO
    # -----------------------------------------------------
    c.setFont("Helvetica", 9)

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    meta_text = (
        f"School ID: {school_id or 'N/A'}    "
        f"Generated: {generated_at}"
    )

    c.drawCentredString(center_x, y_top - 38, meta_text)

    # -----------------------------------------------------
    # Divider
    # -----------------------------------------------------
    c.setStrokeColorRGB(0.2, 0.6, 0.2)

    c.line(
        60,
        y_top - 48,
        width - 60,
        y_top - 48
    )

    # =====================================================
    # 👤 STUDENT INFO
    # =====================================================
    y = y_top - 85

    c.setFont("Helvetica", 11)

    c.drawString(70, y, f"Student Name: {name}")
    y -= 18

    c.drawString(70, y, f"Class: {class_name or 'N/A'}")
    y -= 18

    c.drawString(70, y, f"Subject: {subject}")
    y -= 18

    c.drawString(
        70,
        y,
        f"Test Type: {test_type.title()}"
    )
    y -= 18

    score_label = (
        "Score"
        if test_type == "objective"
        else "Total Score"
    )

    c.drawString(
        70,
        y,
        f"{score_label}: {correct}/{total} ({percent:.2f}%)"
    )

    # -----------------------------------------------------
    # Divider
    # -----------------------------------------------------
    y -= 15

    c.setStrokeColorRGB(0.2, 0.6, 0.2)

    c.line(
        60,
        y,
        width - 60,
        y
    )

    y -= 25

    # =====================================================
    # 📊 QUESTION BREAKDOWN
    # =====================================================
    c.setFont("Helvetica-Bold", 12)

    c.drawString(70, y, "Question Breakdown:")

    y -= 20

    # =====================================================
    # ✅ OBJECTIVE PDF
    # =====================================================
    if test_type == "objective":

        data = [
            ["#", "Question", "Your Answer", "Correct Answer", "Result"]
        ]

        for i, d in enumerate(details, start=1):

            if isinstance(d, dict):

                question = (
                    d.get("question_text")
                    or d.get("question")
                    or ""
                ).strip()

                your_answer = (
                    d.get("selected")
                    or d.get("your_answer")
                    or "—"
                )

                correct_answer = (
                    d.get("correct")
                    or d.get("correct_answer")
                    or "—"
                )

                is_correct = d.get("is_correct", False)

            else:

                question = str(d).strip()

                your_answer = "—"

                correct_answer = "—"

                is_correct = False

            short_q = (
                question[:65] + "..."
                if len(question) > 65
                else question
            )

            result = (
                "✔ Correct"
                if is_correct
                else "✘ Wrong"
            )

            data.append([
                str(i),
                short_q,
                str(your_answer),
                str(correct_answer),
                result
            ])

        table = Table(
            data,
            colWidths=[30, 220, 90, 90, 70]
        )

    # =====================================================
    # ✍️ SUBJECTIVE PDF
    # =====================================================
    else:

        data = [
            ["#", "Question", "Student Answer", "Teacher Score"]
        ]

        for i, d in enumerate(details, start=1):

            if isinstance(d, dict):

                question = (
                    d.get("question")
                    or d.get("question_text")
                    or f"Question {i}"
                )

                student_answer = (
                    d.get("answer")
                    or d.get("selected")
                    or "No Answer"
                )

                teacher_score = (
                    d.get("teacher_score")
                    or d.get("score")
                    or "Not Graded"
                )

            else:

                question = f"Question {i}"

                student_answer = str(d)

                teacher_score = "Not Graded"

            short_q = (
                question[:60] + "..."
                if len(question) > 60
                else question
            )

            short_answer = (
                str(student_answer)[:80] + "..."
                if len(str(student_answer)) > 80
                else str(student_answer)
            )

            data.append([
                str(i),
                short_q,
                short_answer,
                str(teacher_score)
            ])

        table = Table(
            data,
            colWidths=[30, 200, 250, 70]
        )

    # =====================================================
    # 🎨 TABLE STYLE
    # =====================================================
    table.setStyle(TableStyle([

        # Header
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),

        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),

        # Body
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),

        # Alignment
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),

        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),

        # Padding
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),

    ]))

    table.wrapOn(c, width - 120, height)

    table_height = len(data) * 18

    table.drawOn(
        c,
        60,
        y - table_height
    )

    # =====================================================
    # 📄 FOOTER
    # =====================================================
    c.setFont("Helvetica-Oblique", 9)

    c.setFillColorRGB(0.3, 0.3, 0.3)

    c.drawCentredString(
        width / 2,
        30,
        "Generated by Smart Test App © 2025"
    )

    c.setFillColorRGB(0, 0, 0)

    # =====================================================
    # ✅ FINALIZE
    # =====================================================
    c.showPage()

    c.save()

    buffer.seek(0)

    return buffer.getvalue()



# ==============================
# 🧩 Other Small Helpers
# ==============================
def df_download_button(df: pd.DataFrame, label: str, filename: str):
    """Download CSV button helper"""
    if df is None or df.empty:
        st.info("No data available for download.")
        return
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(label, csv, filename, "text/csv")

def excel_download_buffer(dfs: dict, filename="smarttest_backup.xlsx"):
    """Return Excel file buffer from dict of dataframes."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        for sheet, df in dfs.items():
            df.to_excel(writer, index=False, sheet_name=sheet[:31])
    buffer.seek(0)
    return buffer.getvalue()



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



def get_test_type(subject_name: str):
    """
    Determines if a subject should be Objective or Subjective.
    You can later move this logic to the DB or admin panel for flexibility.
    """
    subject_name = subject_name.strip().lower()

    # Example logic — you can customize
    OBJECTIVE_SUBJECTS = [
        "mathematics", "science", "ict", "rme", "social studies", "english"
    ]
    SUBJECTIVE_SUBJECTS = [
        "essay writing", "composition", "literature", "dictation"
    ]

    if subject_name in OBJECTIVE_SUBJECTS:
        return "objective"
    elif subject_name in SUBJECTIVE_SUBJECTS:
        return "subjective"
    else:
        # Default to objective if not categorized yet
        return "objective"



from backend.database import get_session
from backend.models import StudentProgress
from sqlalchemy.orm import Session

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




def get_subject_id_by_name(subject_name: str) -> int | None:
    """
    Convert a subject name (string) to its subject_id (int) using cached subjects.
    Returns None if not found.
    """
    return next(
        (s["id"] for s in st.session_state.get("subjects", []) if s["name"] == subject_name),
        None
    )
