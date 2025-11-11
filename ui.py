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
from helpers import get_subjective_questions, submit_subjective_answer
from models import Subject,SubjectiveSubmission
from database import get_session


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



def generate_pdf(name, class_name, subject, correct, total, percent, details,
                 school_name=None, school_id=None, logo_path=None):
    """
    Generate a neat test result PDF with school info, logo, and result breakdown in a table.
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # --- Top Header Section ---
    y_top = height - 60

    # School logo
    if logo_path:
        try:
            logo = ImageReader(logo_path)
            c.drawImage(logo, 60, y_top - 40, width=80, height=60, preserveAspectRatio=True, mask='auto')
        except Exception:
            c.setFont("Helvetica-Oblique", 9)
            c.drawString(60, y_top - 20, "[Logo not found]")
    else:
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(60, y_top - 20, "[LOGO PLACEHOLDER]")

    # School Name and Info
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2 + 40, y_top, school_name or "SMART TEST SCHOOL")
    c.setFont("Helvetica", 10)
    if school_id:
        c.drawCentredString(width / 2 + 40, y_top - 15, f"School ID: {school_id}")

    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2 + 40, y_top - 40, "STUDENT TEST RESULT")

    # Date/Time
    c.setFont("Helvetica", 9)
    c.drawRightString(width - 60, y_top - 20, datetime.now().strftime("Generated: %Y-%m-%d %H:%M:%S"))

    # --- Student Info ---
    y = y_top - 80
    c.setFont("Helvetica", 11)
    c.drawString(70, y, f"Student Name: {name}")
    y -= 18
    c.drawString(70, y, f"Class: {class_name}")
    y -= 18
    c.drawString(70, y, f"Subject: {subject}")
    y -= 18
    c.drawString(70, y, f"Score: {correct}/{total} ({percent:.2f}%)")

    # Divider Line
    y -= 15
    c.setStrokeColorRGB(0.2, 0.6, 0.2)
    c.line(60, y, width - 60, y)
    y -= 25

    # --- Detailed Results in Table ---
    c.setFont("Helvetica-Bold", 12)
    c.drawString(70, y, "Question Breakdown:")
    y -= 15

    # Table headers and rows
    data = [["#", "Question", "Your Answer", "Correct Answer", "Result"]]

    for i, d in enumerate(details, start=1):
        question = d.get("question", "").strip()
        your_answer = d.get("your_answer", "—")
        correct_answer = d.get("correct_answer", "—")
        is_correct = d.get("is_correct", False)
        short_q = (question[:65] + "...") if len(question) > 65 else question
        result = "✔ Correct" if is_correct else "✘ Wrong"
        data.append([str(i), short_q, your_answer, correct_answer, result])

    # Table style
    table = Table(data, colWidths=[30, 200, 100, 100, 70])
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ])
    table.setStyle(style)

    # Build table page by page
    available_height = y - 100
    table_height = len(data) * 18
    if table_height > available_height:
        # too long, split across pages
        c.showPage()
        y = height - 80

    table.wrapOn(c, width - 120, height)
    table.drawOn(c, 60, y - (len(data) * 18))

    # --- Footer ---
    c.setFont("Helvetica-Oblique", 9)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.drawCentredString(width / 2, 30, "Generated by Smart Test App © 2025")
    c.setFillColorRGB(0, 0, 0)

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()



# ==============================
# Constants
# ==============================
CLASSES = ["JHS1", "JHS2", "JHS3", "SHS1", "SHS2", "SHS3"]


# ==============================
# 🧠 Subject Management Helpers
# ==============================
SUBJECTS_FILE = "subjects.json"
DEFAULT_SUBJECTS = [
    "English", "Mathematics", "Science", "History", "Geography",
    "Physics", "Chemistry", "Biology", "ICT", "Economics"
]

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


def load_classes():
    """Load class list from file or return default list."""
    file_path = "data/classes.json"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return ["JHS 1", "JHS 2", "JHS 3"]


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



# ==============================================
# 🎓 STUDENT: SUBJECTIVE TEST SECTION
# ==============================================
def run_subjective_test_ui():
    st.subheader("📝 Subjective Test Section")

    school_id = st.session_state.get("school_id")
    student_id = st.session_state.get("student_id")
    access_code = st.session_state.get("access_code")
    student_name = st.session_state.get("student_name")

    if not all([school_id, student_id]):
        st.warning("⚠️ Please log in properly to continue.")
        st.stop()

    cls = st.selectbox("Select Class", CLASSES, key="subj_cls")
    subject = st.selectbox("Select Subject", Subject, key="subj_sub")

    if st.button("📂 Load Questions"):
        questions = get_subjective_questions(school_id, cls, subject)

        if not questions:
            st.info("No subjective questions uploaded for this class and subject yet.")
            return

        st.markdown("### ✍️ Answer the questions below:")
        answers = {}
        for q in questions:
            st.markdown(f"**Q{q.id}. {q.question_text}** ({q.marks} marks)")
            answers[q.id] = st.text_area(f"Answer for Q{q.id}", height=150, key=f"ans_{q.id}")

        if st.button("📤 Submit Answers"):
            ok = submit_subjective_answer(
                school_id, student_id, access_code, cls, subject, answers
            )
            if ok:
                st.success("✅ Answers submitted successfully! Await teacher review.")
            else:
                st.error("❌ Could not save answers. Please try again.")




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



