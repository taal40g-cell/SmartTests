import qrcode, io
import pandas as pd
from datetime import datetime, timedelta
import streamlit as st
from database import get_session
from models import StudentProgress
from ui import render_test, generate_pdf,get_test_type,get_subject_id_by_name
from helpers import get_subjective_questions,get_objective_questions,render_subjective_test,save_student_answers,get_subjective_questions,normalize_question
from db_helpers import (
    show_question_tracker,
    can_take_test,
    get_users,load_subjects,
    get_test_duration,load_student_results,
    get_student_by_access_code_db,
    decrement_retake,load_progress, save_progress, clear_progress,has_submitted_test
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
        "test_end_time": None,  # ✅ Add this line
        "five_min_warned": False,
        "saved_to_db": False,
        "last_auto_save": 0
    }

    for key, val in defaults.items():
        st.session_state.setdefault(key, val)


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

    # -------------------------
    # LOGIN (Access Code)
    # -------------------------
    if not st.session_state.get("logged_in", False):
        st.markdown("<div style='font-size:16px; font-weight:600;'>Enter Access Code:</div>", unsafe_allow_html=True)
        access_code_input = st.text_input("Access Code", placeholder="Code issued by Admin", key="access_code_input",
                                          label_visibility="collapsed")

        if access_code_input:
            access_code = access_code_input.strip().upper()
            student_obj = get_student_by_access_code_db(access_code)
            if not student_obj:
                st.error("Invalid login code ❌")
                st.stop()

            # Convert ORM -> dict
            student = {
                "id": student_obj.id,
                "name": student_obj.name,
                "class_name": getattr(student_obj, "class_name", "") or "",
                "access_code": access_code,
                "can_retake": bool(getattr(student_obj, "can_retake", True)),
                "school_id": getattr(student_obj, "school_id", None)
            }


            # Persist in session
            st.session_state.update({
                "logged_in": True,
                "student": student,
                "class_name": student["class_name"],
                "school_id": student["school_id"],  # ✅ CRITICAL FIX
                "student_id": student["id"],  # ✅ CRITICAL FIX
            })

            # Reset stale session vars
            for k in ["test_started", "submitted", "questions", "answers", "current_q",
                      "marked_for_review", "start_time", "duration", "saved_to_db",
                      "test_phase", "test_type"]:
                st.session_state.pop(k, None)

            st.success(f"Welcome, {student['name']} — Class: {student['class_name']}")
            st.rerun()

        st.stop()

    # -------------------------
    # Sidebar: Past Performance
    # -------------------------
    with st.sidebar:
        st.header("📊 Past Performance")
        perf_code = st.text_input("Enter Access Code", key="sidebar_access_code")

        def gen_qr(data):
            qr = qrcode.QRCode(version=1, box_size=6, border=2)
            qr.add_data(data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, "PNG")
            buf.seek(0)
            return buf

        APP_URL = "https://smarttests-1.onrender.com"

        if perf_code:
            perf_code = perf_code.strip().upper()
            stud = get_student_by_access_code_db(perf_code)
            if not stud:
                st.error("Invalid access code")
            else:
                st.success(f"{stud.name} — {stud.class_name}")
                st.image(gen_qr(f"{APP_URL}?access_code={perf_code}"))

                results = load_student_results(perf_code)
                if results:
                    df = pd.DataFrame([{
                        "Class": r.class_name,
                        "Subject": r.subject,
                        "Score": r.score,
                        "Percentage": f"{r.percentage:.2f}%",
                        "Date": r.taken_at.strftime("%Y-%m-%d %H:%M")
                    } for r in sorted(results, key=lambda x: x.taken_at, reverse=True)])

                    def color_pct(val):
                        try:
                            n = float(val.strip('%'))
                            if n >= 70: return 'background-color: #a6f1a6'
                            if n >= 50: return 'background-color: #fff6a6'
                            return 'background-color: #f7a6a6'
                        except Exception:
                            return ''

                    st.dataframe(df.style.applymap(color_pct, subset=['Percentage']), use_container_width=True)
                    st.download_button("⬇️ Download CSV", df.to_csv(index=False).encode(), "results.csv", "text/csv")
                else:
                    st.info("No results yet.")

                if st.button("🔄 Refresh Test (Clear Progress)"):
                    for k in ["test_started", "submitted", "questions", "answers", "current_q",
                              "marked_for_review", "start_time", "duration", "saved_to_db"]:
                        st.session_state.pop(k, None)

                    try:
                        subject_id = get_subject_id_by_name(st.session_state.get("subject"))
                        if subject_id is None:
                            raise ValueError("Could not find subject ID.")

                        clear_progress(
                            perf_code,
                            subject_id,
                            school_id=st.session_state.get("school_id")
                        )
                        st.success("Progress cleared from DB.")
                    except Exception as e:
                        st.warning(f"Could not clear DB progress: {e}")

                    st.success("Local session cleared. Start new test.")
                    st.rerun()

    # -------------------------
    # Main Student UI
    # -------------------------
    student = st.session_state.get("student", {})
    class_name = st.session_state.get("class_name") or student.get("class_name") or ""
    school_id = str(student.get("school_id", ""))  # Ensure string

    if not class_name:
        st.error("Class not set for student — contact admin.")
        st.stop()

    # -------------------------
    # Load subjects once and cache in session_state
    # -------------------------
    if "subjects" not in st.session_state:
        try:
            st.session_state.subjects = load_subjects(class_name, school_id)
        except Exception as e:
            st.error(f"Failed to load subjects: {e}")
            st.session_state.subjects = []

    subjects = st.session_state.subjects

    # 🔍 DEBUG — show what subjects actually contain
    st.write("DEBUG subjects =", subjects)

    if not subjects:
        st.warning("No subjects available for your class. Contact admin.")
        st.stop()


    # -------------------------
    # 1️⃣ Select Subject
    # -------------------------
    st.markdown("#### 📘 Select Subject")

    # Build mapping: name -> id
    subject_map = {s["name"]: s["id"] for s in subjects if isinstance(s, dict)}
    subject_options = list(subject_map.keys())
    selected_subject = st.selectbox("Subject", subject_options, key="subject_select_box")
    st.session_state.subject = selected_subject

    # Get integer subject ID
    selected_subject_id = subject_map.get(selected_subject)
    if selected_subject_id is None:
        st.error(f"❌ Subject ID not found for '{selected_subject}'")
        st.stop()

    # -------------------------
    # 2️⃣ Load Questions
    # -------------------------
    st.session_state.class_name = class_name
    school_id_int = int(school_id) if school_id else None

    key_obj = f"objective_{class_name}_{selected_subject_id}_{school_id_int}"
    key_subj = f"subjective_{class_name}_{selected_subject_id}_{school_id_int}"

    if key_obj not in st.session_state:
        st.session_state[key_obj] = get_objective_questions(class_name, selected_subject_id, school_id_int) or []

    if key_subj not in st.session_state:
        st.session_state[key_subj] = get_subjective_questions(class_name, selected_subject_id, school_id_int) or []

    objective_questions = st.session_state[key_obj]
    subjective_questions = st.session_state[key_subj]

    # -------------------------
    # 3️⃣ Choose Test Type
    # -------------------------
    test_options = ["Objective", "Subjective"]
    if not objective_questions:
        test_options[0] += " (No questions)"
    if not subjective_questions:
        test_options[1] += " (No questions)"

    st.markdown(
        """
        <div style='display:inline-block; font-size:20px; font-weight:bold;
        color:#f3f6f6; border-bottom:4px solid #4CAF50; padding-bottom:2px; margin-bottom:10px;'>
        🧩 Choose Test Type
        </div>
        """, unsafe_allow_html=True
    )

    test_choice = st.radio(
        "Choose type",
        test_options,
        index=0,
        horizontal=True,
        key=f"test_type_radio_{class_name}_{selected_subject}"
    )

    st.session_state.test_type = "objective" if "objective" in test_choice.lower() else "subjective"
    st.session_state.test_phase = st.session_state.test_type

    # -------------------------
    # 4️⃣ Load / Create Student Progress  (FIXED)
    # -------------------------
    access_code = st.session_state.student.get("access_code", "").strip()
    student_info = st.session_state.get("student")

    if not student_info or not student_info.get("id"):
        st.error("❌ Student ID missing. Please log in again.")
        st.stop()

    student_id = student_info["id"]

    # Load saved progress using subject_id
    saved_progress = load_progress(
        access_code,
        selected_subject_id,  # ✅ FIXED
        school_id=school_id_int,
        test_type=st.session_state.test_type
    ) if access_code else None

    db = get_session()
    try:
        record_query = db.query(StudentProgress).filter_by(
            student_id=student_id,
            access_code=access_code,
            subject_id=selected_subject_id,  # ✅ correct
            test_type=st.session_state.test_type,
            school_id=school_id_int,
        )

        record = record_query.first()

        if not record:
            record = StudentProgress(
                student_id=student_id,
                access_code=access_code,
                subject_id=selected_subject_id,  # ✅ FIXED
                answers=[],
                current_q=0,
                start_time=datetime.now().timestamp(),
                duration=30 * 60,
                questions=[],
                school_id=school_id_int,
                test_type=st.session_state.test_type,
                submitted=False
            )
            db.add(record)
            db.commit()

    finally:
        db.close()

    # -------------------------
    # 5️⃣ Determine test type (unchanged)
    # -------------------------
    selected_test_mode = st.session_state.get("selected_test_mode") or "Objective"
    test_type = "objective" if selected_test_mode.lower().startswith("obj") else "subjective"

    # -------------------------
    # 5️⃣ Start / Resume Logic (FIXED)
    # -------------------------
    col1, col2 = st.columns(2)

    start_clicked = col1.button("🚀 Start Test", key=f"start_btn_{selected_subject_id}")
    resume_clicked = False

    # Check if student already submitted this test
    already_done = has_submitted_test(
        access_code,
        selected_subject_id,
        school_id_int,
        test_type
    )

    if already_done:
        if can_take_test(access_code, selected_subject_id, school_id_int):  # ✅ uses ID now
            st.success("🔁 Retake allowed by Admin.")
        else:
            st.error("❌ You have already completed this test.")
            st.stop()

    # Allow resume only if previous attempt NOT submitted
    if saved_progress and not saved_progress.get("submitted", False):
        resume_clicked = col2.button("🔄 Resume Test", key=f"resume_btn_{selected_subject_id}")

    # -------------------------
    # 6️⃣ Fresh Start / Resume
    # -------------------------
    if start_clicked or resume_clicked or st.session_state.get("test_started"):
        st.session_state.test_started = True
        duration_minutes = get_test_duration(class_name=class_name, subject=selected_subject,
                                             school_id=school_id_int) or 30

        if start_clicked or "questions" not in st.session_state:
            st.session_state.questions = objective_questions if st.session_state.test_type == "objective" else subjective_questions
            st.session_state.answers = [""] * len(st.session_state.questions)
            st.session_state.current_q = 0
            st.session_state.start_time = datetime.now()
            st.session_state.duration = duration_minutes * 60
            st.session_state.test_end_time = st.session_state.start_time + timedelta(seconds=st.session_state.duration)
            st.session_state.marked_for_review = set()

        # --------------------------------------------
        # 🟩 Resume Test (Continue from save)
        # --------------------------------------------
        if resume_clicked and saved_progress:
            saved_questions = saved_progress.get("questions", [])

            # Ensure questions is a list
            if isinstance(saved_questions, str):
                import json
                try:
                    saved_questions = json.loads(saved_questions)
                except json.JSONDecodeError:
                    saved_questions = []

            st.session_state.questions = saved_questions or st.session_state.questions

            st.session_state.answers = saved_progress.get(
                "answers", [""] * len(st.session_state.questions)
            )
            st.session_state.current_q = saved_progress.get("current_q", 0)

            # Clamp current_q
            st.session_state.current_q = min(max(st.session_state.current_q, 0), len(st.session_state.questions) - 1)

            saved_start_time = saved_progress.get("start_time")
            if saved_start_time:
                st.session_state.start_time = datetime.fromtimestamp(saved_start_time)
            else:
                st.session_state.start_time = datetime.now()

            st.session_state.duration = saved_progress.get(
                "duration", duration_minutes * 60
            )

            st.session_state.test_end_time = (
                    st.session_state.start_time + timedelta(seconds=st.session_state.duration)
            )


        import re

        # -------------------------
        # Safe options parser + cleaner
        # -------------------------
        def parse_options(raw_options):
            if isinstance(raw_options, list):
                opts = raw_options
            elif isinstance(raw_options, str):
                cleaned = raw_options.strip()
                try:
                    parsed = json.loads(cleaned)
                    opts = parsed if isinstance(parsed, list) else [str(parsed)]
                except Exception:
                    opts = [o.strip() for o in cleaned.replace(";", ",").split(",") if o.strip()]
            else:
                opts = []

            def clean_option(opt):
                text = str(opt).strip()
                text = text.strip('"').strip("'")
                for bad in ["(", ")", "[", "]", "{", "}"]:
                    text = text.replace(bad, "")
                text = text.replace("\n", " ").strip()
                text = " ".join(text.split())
                return text

            return [clean_option(o) for o in opts]

        # -------------------------
        # Safe field getter
        # -------------------------
        def field(obj, name, default=None):
            if isinstance(obj, dict):
                return obj.get(name, default)
            return getattr(obj, name, default)

            # -------------------------
            # Render current question
            # -------------------------

        questions = st.session_state.questions
        current_q_idx = st.session_state.current_q

        if not questions:
            st.warning("⚠️ No questions available for this test.")
            st.stop()

        current_q_idx = min(max(current_q_idx, 0), len(questions) - 1)
        st.session_state.current_q = current_q_idx
        show_question_tracker(st.session_state.questions, st.session_state.current_q, st.session_state.answers)

        q = questions[current_q_idx]
        question_text = field(q, "question_text") or field(q, "question") or "No question text"
        st.markdown(f"**Q{current_q_idx + 1}: {question_text}**")

        # -------------------------
        # Options (clean + placeholder)
        # -------------------------
        raw_options = field(q, "options", [])
        options = parse_options(raw_options)

        # Clean: remove quotes
        clean_options = [str(opt).strip().strip('"').strip("'") for opt in options]

        # Add placeholder
        choices = ["Choose answer"] + clean_options

        # Ensure answers list is sized
        while len(st.session_state.answers) <= current_q_idx:
            st.session_state.answers.append("")

        prev_answer = st.session_state.answers[current_q_idx]

        # Determine which index should be selected
        selected_index = choices.index(prev_answer) if prev_answer in choices else 0

        # -------------------------
        # Radio button
        # -------------------------
        selected_option = st.radio(
            "Choose an option:",
            choices,
            index=selected_index,
            key=f"q_{current_q_idx}"
        )

        # Save answer (ignore placeholder)
        if selected_option == "Choose answer":
            st.session_state.answers[current_q_idx] = ""
        else:
            st.session_state.answers[current_q_idx] = selected_option

        # -------------------------
        # Navigation buttons
        # -------------------------
        col1, col2, col3 = st.columns([1, 1, 1])

        with col1:
            if st.button("⬅️ Previous", disabled=current_q_idx == 0, key=f"prev_{current_q_idx}"):
                st.session_state.current_q = max(0, current_q_idx - 1)
                st.rerun()

        with col2:
            if st.button("➡️ Next", disabled=current_q_idx == len(questions) - 1, key=f"next_{current_q_idx}"):
                st.session_state.current_q = min(len(questions) - 1, current_q_idx + 1)
                st.rerun()

        with col3:
            if st.button("✅ Submit Test", key=f"submit_{current_q_idx}"):
                st.session_state.submitted = True

                start_time_ts = (
                    st.session_state.start_time.timestamp()
                    if isinstance(st.session_state.start_time, datetime)
                    else st.session_state.start_time
                )

                # Convert subject name → subject_id
                subject_id = next(
                    (s["id"] for s in st.session_state.subjects if s["name"] == selected_subject),
                    None
                )

                if subject_id is None:
                    st.error(f"Could not find subject ID for '{selected_subject}'")
                    st.stop()

                save_progress(
                    access_code=access_code,
                    subject_id=subject_id,  # ✅ pass ID, not name
                    answers=st.session_state.answers,
                    current_q=st.session_state.current_q,
                    start_time=start_time_ts,
                    duration=st.session_state.duration,
                    questions=st.session_state.questions,
                    school_id=school_id,
                    test_type=st.session_state.test_type,
                    submitted=True
                )

                # Show final message and lock the test
                mins, secs = divmod(0, 60)
                st.markdown(
                    f"<div style='text-align:right; font-size:20px; color:#f44336;'>⏱️ Time Left: {mins:02d}:{secs:02d}</div>",
                    unsafe_allow_html=True
                )

                st.success("✅ Test submitted successfully!")
                st.warning("⛔ Retake not allowed. Please contact your teacher.")

                # 🔒 Lock down the entire test interface
                st.session_state.test_started = False
                st.session_state.questions = []
                st.session_state.answers = []

                st.stop()
