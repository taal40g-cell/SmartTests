import streamlit as st
import os
import base64
import json
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from datetime import datetime
from io import BytesIO

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


# -----------------------------
# Set Streamlit background
# -----------------------------
def set_background(file_path: str, force_reload: bool = False):
    """
    Sets a Streamlit app background using a local image.

    Parameters:
    - file_path: Path to the image file.
    - force_reload: If True, clears the cached image to reload a new one.
    """
    if not os.path.exists(file_path):
        st.error(f"Background file not found: {file_path}")
        return

    # Force cache clear if requested
    if force_reload:
        try:
            st.cache_data.clear()
        except AttributeError:
            pass  # Older Streamlit versions may not support clear()

    try:
        base64_image = get_base64_image(file_path)
    except Exception as e:
        st.error(f"Failed to load background image: {e}")
        return

    st.markdown(
        f"""
        <style>
            .stApp {{
                background-image: url("data:image/png;base64,{base64_image}");
                background-size: cover;
                background-repeat: no-repeat;
                background-attachment: fixed;
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



def generate_pdf(name, class_name, subject, correct, total, percent, details, logo_path=None):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # --- Logo on the Left ---
    if logo_path:
        try:
            logo = ImageReader(logo_path)
            c.drawImage(logo, 60, height - 100, width=80, height=60, preserveAspectRatio=True, mask='auto')
        except Exception:
            c.setFont("Helvetica-Oblique", 10)
            c.drawString(60, height - 80, "[Logo not found]")
    else:
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(60, height - 80, "[LOGO PLACEHOLDER]")

    # --- Title ---
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width / 2 + 60, height - 70, "SMART TEST RESULT")

    # --- Date & Time ---
    c.setFont("Helvetica", 10)
    c.drawRightString(width - 60, height - 80, datetime.now().strftime("Generated: %Y-%m-%d %H:%M:%S"))

    # --- Student Info ---
    c.setFont("Helvetica", 12)
    y = height - 140
    c.drawString(70, y, f"Student: {name}")
    y -= 20
    c.drawString(70, y, f"Class: {class_name}")
    y -= 20
    c.drawString(70, y, f"Subject: {subject}")
    y -= 20
    c.drawString(70, y, f"Score: {correct}/{total} ({percent:.2f}%)")
    y -= 30

    # --- Divider ---
    c.setStrokeColorRGB(0.2, 0.6, 0.2)
    c.line(60, y, width - 60, y)
    y -= 30

    # --- Detailed Results ---
    c.setFont("Helvetica-Bold", 13)
    c.drawString(70, y, "Question Breakdown")
    y -= 20
    c.setFont("Helvetica", 10)

    for i, d in enumerate(details, start=1):
        question = d.get("question", "")
        your_answer = d.get("your_answer", "No Answer")
        correct_answer = d.get("correct_answer", "N/A")
        is_correct = d.get("is_correct", False)

        qtext = f"Q{i}: {question[:80]}..." if len(question) > 80 else f"Q{i}: {question}"

        # Question
        c.setFont("Helvetica-Bold", 10)
        c.drawString(70, y, qtext)
        y -= 15

        # Answers
        c.setFont("Helvetica", 10)
        c.drawString(90, y, f"Your Answer: {your_answer}")
        y -= 15
        c.drawString(90, y, f"Correct Answer: {correct_answer}")
        y -= 15
        c.setFillColorRGB(0, 0.6, 0) if is_correct else c.setFillColorRGB(1, 0, 0)
        c.drawString(90, y, f"Result: {'✔ Correct' if is_correct else '✘ Wrong'}")
        c.setFillColorRGB(0, 0, 0)
        y -= 25

        if y < 100:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = height - 100

    # --- Footer ---
    c.setFont("Helvetica-Oblique", 9)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.drawCentredString(width / 2, 30, "Generated by Smart Test App © 2025")
    c.setFillColorRGB(0, 0, 0)

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()




def is_archived(q):
    """Safely return True/False if a question is archived."""
    if isinstance(q, dict):
        return q.get("archived", False)
    return getattr(q, "archived", False)


