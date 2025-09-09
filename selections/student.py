
import streamlit as st
import io
import qrcode
from fpdf import FPDF
from datetime import datetime, timedelta
from helpers import (
    generate_result_pdf,
    get_users, set_users,
    get_submissions, set_submissions,
    load_questions, save_submission,
    show_question_tracker,
    calculate_score,
    can_take_test,  # ✅ Ensure we import the helper
)

# =====================================================================
# Student Mode Main Function
# =====================================================================
def run_student_mode():
    users_dict = get_users()

    # -----------------------------
    # Initialize session variables
    # -----------------------------
    defaults = {
        "test_started": False,
        "submitted": False,
        "logged_in": False,
        "student": {},
        "answers": [],
        "current_q": 0,
        "test_end_time": None,
        "questions": [],
        "subject": None,
        "marked_for_review": set()
    }
    for key, val in defaults.items():
        st.session_state.setdefault(key, val)

    # -----------------------------
    # Header
    # -----------------------------
    st.markdown("### SmartTest Student Portal")
    st.markdown("Welcome to your personalized test center.")

    # -----------------------------
    # Global CSS styling
    # -----------------------------
    st.markdown("""
        <style>
        .small-input input, .small-input select {
            width: 150px !important; padding: 6px; font-size: 14px;
        }
        div[data-baseweb="input"], div[data-baseweb="select"] {
            width: 220px !important; margin-left: 0 !important;
        }
        .card {
            padding: 1rem; margin-top: 0.8rem; border-radius: 10px;
            border: 1px solid #ddd; background-color: #fafafa;
            box-shadow: 1px 1px 4px rgba(0,0,0,0.08);
        }
        </style>
    """, unsafe_allow_html=True)

    # =================================================================
    # Login
    # =================================================================
    if not st.session_state.logged_in:
        st.markdown("<div style='font-size:16px; font-weight:600;'>Enter logins:</div>", unsafe_allow_html=True)
        access_code = st.text_input(
            label="Logins",
            placeholder="eg: code given by Admin",
            key="access_code_input",
            label_visibility="collapsed"
        )

        if access_code:
            student = users_dict.get(access_code.strip())
            if student:
                # Set session
                student["access_code"] = access_code.strip()
                st.session_state.logged_in = True
                st.session_state.student = student
                st.success(f"Welcome, {student['name']} — Class {student['class']}")
                st.rerun()
            else:
                st.error("Invalid login code.")
            return

    # =================================================================
    # Sidebar: Past Performance + Refresh
    # =================================================================
    with st.sidebar:
        st.header("View Past Performance")
        access_code_perf = st.text_input("Enter Access Code", key="sidebar_access_code")

        def generate_qr_code(data):
            qr = qrcode.QRCode(version=1, box_size=8, border=2)
            qr.add_data(data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)
            return buf

        if access_code_perf:
            student_perf = users_dict.get(access_code_perf.strip())
            if student_perf:
                st.success(f"Student: {student_perf['name']} | Class: {student_perf['class']}")
                url = f"http://localhost:8501/?page=results&access_code={access_code_perf.strip()}"
                st.image(generate_qr_code(url), caption="Scan this QR to view performance", use_container_width=False)
            else:
                st.error("Invalid Access Code.")

        if st.session_state.logged_in:
            if st.button("🔄 Refresh Test", key="refresh_update_state"):
                # ✅ Clear only test-related session state
                for k in ["test_started", "submitted", "questions", "answers", "current_q", "marked_for_review", "test_end_time"]:
                    st.session_state.pop(k, None)
                st.success("✅ Test has been cleared. You can start a new test.")
                st.rerun()

    # =================================================================
    # Student Info
    # =================================================================
    student = st.session_state.student
    if student and "name" in student:
        st.info(f"Welcome {student['name']} | Class: {student.get('class', 'Unknown').upper()}")

    # =================================================================
    # Subject Selection
    # =================================================================
    subjects_list = {
        "jhs1": ["English", "Math", "Science", "History", "Geography", "Physics", "Chemistry", "Biology", "ICT", "Economics"],
        "jhs2": ["English", "Math", "Science", "History", "Geography", "Physics", "Chemistry", "Biology", "ICT", "Economics"],
        "jhs3": ["English", "Math", "Science", "History", "Geography", "Physics", "Chemistry", "Biology", "ICT", "Economics"],
    }

    subject_options = subjects_list.get(student.get('class', '').strip().lower().replace(" ", ""), [])
    if not subject_options:
        st.info("No subjects found for your class.")
        return

    st.markdown('<div class="small-input">', unsafe_allow_html=True)
    selected_subject = st.selectbox("Select Subject", subject_options, key="subject_select", label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)
    st.session_state.subject = selected_subject

    # =================================================================
    # Start Test Button with Retake Enforcement (✅ cleaned up)
    # =================================================================
    if st.button("Start Test") and not st.session_state.test_started:
        access_code = student.get("access_code", "").strip()
        allowed, msg = can_take_test(access_code, st.session_state.subject)
        if not allowed:
            st.error(msg)
            st.stop()

        # Load questions
        questions = load_questions(student.get("class", ""), st.session_state.subject)
        if not questions:
            st.warning("Good Luck.")
            return

        # Initialize test session
        st.session_state.update({
            "test_started": True,
            "submitted": False,
            "questions": questions,
            "answers": [""] * len(questions),
            "current_q": 0,
            "marked_for_review": set(),
            "test_end_time": datetime.now() + timedelta(minutes=30)
        })

    # =================================================================
    # Test In Progress
    # =================================================================
    if st.session_state.test_started and not st.session_state.submitted:
        now = datetime.now()
        if now > st.session_state.test_end_time:
            st.warning("⏰ Time is up! Submitting automatically.")
            st.session_state.submitted = True
        else:
            questions = st.session_state.questions
            show_question_tracker(questions, st.session_state.current_q, st.session_state.answers)

            q_index = st.session_state.current_q
            q = questions[q_index]

            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown(f"**Q{q_index + 1}. {q['question']}**")

            options = [""] + q.get("options", [])
            selected = st.session_state.answers[q_index]
            st.session_state.answers[q_index] = st.radio(
                "Choose one:", options, index=options.index(selected) if selected in options else 0, key=f"q_{q_index}"
            )

            mark_toggle = st.checkbox(
                "Mark this question for review",
                value=q_index in st.session_state.marked_for_review,
                key=f"mark_review_{q_index}"
            )
            if mark_toggle:
                st.session_state.marked_for_review.add(q_index)
            else:
                st.session_state.marked_for_review.discard(q_index)

            col1, col2, col3 = st.columns(3)
            with col1:
                st.button("Previous", on_click=lambda: st.session_state.update(
                    current_q=max(st.session_state.current_q - 1, 0)), disabled=q_index == 0)
            with col2:
                st.button("Next", on_click=lambda: st.session_state.update(
                    current_q=min(st.session_state.current_q + 1, len(questions) - 1)), disabled=q_index == len(questions) - 1)
            with col3:
                if st.button("Submit Test"):
                    st.session_state.submitted = True
            st.markdown('</div>', unsafe_allow_html=True)

    # =================================================================
    # Results + PDF
    # =================================================================
    if st.session_state.submitted:
        correct, details = calculate_score(st.session_state.questions, st.session_state.answers)
        total = len(st.session_state.questions)
        percent = (correct / total) * 100 if total > 0 else 0

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.success(f"Score: {correct}/{total} ({percent:.2f}%)")

        if percent >= 90:
            st.balloons()
            st.markdown("### Excellent work! You're a star! ⭐")
        elif percent >= 70:
            st.snow()
            st.markdown("### Good job! Keep it up! 👍")
        elif percent >= 50:
            st.info("### Fair effort. Keep practicing!")
        else:
            st.warning("### Keep trying! Practice makes perfect!")

        # Correct / Wrong counts
        correct_count = sum(1 for d in details if d['is_correct'])
        wrong_count = total - correct_count
        col1, col2 = st.columns(2)
        col1.success(f"Correct: {correct_count}")
        col2.error(f"Wrong: {wrong_count}")

        with st.expander("View Detailed Answers"):
            for i, d in enumerate(details):
                st.markdown(f"**Q{i + 1}: {d['question']}**")
                st.write(f"Your Answer: {d['your_answer'] or 'No Answer'}")
                st.write(f"Correct Answer: {d['correct_answer']}")
                st.success("Correct" if d['is_correct'] else "Incorrect")
                st.divider()
        st.markdown('</div>', unsafe_allow_html=True)

        # ✅ Generate PDF
        logo_path = "assets/logo.png"
        school_name = "My School"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        def generate_pdf(name, class_name, subject, correct, total, percent, details):
            pdf = FPDF()
            pdf.add_page()
            try:
                pdf.image(logo_path, x=10, y=8, w=25)
            except:
                pass
            pdf.set_font("Arial", 'BU', 16)
            pdf.cell(0, 10, school_name, ln=True, align="C")
            pdf.set_font("Arial", size=12)
            page_width = pdf.w - 2 * pdf.l_margin
            date_text = f"Date: {timestamp}"
            text_width = pdf.get_string_width(date_text) + 6
            pdf.set_xy(pdf.l_margin + page_width - text_width, 10)
            pdf.cell(text_width, 10, date_text, ln=False)
            pdf.ln(15)
            pdf.cell(0, 10, f"Student: {name} | Class: {class_name} | Subject: {subject}", ln=True)
            pdf.cell(0, 10, f"Score: {correct}/{total} ({percent:.2f}%)", ln=True)
            pdf.ln(5)
            for i, d in enumerate(details):
                pdf.set_font("Arial", size=11)
                pdf.multi_cell(
                    0, 10,
                    f"Q{i + 1}: {d['question']}\n"
                    f"Your Answer: {d.get('your_answer', 'No Answer')}\n"
                    f"Correct Answer: {d.get('correct_answer', 'N/A')}\n"
                    f"Result: {'Correct' if d.get('is_correct') else 'Wrong'}",
                    border=1
                )
                pdf.ln(1)
            return pdf.output(dest='S').encode('latin1')

        # ==========================================================
        # Save submission with retake enforcement
        # ==========================================================
        access_code = st.session_state.student.get("access_code", "").strip()
        subject = st.session_state.subject

        allowed, msg = can_take_test(access_code, subject)

        if not allowed:
            st.error(msg)
        else:
            submissions = get_submissions()
            submissions.append({
                "access_code": access_code,
                "subject": subject,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "allowed_retake": False  # reset after submission
            })
            set_submissions(submissions)

            # Generate & allow PDF download
            pdf_bytes = generate_pdf(
                name=st.session_state.student['name'],
                class_name=st.session_state.student['class'],
                subject=st.session_state.subject,
                correct=correct,
                total=total,
                percent=percent,
                details=details
            )
            st.download_button("Download Results as PDF", data=pdf_bytes, file_name="smartest_result.pdf")
