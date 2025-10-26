
import io
import uuid
import time
import json
import qrcode
import streamlit as st
from ui import render_test, generate_pdf
from db_helpers import (
    get_submission_db,
    add_submission_db,
    load_questions_db,
    set_submission_db,
    calculate_score_db,
    show_question_tracker,
    can_take_test,
    get_users,
    get_test_duration,load_student_results,
    get_retake_db,get_student_by_access_code_db,get_student_by_code,get_current_school_id,
    decrement_retake,save_student_answers,load_progress, save_progress, clear_progress
)
def get_student_display(student) -> str:
    """Return a formatted display string for both dict and ORM student."""
    if hasattr(student, "__dict__"):  # ORM object
        name = getattr(student, "name", "Student")
        class_name = getattr(student, "class_name", "Unknown")
    else:  # dictionary
        name = student.get("name", "Student")
        class_name = student.get("class_name", "Unknown")
    return f"Welcome {name} | Class: {class_name.upper()}"

from streamlit_autorefresh import st_autorefresh

# ==============================
# Main Student Mode
# ==============================
def run_student_mode():
    users_dict = get_users()

    # -----------------------------
    # Initialize session defaults
    # -----------------------------
    defaults = {
        "test_started": False,
        "submitted": False,
        "logged_in": False,
        "student": {},
        "answers": [],
        "current_q": 0,
        "current_page": 0,
        "questions": [],
        "subject": None,
        "marked_for_review": set(),
        "duration": None,
        "start_time": None,
        "five_min_warned": False,
        "saved_to_db": False,
        "last_auto_save": 0
    }
    for key, val in defaults.items():
        st.session_state.setdefault(key, val)

    # Helper: ensure answers list length matches questions
    def _normalize_answers(answers, questions):
        # Convert dict -> list if needed, then pad with -1
        if isinstance(answers, dict):
            try:
                out = [-1] * len(questions)
                for k, v in answers.items():
                    idx = int(k)
                    out[idx] = int(v)
                answers = out
            except Exception:
                answers = [-1] * len(questions)
        if not isinstance(answers, list):
            answers = [-1] * len(questions)
        if len(answers) < len(questions):
            answers = answers + [-1] * (len(questions) - len(answers))
        if len(answers) > len(questions):
            answers = answers[: len(questions)]
        return answers

    # -----------------------------
    # Header & Banner
    # -----------------------------
    st.markdown("### SmartTest Student Portal")
    st.markdown("Welcome to your personalized test center.")
    st.markdown(
        """
        <marquee behavior="scroll" direction="left" scrollamount="5"
            style="color: #F54927; padding: 10px; border-radius: 15px; font-weight: bold;">
           Retakes are controlled by Admins! Submit your test before time runs out 
        </marquee>
        """,
        unsafe_allow_html=True
    )

    # -----------------------------
    # CSS Styling
    # -----------------------------
    st.markdown("""
        <style>
        .small-input input, .small-input select { width: 150px !important; padding: 6px; font-size: 14px; }
        div[data-baseweb="input"], div[data-baseweb="select"] { width: 220px !important; margin-left: 0 !important; }
        .card { padding: 1rem; margin-top: 0.8rem; border-radius: 10px; border: 1px solid #ddd; background-color: #fafafa; box-shadow: 1px 1px 4px rgba(0,0,0,0.08); }
        </style>
    """, unsafe_allow_html=True)

    # ==============================
    # Login
    # ==============================
    if not st.session_state.logged_in:
        st.markdown("<div style='font-size:16px; font-weight:600;'>Enter Access Code:</div>", unsafe_allow_html=True)
        access_code = st.text_input("Access Code", placeholder="Code issued by Admin", key="access_code_input", label_visibility="collapsed")
        if access_code:
            student = get_student_by_access_code_db(access_code.strip().upper())
            if student:
                # ✅ Convert ORM object → dictionary
                student = {
                    "id": student.id,
                    "name": student.name,
                    "class_name": student.class_name,
                    "access_code": student.access_code,
                    "can_retake": getattr(student, "can_retake", True)
                }

                st.session_state.logged_in = True
                st.session_state.student = student

                # Clear any residual test state on fresh login
                for k in [
                    "test_started", "submitted", "questions", "answers", "current_q",
                    "marked_for_review", "start_time", "duration", "five_min_warned", "saved_to_db"
                ]:
                    st.session_state.pop(k, None)

                st.info(get_student_display(student))
                st.rerun()
            else:
                st.error("Invalid login code ❌")

        st.stop()

    # ==============================
    # Handle QR Access via URL
    # ==============================
    query_params = st.query_params
    if "access_code" in query_params:
        st.session_state["sidebar_access_code"] = query_params["access_code"]

    # ==============================
    # Sidebar: Past Performance + Refresh
    # ==============================
    with st.sidebar:
        st.markdown(
            """
            <style>
            [data-testid="stSidebar"] {
                background-color: #7abaa1 !important;
                color: white !important;
            }
            [data-testid="stSidebar"] h1, 
            [data-testid="stSidebar"] h2, 
            [data-testid="stSidebar"] h3, 
            [data-testid="stSidebar"] label, 
            [data-testid="stSidebar"] p {
                color: white !important;
            }
            </style>
            """,
            unsafe_allow_html=True
        )

        st.header("📊 View Past Performance")
        access_code_perf = st.text_input("Enter Access Code", key="sidebar_access_code")

        import qrcode, io
        import pandas as pd
        from sqlalchemy.orm import Session
        from database import get_session
        from models import Student

        def generate_qr_code(data):
            qr = qrcode.QRCode(version=1, box_size=8, border=2)
            qr.add_data(data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            return buf

        APP_URL = "https://smarttests-1.onrender.com"

        # ------------------------------
        # Sidebar Access Code Input
        # ------------------------------
        if access_code_perf:
            access_code_perf = access_code_perf.strip().upper()
            student_perf = get_student_by_access_code_db(access_code_perf)

            if not student_perf:
                st.error("❌ Invalid Access Code.")
            else:
                st.success(f"Student: {student_perf.name} | Class: {student_perf.class_name}")

                # Generate QR link
                url = f"{APP_URL}?access_code={access_code_perf}"
                st.image(generate_qr_code(url), caption="📱 Scan to view performance", use_container_width=False)

                # Load results
                student_results = load_student_results(access_code_perf)

                if student_results:
                    # Format and sort data
                    data = [
                        {
                            "Class": r.class_name,
                            "Subject": r.subject,
                            "Score": r.score,
                            "Percentage": f"{r.percentage:.2f}%",
                            "Date": r.taken_at.strftime("%Y-%m-%d %H:%M"),
                        }
                        for r in sorted(student_results, key=lambda r: r.taken_at, reverse=True)
                    ]

                    df = pd.DataFrame(data)

                    # Apply color highlights
                    def highlight_score(val):
                        try:
                            num = float(val.strip('%'))
                            if num >= 70:
                                color = '#a6f1a6'  # Green for good
                            elif num >= 50:
                                color = '#fff6a6'  # Yellow for average
                            else:
                                color = '#f7a6a6'  # Red for poor
                            return f'background-color: {color}'
                        except Exception:
                            return ''

                    st.dataframe(
                        df.style.map(highlight_score, subset=['Percentage']),
                        use_container_width=True,
                        hide_index=True
                    )

                    # Download button
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "⬇️ Download My Results (CSV)",
                        csv,
                        f"{student_perf.name}_results.csv",
                        "text/csv",
                    )
                else:
                    st.info("No results found yet. 🕒")

    # ==============================
    # Auto-load results via QR URL
    # ==============================
    if "access_code" in query_params:
        access_code_query = query_params["access_code"]
        if isinstance(access_code_query, list):
            access_code_query = access_code_query[0]
        access_code_query = access_code_query.strip().upper()

        student_perf = get_student_by_access_code_db(access_code_query)
        if student_perf:
            st.success(f"👤 {student_perf.name} | Class: {student_perf.class_name}")
            results = load_student_results(access_code_query)

            if results:
                data = [
                    {
                        "Class": r.class_name,
                        "Subject": r.subject,
                        "Score": r.score,
                        "Percentage": f"{r.percentage:.2f}%",
                        "Date": r.taken_at.strftime("%Y-%m-%d %H:%M"),
                    }
                    for r in sorted(results, key=lambda r: r.taken_at, reverse=True)
                ]
                df = pd.DataFrame(data)

                st.dataframe(
                    df.style.applymap(
                        lambda val: (
                            'background-color: #a6f1a6' if float(val.strip('%')) >= 70
                            else 'background-color: #fff6a6' if float(val.strip('%')) >= 50
                            else 'background-color: #f7a6a6'
                        ),
                        subset=['Percentage']
                    ),
                    use_container_width=True,
                    hide_index=True
                )

                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "⬇️ Download My Results (CSV)",
                    csv,
                    f"{student_perf.name}_results.csv",
                    "text/csv",
                )
            else:
                st.info("No results found yet. 🕒")
        else:
            st.error("❌ Invalid Access Code.")

        # Optional: Quick Reset Button
        if st.session_state.get("logged_in"):
            if st.button("🔄 Refresh Test", key="refresh_update_state"):
                access_code = st.session_state.student.get("access_code", "").strip()
                subject = st.session_state.get("subject")

                # Clear session state
                for k in ["test_started", "submitted", "questions", "answers", "current_q",
                          "marked_for_review", "start_time", "duration", "five_min_warned",
                          "saved_to_db", "last_auto_save"]:
                    st.session_state.pop(k, None)

                # Clear DB progress
                if access_code and subject:
                    try:
                        clear_progress(access_code, subject)
                        st.success("Saved progress cleared from database.")
                    except Exception:
                        st.warning("Could not clear saved progress from DB — local state cleared only.")

                st.success("✅ Test has been cleared. You can start a new test.")
                st.rerun()

    # ==============================
    # Student Info
    # ==============================
    student = st.session_state.student
    st.info(get_student_display(student))
    # ------------------------------
    # Sync class & subject in session
    # ------------------------------
    # Ensure student's class and selected subject are set before fetching duration
    if "selected_class" in st.session_state:
        st.session_state.class_name = st.session_state.selected_class
    else:
        st.session_state.class_name = student.get("class_name")

    if "selected_subject" in st.session_state:
        st.session_state.subject = st.session_state.selected_subject

    # ------------------------------
    # Fetch enforced duration from DB (Admin set)
    # ------------------------------
    school_id = student.get("school_id", 1)
    class_name = st.session_state.get("class_name")
    subject = st.session_state.get("subject")

    if class_name and subject:
        st.session_state.duration = get_test_duration(class_name, subject, school_id)
        st.info(f"⏱ Test duration set to {int(st.session_state.duration)} minutes for {class_name} - {subject}")
    else:
        st.session_state.duration = None  # silently skip

    # ==============================
    # Subject Selection
    # ==============================
    subjects_list = {
        "jhs1": ["English", "Math", "Science", "History", "Geography", "Physics", "Chemistry", "Biology", "ICT", "Economics"],
        "jhs2": ["English", "Math", "Science", "History", "Geography", "Physics", "Chemistry", "Biology", "ICT", "Economics"],
        "jhs3": ["English", "Math", "Science", "History", "Geography", "Physics", "Chemistry", "Biology", "ICT", "Economics"],
    }
    class_name = student.get("class_name", "").strip().lower().replace(" ", "")
    subject_options = subjects_list.get(class_name, [])

    selected_subject = st.selectbox(
        "Select Subject",
        subject_options,
        key="subject_select",
        label_visibility="collapsed"
    )
    st.session_state.subject = selected_subject

    # -----------------------------
    # Show saved progress option (but do NOT auto-start)
    # -----------------------------
    access_code = student.get("access_code", "").strip()
    saved_progress = None
    if st.session_state.logged_in and selected_subject:
        try:
            saved_progress = load_progress(access_code, selected_subject)
        except Exception:
            saved_progress = None

    if saved_progress and not st.session_state.get("test_started", False):
        # Check if the test was already submitted
        if saved_progress.get("submitted", False):
            st.info("✅ You have already submitted this test. Retake is not allowed.")
        else:
            st.info("🕒 We found a saved test progress for this subject.")
            if st.button("▶️ Resume saved test", key=f"resume_{selected_subject}"):
                questions = saved_progress.get("questions", [])
                answers = saved_progress.get("answers", [])
                answers = _normalize_answers(answers, questions)

                # 🧹 Remove any leftover "Default" options
                for q in questions:
                    opts = q.get("options", [])
                    if "Default" in opts:
                        opts = [o for o in opts if o != "Default"]
                        q["options"] = opts

                st.session_state.update({
                    "test_started": True,
                    "submitted": False,  # ⚠️ force new session as active only for unsubmitted tests
                    "questions": questions,
                    "answers": answers,
                    "current_q": saved_progress.get("current_q", 0),
                    "duration": saved_progress.get("duration", 1800),
                    "start_time": saved_progress.get("start_time", time.time()),
                    "marked_for_review": set(saved_progress.get("marked_for_review", [])),
                    "saved_to_db": False
                })
                st.success("✅ Resumed previous test progress.")
                st.rerun()
            else:
                st.warning("✅ You have already submitted this test. Retake is not allowed.")


    # ==============================
    # Start Test (fresh) if no saved progress or user didn't press resume/startnew
    # ==============================
    if not st.session_state.get("test_started", False):
        if st.button("🚀 Start Test"):
            # Normal flow: start a fresh test (if saved_progress exists user should have used Resume/Start new)
            allowed, msg = can_take_test(access_code, selected_subject)
            if not allowed:
                st.error(f"{msg}")
                st.stop()

            try:
                decrement_retake(access_code, selected_subject)
            except Exception:
                pass

            class_name = student.get("class_name", "").strip()
            questions = load_questions_db(class_name, selected_subject, limit=30)
            if not questions:
                st.warning(f"No questions found for {class_name} / {selected_subject}.")
                st.stop()

            import random, json
            random.shuffle(questions)
            for q in questions:
                opts = q.get("options", [])
                if isinstance(opts, str):
                    try:
                        opts = json.loads(opts)
                        if not isinstance(opts, list):
                            opts = [opts]
                    except:
                        opts = [o.strip() for o in opts.split(",") if o.strip()]
                elif not isinstance(opts, list):
                    opts = [str(opts)]
                correct_text = str(q.get("answer", "")).strip()
                q["correct_answer_text"] = correct_text
                random.shuffle(opts)
                q["options"] = opts
                q["answer_index"] = opts.index(correct_text) if correct_text in opts else -1
                q.pop("answer", None)

            # ============================
            # Strictly use Admin-defined duration
            # ============================
            # Get class name safely from session or input
            student_class = st.session_state.student.get("class_name") if "student" in st.session_state else None
            if not student_class:
                student_class = st.session_state.get("selected_class")

            duration_secs = get_test_duration(
                class_name=student_class,
                subject=selected_subject,
                school_id=st.session_state.student.get("school_id", 1)
            )

            if not duration_secs or duration_secs <= 0:
                st.error(f"❌ No valid duration set for {selected_subject}. Please contact your Admin.")
                st.stop()

            # Initialize session state
            st.session_state.update({
                "test_id": str(uuid.uuid4()),
                "test_started": True,
                "submitted": False,
                "questions": questions,
                "answers": [-1] * len(questions),
                "current_q": 0,
                "marked_for_review": set(),
                "duration": duration_secs,
                "start_time": time.time(),
                "five_min_warned": False,
                "saved_to_db": False
            })
            st.success(f"Good Luck! Test started for {selected_subject}")
            st.rerun()

    # ==============================
    # Test In Progress
    # ==============================
    if st.session_state.get("test_started", False) and not st.session_state.get("submitted", False):
        questions = st.session_state.get("questions", [])
        if not questions:
            st.warning("⚠️ No questions loaded yet. Click 'Refresh Test' if this persists.")
            st.stop()

        # Defensive: ensure current_q and answers are valid
        if st.session_state.get("current_q", 0) >= len(questions):
            st.session_state.current_q = 0
        st.session_state.answers = _normalize_answers(st.session_state.get("answers", []), questions)

        # Render question tracker
        try:
            show_question_tracker(questions, st.session_state.answers)
        except Exception:
            pass

        # Timer
        start_time = st.session_state.get("start_time", time.time())
        duration_secs = st.session_state.get("duration", 1800)
        end_time = start_time + duration_secs
        remaining_secs = max(0, int(end_time - time.time()))
        hours, rem = divmod(remaining_secs, 3600)
        minutes, seconds = divmod(rem, 60)
        timer_str = f"{hours} hr {minutes:02d} min {seconds:02d} sec" if hours else f"{minutes:02d} min {seconds:02d} sec"
        st.markdown(f"### ⏳ Time Remaining: {timer_str}")

        # 5-minute warning
        if 295 < remaining_secs <= 300 and not st.session_state.get("five_min_warned", False):
            st.warning("⚠️ Only 5 minutes remaining!")
            st.session_state.five_min_warned = True

        # Auto-submit when time runs out
        if remaining_secs <= 0 and not st.session_state.get("submitted", False):
            st.error("⌛ Time's up! Auto-submitting your test…")
            st.session_state.submitted = True

            if not st.session_state.get("saved_to_db", False):
                try:
                    save_student_answers(
                        access_code=st.session_state.student["access_code"],
                        subject=st.session_state.subject,
                        questions=st.session_state.questions,
                        answers=st.session_state.answers
                    )
                    st.session_state.saved_to_db = True
                except Exception:
                    pass
            st.rerun()

        # Render question content
        render_test(questions, st.session_state.subject)

        # Auto-save progress every 60 seconds
        now = time.time()
        last_save = st.session_state.get("last_auto_save", 0)
        if now - last_save > 60:
            try:
                save_progress(
                    access_code=st.session_state.student["access_code"],
                    subject=st.session_state.subject,
                    questions=st.session_state.questions,
                    answers=st.session_state.answers,
                    current_q=st.session_state.current_q,
                    start_time=st.session_state.start_time,
                    duration=st.session_state.duration
                )
                st.session_state.last_auto_save = now
                st.toast("💾 Progress saved automatically!", icon="💾")
            except Exception as e:
                st.warning(f"⚠️ Could not auto-save progress: {e}")

    # ==============================
    # After Submission: Score Calculation + Feedback
    # ==============================
    if st.session_state.get("submitted", False):
        questions = st.session_state.get("questions", [])
        answers = st.session_state.get("answers", [])

        if not questions:
            st.warning("⚠️ No questions loaded. Please contact admin.")
            st.stop()

        details = []
        correct = 0
        import re

        def normalize_answer(ans: str) -> str:
            ans = str(ans).lower().strip()
            ans = ans.replace("×", "x").replace("÷", "/").replace("^2", "²")
            ans = ans.replace(" per ", "/")
            ans = re.sub(r"\s+", " ", ans)
            ans = re.sub(r"[^\w\s/.\-+]", "", ans)
            return ans

        for i, q in enumerate(questions):
            student_index = answers[i] if i < len(answers) else -1
            student_answer = q["options"][student_index] if 0 <= student_index < len(
                q.get("options", [])) else "No Answer"
            correct_answer = q.get("correct_answer_text", "N/A")

            sa = normalize_answer(student_answer)
            ca = normalize_answer(correct_answer)
            is_correct = sa == ca
            if is_correct:
                correct += 1
            details.append({
                "question": q.get("question", ""),
                "your_answer": student_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct
            })

        total_questions = len(questions)
        percent = (correct / total_questions * 100) if total_questions else 0

        # 🎉 Motivational Message
        if percent >= 80:
            st.success(f"🏆 Excellent work! You scored {percent:.1f}% — Outstanding performance!")
        elif percent >= 50:
            st.info(f"👍 Good job! You scored {percent:.1f}% — Keep practicing to improve.")
        else:
            st.warning(f"💪 Don’t give up! You scored {percent:.1f}% — Review and try again.")

        # Show summary
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.success(f"Score: {correct}/{total_questions} ({percent:.2f}%)")
        col1, col2 = st.columns(2)
        col1.success(f"✅ Correct: {correct}")
        col2.error(f"❌ Wrong: {total_questions - correct}")

        with st.expander("📋 View Answer Breakdown"):
            for i, d in enumerate(details, 1):
                color = "green" if d["is_correct"] else "red"
                st.markdown(
                    f"<p style='color:{color};'><b>Q{i}:</b> {d['question']}<br>"
                    f"Your Answer: <b>{d['your_answer']}</b><br>"
                    f"Correct: <b>{d['correct_answer']}</b></p>",
                    unsafe_allow_html=True
                )

        # Save results to DB (best-effort)
        if not st.session_state.get("saved_to_db", False):
            try:
                save_student_answers(
                    access_code=st.session_state.student["access_code"],
                    subject=st.session_state.subject,
                    questions=questions,
                    answers=answers
                )
                st.session_state.saved_to_db = True
            except Exception:
                pass

        # ✅ Generate PDF result with school info and logo
        school_name = st.session_state.get('school_name', 'Smart Test School')
        school_id = st.session_state.get('school_id', '—')

        pdf_bytes = generate_pdf(
            name=st.session_state.student['name'],
            class_name=st.session_state.student.get('class_name', ''),
            subject=st.session_state.subject,
            correct=correct,
            total=total_questions,
            percent=percent,
            details=details,
            school_name=school_name,
            school_id=school_id,
            logo_path="logo.png"
        )

        # 📥 Download button
        st.download_button(
            "📄 Download Result as PDF",
            data=pdf_bytes,
            file_name=f"result_{st.session_state.student['name']}_{st.session_state.subject}.pdf",
            mime="application/pdf",
            key="download_result_pdf"
        )

        # ✅ Return to Subject Selection
        if st.button("🔙 Return to Subject Selection"):
            # Keep login info but clear test session
            for key in [
                "submitted", "questions", "answers", "test_started", "saved_to_db",
                "subject", "current_q", "start_time", "duration", "five_min_warned"
            ]:
                st.session_state.pop(key, None)

            st.success("✅ Test completed — ready to choose another subject.")
            st.rerun()
