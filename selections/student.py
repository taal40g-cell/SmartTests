import streamlit as st
from datetime import datetime, timedelta
from auth import get_student_by_code
from helpers import load_questions, calculate_score,load_users_dict
from helpers import show_question_tracker
import pandas as pd
from fpdf import FPDF
import io
import qrcode
import random

def run_student_mode():
    users_dict = load_users_dict()
    # ?? Init session
    defaults = {
        "test_started": False,
        "submitted": False,
        "logged_in": False,
        "student": {},
        "answers": [],
        "current_q": 0,
        "test_end_time": None,
        "questions": [],
        "subject": None  # ? Add this
    }

    for key, val in defaults.items():
        st.session_state.setdefault(key, val)

    st.markdown("<h3 style='text-decoration: underline;'>Student Portal</h3>", unsafe_allow_html=True)
    st.markdown("Welcome to your personalized test center.")

    # ?? Inject consistent styling
    st.markdown("""
        <style>
        .small-input input, .small-input select {
            width: 150px !important;
            padding: 6px;
            font-size: 14px;
            text-align: left;
        }
        </style>
    """, unsafe_allow_html=True)

    # ?? Login
    if not st.session_state.logged_in:
        # Tight and styled label just above input
        st.markdown("""
            <div style='margin-bottom: 2px; font-size: 16px; font-weight: 600;'>
                 Enter logins:
                <span title='Access code given by Admin' style='cursor: help;'></span>
            </div>
        """, unsafe_allow_html=True)

        access_code = st.text_input(
            label="Access Code",
            placeholder="e.g., 1234",
            key="access_code_input",
            label_visibility="collapsed"
        )
        # Shrink and align left
        st.markdown("""
            <style>
            div[data-baseweb="input"] {
                width: 220px !important;
                margin-left: 0 !important;
            }
            </style>
        """, unsafe_allow_html=True)

        if access_code:
            student = get_student_by_code(access_code.strip())
            if student:
                st.session_state.logged_in = True
                st.session_state.student = student
                st.success(f"Welcome, {student['name']} — Class {student['class']}")
                st.rerun()
            else:
                st.error("Invalid access code.")
        return
    with st.sidebar:
        st.header("View Past Performance")
        access_code_perf = st.text_input("Enter Access Code")


        from PIL import Image

        def generate_qr_code(data):
            qr = qrcode.QRCode(version=1, box_size=8, border=2)
            qr.add_data(data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)
            return buf

        # Inside your sidebar where you have access_code_perf and student_perf:
        if access_code_perf:
            student_perf = users_dict.get(access_code_perf.strip())
            if student_perf:
                st.success(f"Student: {student_perf['name']} | Class: {student_perf['class']}")

                # Generate QR code URL that directs to results page with params
                url = f"http://localhost:8501/?page=results&access_code={access_code_perf.strip()}"

                qr_img_buf = generate_qr_code(url)
                st.image(qr_img_buf, caption="Scan this QR to view performance", use_container_width=False)
            else:
                st.error("Invalid Access Code for performance lookup.")

    student = st.session_state.student
    # Normalize class name
    raw_class = student['class'].strip().lower().replace(" ", "")  # remove spaces & lowercase
    class_map = {
        "jhs1": "jhs 1",
        "jhs2": "jhs 2",
        "jhs3": "jhs 3"
    }
    class_name = class_map.get(raw_class, raw_class)

    st.info(f"{student['name']} | 🎓 Class: {class_name.upper()}")

    # Subject Selection
    subjects_by_class = {
        "jhs 1": ["English", "Math", "Science", "History", "Geography", "Physics", "Chemistry", "Biology", "ICT",
                  "Economics"],
        "jhs 2": ["English", "Math", "Science", "History", "Geography", "Physics", "Chemistry", "Biology", "ICT",
                  "Economics"],
        "jhs 3": ["English", "Math", "Science", "History", "Geography", "Physics", "Chemistry", "Biology", "ICT",
                  "Economics"],
    }

    subject_list = subjects_by_class.get(class_name, [])

    # Render selectable with a placeholder if list is empty
    with st.container():
        st.markdown("""
            <style>
            div[data-baseweb="select"] {
                width: 220px !important;
                margin-left: 0 !important;
            }
            </style>
        """, unsafe_allow_html=True)
        st.markdown('<div class="small-input">', unsafe_allow_html=True)

        # ----------------------------
        # SUBJECT SELECTION & START TEST
        # ----------------------------

        # Initialize selected_subject in session_state if not exists
        if "selected_subject" not in st.session_state:
            st.session_state.selected_subject = None

        # Subject list for the student's class
        subjects_by_class = {
            "jhs 1": ["English", "Math", "Science", "History", "Geography", "Physics",
                      "Chemistry", "Biology", "ICT", "Economics"],
            "jhs 2": ["English", "Math", "Science", "History", "Geography", "Physics",
                      "Chemistry", "Biology", "ICT", "Economics"],
            "jhs 3": ["English", "Math", "Science", "History", "Geography", "Physics",
                      "Chemistry", "Biology", "ICT", "Economics"],
        }

        subject_list = subjects_by_class.get(class_name, [])

        # Styling
        st.markdown("""
            <style>
            div[data-baseweb="select"] {
                width: 220px !important;
                margin-left: 0 !important;
            }
            .small-input input, .small-input select {
                width: 150px !important;
                padding: 6px;
                font-size: 14px;
                text-align: left;
            }
            </style>
        """, unsafe_allow_html=True)

        # Initialize selected_subject if it doesn't exist
        if "selected_subject" not in st.session_state:
            st.session_state.selected_subject = None

        # Render the subject selectbox
        if subject_list:
            st.selectbox(
                "Select Subject",
                subject_list,
                index=0 if st.session_state.selected_subject is None else subject_list.index(
                    st.session_state.selected_subject),
                key="selected_subject",
                label_visibility="visible"
            )
        else:
            st.selectbox(
                "Subject",
                ["No subjects available"],
                key="subject_select_empty",
                disabled=True
            )

        # Start Test button
        if st.button("Start Test"):
            selected_subject = st.session_state.selected_subject
            if not selected_subject:
                st.error("❌ Please select a subject before starting the test.")
            else:
                st.session_state.start_info = f"📝 Starting test for Class: `{class_name}`, Subject: `{selected_subject}`"

                # Reset previous test session but NOT selected_subject
                st.session_state.questions = []
                st.session_state.answers = []
                st.session_state.current_q = 0
                st.session_state.test_started = False
                st.session_state.submitted = False
                st.session_state.test_end_time = None

                # Load questions
                questions = load_questions(class_name, selected_subject)
                if questions:
                    base_questions = questions[:5]
                    randomized_questions = []
                    while len(randomized_questions) < 20:
                        randomized_questions.append(random.choice(base_questions))
                    random.shuffle(randomized_questions)

                    st.session_state.questions = randomized_questions
                    st.session_state.answers = [""] * len(randomized_questions)
                    st.session_state.current_q = 0
                    st.session_state.test_started = True
                    st.session_state.submitted = False
                    st.session_state.test_end_time = datetime.now() + timedelta(minutes=30)
                    st.session_state.subject = selected_subject
                    st.rerun()

    # Show the start message after rerun
    if "start_info" in st.session_state:
        st.info(st.session_state.start_info)
        del st.session_state.start_info

    # ?? Test in Progress
    if st.session_state.test_started and not st.session_state.submitted:
        now = datetime.now()
        if st.session_state.test_end_time is not None and now > st.session_state.test_end_time:
            st.warning("Time is up! Submitting automatically.")
            st.session_state.submitted = True

        else:
            questions = st.session_state.questions
            show_question_tracker()
            q_index = st.session_state.current_q
            q = questions[q_index]

            st.markdown(
                f"<h3 style='font-size:24px; font-weight:600;'>Q{q_index + 1}. {q['question']}</h3>",
                unsafe_allow_html=True
            )

            options = [""] + q["options"]  # Add empty option as first
            selected = st.session_state.answers[q_index]

            st.session_state.answers[q_index] = st.radio(
                "Choose one:",
                options,
                index=options.index(selected) if selected in options else 0,
                key=f"q_{q_index}"
            )
            # Initialize marked_for_review set if it doesn't exist
            if "marked_for_review" not in st.session_state:
                st.session_state.marked_for_review = set()

            # Is current question marked?
            is_marked = q_index in st.session_state.marked_for_review

            # Checkbox for marking the question for review
            mark_toggle = st.checkbox(
                "Mark this question for review",
                value=is_marked,
                key=f"mark_review_{q_index}"
            )

            # Update the set based on toggle
            if mark_toggle:
                st.session_state.marked_for_review.add(q_index)
            else:
                st.session_state.marked_for_review.discard(q_index)

            col1, col2, col3 = st.columns(3)
            with col1:
                st.button("Previous", on_click=lambda: st.session_state.update(current_q=st.session_state.current_q - 1), disabled=q_index == 0)
            with col2:
                st.button("Next", on_click=lambda: st.session_state.update(current_q=st.session_state.current_q + 1), disabled=q_index == len(questions) - 1)
            with col3:
                if st.button("Submit Test"):
                    st.session_state.submitted = True


    # ?? Result Summary
    if st.session_state.submitted:
        correct, details = calculate_score(st.session_state.questions, st.session_state.answers)
        total = len(st.session_state.questions)
        percent = (correct / total) * 100

        # ?? Score feedback
        st.success(f" Score: {correct}/{total} ({percent:.2f}%)")

        # ?? Feedback + animation
        if percent >= 90:
            st.balloons()
            st.markdown("###Excellent work! You're a star!")
        elif percent >= 70:
            st.snow()
            st.markdown("### Good job! You're getting there!")
        elif percent >= 50:
            st.info("### Fair effort. A little more practice will help!")
        else:
            st.warning("###  Keep trying! Practice makes perfect!")

        # ?? Quick summary
        correct_count = sum(1 for d in details if d['is_correct'])
        wrong_count = total - correct_count
        col1, col2 = st.columns(2)
        with col1:
            st.success(f" Correct: {correct_count}")
        with col2:
            st.error(f"Wrong: {wrong_count}")

        # ?? Detailed Answer View + PDF
        with st.expander("View Correct / Wrong Answers & Download Your Results"):
            for i, d in enumerate(details):
                st.write(f"**Q{i + 1}: {d['question']}**")
                st.write(f"? Correct Answer: {d['correct_answer']}")
                st.write(f"?? Your Answer: {d['your_answer'] or 'No Answer'}")
                if d['is_correct']:
                    st.success("Correct")
                else:
                    st.error("Incorrect")
                st.divider()

            # Simple PDF export

            # Show school info and timestamp
            logo_path = "assets/logo.png"
            school_name = "SmartTest Academy"
            timestamp = datetime.now().strftime("%d-%m-%Y %H:%M")

            st.image(logo_path, width=80)
            st.markdown(f"## ?? {school_name}")
            st.markdown(f"?? **Date:** {timestamp}")
            st.markdown(
                f" **Student:** {student['name']}  |  **Class:** {student['class'].upper()}  |  **Subject:** {st.session_state.subject}")
            st.markdown(f" **Score:** {correct}/{total} ({percent:.2f}%)")

            # ?? Feedback
            if percent >= 90:
                st.balloons()
                st.markdown("###Excellent work! You're a star!")
            elif percent >= 70:
                st.snow()
                st.markdown("###  Good job! You're getting there!")
            elif percent >= 50:
                st.info("### Fair effort. A little more practice will help!")
            else:
                st.warning("### Download result summary!")

            # ?? Quick Count
            # ?? View full result in a nice table
            st.markdown("### Detailed Answers")
            df = pd.DataFrame([{
                "Q#": i + 1,
                "Question": d["question"],
                "Your Answer": d["your_answer"],
                "Correct Answer": d["correct_answer"],
                "Result": "? Correct" if d["is_correct"] else "? Wrong"
            } for i, d in enumerate(details)])

            st.dataframe(df, use_container_width=True)

            # ?? PDF Generation Function
            def generate_pdf(name, class_name, subject, correct, total, percent, details):
                pdf = FPDF()
                pdf.add_page()

                pdf.image(logo_path, x=10, y=8, w=25)
                pdf.set_font("Arial", 'B', 16)
                pdf.cell(80)
                pdf.cell(30, 10, school_name, ln=True, align="C")
                pdf.set_font("Arial", size=12)
                pdf.cell(0, 10, f"Date: {timestamp}", ln=True)
                pdf.cell(0, 10, f"Student: {name} | Class: {class_name} | Subject: {subject}", ln=True)
                pdf.cell(0, 10, f"Score: {correct}/{total} ({percent:.2f}%)", ln=True)
                pdf.ln(5)

                for i, d in enumerate(details):
                    pdf.set_font("Arial", size=11)
                    pdf.multi_cell(0, 10,
                                   f"Q{i + 1}: {d['question']}\nYour Answer: {d['your_answer']}\nCorrect Answer: {d['correct_answer']}\nResult: {'Correct' if d['is_correct'] else 'Wrong'}",
                                   border=1)
                    pdf.ln(1)

                return pdf.output(dest='S').encode('latin1')

            # ?? Offer PDF download
            pdf_bytes = generate_pdf(
                name=student['name'],
                class_name=student['class'],
                subject=st.session_state.subject,
                correct=correct,
                total=total,
                percent=percent,
                details=details
            )

            st.download_button("Download Results as PDF", data=pdf_bytes, file_name="smarttest_result.pdf")
