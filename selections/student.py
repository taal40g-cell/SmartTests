import json
import random
from datetime import datetime, timedelta,timezone
import streamlit as st
from sqlalchemy.orm import joinedload
# Backend modules
from backend.models import Student
from backend.database import get_session
from backend.ui import  generate_pdf,reset_test_state
from backend.helpers import (
    get_subjective_questions,
    get_objective_questions,
    save_answer,normalize_question,
    handle_subjective_submission,
    render_student_login,
    render_results_center,
    render_start_resume_controls,
    handle_test_actions,
    get_duration_minutes,
    get_or_create_student_progress,
    load_question_cache,finalize_submission,
    render_test_type_selector,persist_progress,
    render_test_entry_controls,persist_progress

)
from backend.db_helpers import (
    show_question_tracker,
    can_take_test,
    get_users,
    load_subjects,
    get_test_duration,
    get_student_by_access_code,
    load_progress,
    save_progress,parse_options,field,
    decrement_retake,normalize_subjective,normalize_objective,
    log_violation,is_answered
)
from backend.models import (SubjectiveQuestion,AntiCheatLog,TestResult,School,
StudentProgress,Class,StudentAnswer)


# -------------------------
# Confirm Submission Dialog
# Define ONCE
# -------------------------
@st.dialog("⚠️ Confirm Submission")
def confirm_submit_dialog():
    unanswered = st.session_state.get(
        "unanswered",
        0
    )

    st.write(
        f"You have **{unanswered} unanswered questions.**"
    )

    st.write(
        "Do you want to submit anyway?"
    )

    col1, col2 = st.columns(2)

    with col1:

        if st.button("✅ Submit Anyway", key="confirm_submit_anyway"):
            st.session_state.confirm_submit = False
            st.session_state.final_submit = True
            st.rerun()

    with col2:

        if st.button("🚫 Go Back to Test", key="go_back_test"):
            st.session_state.confirm_submit = False
            st.rerun()



# ==============================
# Main Student Mode
# ==============================
def run_student_mode():


    import time

    page_start = time.time()

    @st.cache_data(ttl=300)
    def cached_users():
        return get_users()

    if "users_dict" not in st.session_state:
        st.session_state.users_dict = cached_users()

    users_dict = st.session_state.users_dict


    # =============================
    # SHOW SUBMISSION SUCCESS PAGE
    # =============================
    if st.session_state.get("show_submission_message"):
        st.balloons()

        st.markdown(
        """
        <div style="
            text-align:center;
            padding:40px;
            border-radius:12px;
            background-color:#f0f9f4;
            border:1px solid #c8e6c9;
        ">
            <h1>🎉 Test Submitted Successfully!</h1>

            <p style="font-size:18px;">
            🙌 Thank you for completing your test.
            </p>

            <p style="font-size:16px;">
            Your answers have been safely submitted and will be reviewed by your teacher.
            </p>

            <p style="font-size:16px;">
            🧑‍🏫 Once grading is complete, your results will appear in your
            <b>Performance Dashboard</b>.
            </p>

            <p style="font-size:16px;">
            Great effort — keep learning and improving! 🚀
            </p>
        </div>
        """,
        unsafe_allow_html=True
        )

        st.write("")

        if st.button("⬅ Return to Test Portal", key="return_test_portal"):
            st.session_state.show_submission_message = False
            st.rerun()

        st.stop()


    # -----------------------------
    # Initialize session defaults
    # -----------------------------
    defaults = {
        "test_started": False,
        "submitted": False,
        "logged_in": False,
        "student": {},
        "answers": {},  # dict keyed by question_id
        "current_q": 0,
        "current_page": 0,
        "questions": [],
        "subject": None,
        "marked_for_review": set(),  # IMPORTANT FIX (not list)
        "duration": None,
        "start_time": None,
        "test_end_time": None,
        "five_min_warned": False,
        "saved_to_db": False,
        "last_auto_save": 0
    }

    for key, val in defaults.items():
        st.session_state.setdefault(key, val)

    # -------------------------
    # Session state defaults
    # -------------------------

    st.session_state.setdefault("confirm_submit", False)
    st.session_state.setdefault("final_submit", False)
    st.session_state.setdefault("answered_count", 0)
    st.session_state.setdefault("unanswered", 0)

    # -------------------------
    # Navigation core state (MISSING PIECE)
    # -------------------------
    st.session_state.setdefault("current_q", 0)
    st.session_state.setdefault("answers", {})
    st.session_state.setdefault("questions", [])

    # -------------------------
    # Identity (IMPORTANT for persist_progress)
    # -------------------------
    st.session_state.setdefault("access_code", None)
    st.session_state.setdefault("student_id", None)
    st.session_state.setdefault("subject_id", None)
    st.session_state.setdefault("class_id", None)
    st.session_state.setdefault("school_id", None)


    # -----------------------------
    # Student Hub Header
    # -----------------------------
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

    # -----------------------------
    # Header & Banner
    # -----------------------------
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

    # -----------------------------
    # CSS Styling
    # -----------------------------
    st.markdown("""
    <style>
    .small-input input, .small-input select {
        width: 150px !important;
        padding: 6px;
        font-size: 14px;
    }

    div[data-baseweb="input"],
    div[data-baseweb="select"] {
        width: 220px !important;
        margin-left: 0 !important;
    }

    .card {
        padding: 1rem;
        margin-top: 0.8rem;
        border-radius: 10px;
        border: 1px solid #ddd;
        background-color: #fafafa;
        box-shadow: 1px 1px 4px rgba(0,0,0,0.08);
    }
    </style>
    """, unsafe_allow_html=True)

    # =========================================================
    # 👨‍🎓 STUDENT MODE ENTRY POINT
    # =========================================================

    # Show login page if needed
    render_student_login()

    # Use session as source of truth
    student = st.session_state.get("student")

    if not student:
        st.info("🚫 Student session not initialized.")
        st.stop()

    school_id = student.get("school_id")
    class_id = student.get("class_id")

    if not school_id or not class_id:
        st.info("🚫 Student is missing school or class assignment.")
        st.stop()

    school_id_int = int(school_id)
    class_id_int = int(class_id)

    # =========================================================
    # 🚀 PRE-TEST SETUP
    # Only execute before a test starts
    # =========================================================
    if not st.session_state.get("test_started", False):

        # -----------------------------------------------------
        # 📊 Results Center
        # -----------------------------------------------------
        render_results_center()

        # -----------------------------------------------------
        # 📦 Load Classes (Cached)
        # -----------------------------------------------------
        if "classes" not in st.session_state:
            db = get_session()

            try:
                classes = db.query(Class).all()

                st.session_state.classes = [
                    {
                        "id": c.id,
                        "name": c.name
                    }
                    for c in classes
                ]

            finally:
                db.close()

        # -----------------------------------------------------
        # 📚 Load Subjects (Cached)
        # -----------------------------------------------------
        if "subjects" not in st.session_state:
            try:
                st.session_state.subjects = load_subjects(
                    school_id=school_id_int,
                    class_id=class_id_int
                )

            except Exception as e:
                st.error(f"Failed to load subjects: {e}")
                st.session_state.subjects = []

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
        st.info(f"🚫 Subject ID not found for '{selected_subject}'")
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
            "test_started" in st.session_state
            and st.session_state.test_started
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


    # -------------------------
    # 👤 VALIDATE STUDENT
    # -------------------------
    student_info = st.session_state.get("student")
    access_code = st.session_state.student.get("access_code", "").strip()

    if not student_info or not student_info.get("id"):
        st.info("🚫 Student ID missing. Please log in again.")
        st.stop()

    student_id = student_info["id"]

    print("CURRENT TEST TYPE:", st.session_state.test_type)
    print(">>> LOADING STUDENT PROGRESS")
    record = get_or_create_student_progress(
        student_id=student_id,
        access_code=access_code,
        subject_id=selected_subject_id,
        class_id=class_id_int,
        school_id=school_id_int,
        test_type=st.session_state.test_type
    )


    print("DATABASE RECORD")
    print(record)
    print("LOCKED:", record.get("locked"))
    print("SUBMITTED:", record.get("submitted"))

    print(">>> STUDENT PROGRESS LOADED")
    is_locked = record.get("locked", False)
    is_submitted = record.get("submitted", False)



    # -------------------------
    # 🔁 RETAKE LOGIC
    # -------------------------
    retake_allowed = can_take_test(
        student_id,
        selected_subject_id,
        school_id_int,
        st.session_state.test_type
    )

    # -------------------------
    # 🚦 START BUTTON STATE
    # -------------------------
    saved_progress = None

    if not st.session_state.test_started:
        saved_progress = render_test_entry_controls(
            access_code=access_code,
            subject_id=selected_subject_id,
            class_id=class_id_int,
            school_id=school_id_int,
            student_id=student_id,
            test_type=st.session_state.test_type,
            is_submitted=is_submitted,
            is_locked=is_locked,
            retake_allowed=retake_allowed
        )



    # -------------------------
    # 🧠 UX LABELS
    # -------------------------
    if is_submitted and not retake_allowed:
        st.caption("📌 Test submitted. Retake not permitted.")
    elif is_locked and retake_allowed:
        st.caption("🔁 Retake available.")


    # -------------------------
    # 🎯 MAIN TEST FLOW
    # -------------------------
    if st.session_state.get("test_started"):

        action = st.session_state.get("test_action")

        duration_minutes = get_duration_minutes(
            class_id=class_id,
            subject_id=selected_subject_id,
            school_id=school_id_int
        )



# -----------------------------------
# start test
# -----------------------------------

        if action == "start":

            # -------------------------
            # Get question bank
            # -------------------------
            t0 = time.time()

            question_bank = (
                objective_questions
                if st.session_state.test_type == "objective"
                else subjective_questions
            )

            question_bank = list(question_bank)
            random.shuffle(question_bank)



            # -------------------------
            # Normalize questions
            # -------------------------
            normalized_questions = [
                normalize_question(q)
                for q in question_bank
            ]



            # ✅ SAVE RANDOMIZED ORDER
            st.session_state.questions = normalized_questions
            st.session_state.test_started = True


            # -------------------------
            # Reset state
            # -------------------------
            st.session_state.answers = {
                str(q["id"]): ""
                for q in normalized_questions
            }

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

            # -------------------------
            # Save progress (UPDATED FIXED VERSION)
            # -------------------------
            t0 = time.time()

            # 🔥 IMPORTANT: DO NOT rebuild/reset answers here
            answers = st.session_state.get("answers", {})
            if not isinstance(answers, dict):
                answers = {}

            save_progress(
                access_code=access_code,
                subject_id=selected_subject_id,
                class_id=class_id_int,
                school_id=school_id_int,
                test_type=st.session_state.test_type,

                answers=answers,

                current_q=st.session_state.current_q,

                start_time=st.session_state.start_time,

                duration=st.session_state.duration,

                questions=[
                    q["id"]
                    for q in normalized_questions
                ],

                student_id=student_id,

                submitted=False
            )



            st.session_state.test_action = None

            st.rerun()


        # -------------------------
        # 🟩 RESUME TEST
        # -------------------------
        elif action == "resume":

            t0 = time.time()

            saved_progress = load_progress(
                access_code=access_code,
                subject_id=selected_subject_id,
                class_id=class_id_int,
                school_id=school_id_int,
                test_type=st.session_state.test_type,
                student_id=student_id
            )

            if not saved_progress:
                st.warning("⚠️ No unfinished test to resume.")
                st.session_state.test_started = False
                st.session_state.test_action = None
                st.stop()

            if saved_progress.get("submitted", False):
                st.warning("⚠️ This test was already submitted.")
                st.stop()

            # -------------------------
            # TIME RESTORE
            # -------------------------
            start_time = saved_progress.get("start_time")
            duration = saved_progress.get("duration", 0)

            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time)
            elif isinstance(start_time, (int, float)):
                start_time = datetime.fromtimestamp(start_time)

            st.session_state.start_time = start_time
            st.session_state.duration = int(duration)

            st.session_state.test_end_time = start_time + timedelta(seconds=int(duration))

            # -------------------------
            # QUESTIONS (IMPORTANT)
            # -------------------------
            saved_questions = saved_progress.get("questions", [])

            if isinstance(saved_questions, str):
                try:
                    saved_questions = json.loads(saved_questions)
                except:
                    saved_questions = []

            # Load the full question bank
            question_bank = (
                objective_questions
                if st.session_state.test_type == "objective"
                else subjective_questions
            )

            # Normalize every question
            normalized_questions = [
                normalize_question(q)
                for q in question_bank
            ]

            # Build lookup table
            question_map = {
                q["id"]: q
                for q in normalized_questions
            }

            # Rebuild full question objects
            rebuilt_questions = [
                question_map[qid]
                for qid in saved_questions
                if qid in question_map
            ]

            # Fallback if something went wrong
            if rebuilt_questions:
                st.session_state.questions = rebuilt_questions
            else:
                st.session_state.questions = normalized_questions

            # -------------------------
            # CURRENT QUESTION (FIXED RESET ISSUE)
            # -------------------------
            saved_current_q = int(saved_progress.get("current_q") or 0)

            # 🔥 ALWAYS restore (REMOVE resume flag logic)
            st.session_state.current_q = saved_current_q

            # -------------------------
            # ANSWERS RESTORE
            # -------------------------
            saved_answers = saved_progress.get("answers", {})

            if isinstance(saved_answers, str):
                try:
                    saved_answers = json.loads(saved_answers)
                except:
                    saved_answers = {}

            if not isinstance(saved_answers, dict):
                saved_answers = {}

            st.session_state.answers = {
                str(k): (v.get("selected") if isinstance(v, dict) else v)
                for k, v in saved_answers.items()
            }

            # -------------------------
            # FLAGS
            # -------------------------
            st.session_state.resumed = True
            st.session_state.test_started = True
            st.session_state.test_action = None



        # -------------------------
        # ⏱️ TIMER
        # -------------------------
        if not isinstance(st.session_state.start_time, datetime):
            st.error(
                f"Invalid start_time: {st.session_state.start_time}"
            )
            st.stop()

        now_ts = datetime.now().timestamp()
        start_ts = st.session_state.start_time.timestamp()

        elapsed = now_ts - start_ts
        remaining = st.session_state.duration - elapsed

        mins = int(remaining // 60)
        secs = int(remaining % 60)

        # -------------------------
        # 🔴 AUTO SUBMIT
        # -------------------------
        if remaining <= 0:

            if not st.session_state.get("auto_submitted", False):
                st.warning("⏰ Time is up! Submitting your test automatically...")

                st.session_state.auto_submitted = True
                st.session_state.final_submit = True

                st.rerun()

        # ✅ AUTO-INITIALIZE TEST (CRITICAL FIX)
        if (
                st.session_state.get("test_started")
                and not st.session_state.get("test_end_time")
                and not st.session_state.get("resumed", False)
        ):
            st.warning("AUTO INITIALIZE EXECUTED")
            duration_minutes = get_test_duration(
                class_id=class_id,
                subject_id=selected_subject_id,
                school_id=school_id_int
            ) or 30

            st.session_state.questions = (
                objective_questions
                if st.session_state.test_type == "objective"
                else subjective_questions
            )

            if not st.session_state.get("resumed", False):
                st.session_state.answers = {
                    str(q["id"]): ""
                    for q in st.session_state.questions
                }

            st.session_state.current_q = 0
            st.session_state.start_time = datetime.now()
            st.session_state.duration = duration_minutes * 60

            st.session_state.test_end_time = (
                    st.session_state.start_time +
                    timedelta(seconds=st.session_state.duration)
            )

            st.session_state.marked_for_review = set()
            st.session_state.paste_count = 0




        # =============================
        # ⏱️ TIMER (BEFORE RENDER)
        # =============================
        now = datetime.now()

        # ✅ FIX: ensure test is initialized
        if "test_end_time" not in st.session_state:
            st.session_state.test_end_time = datetime.now() + timedelta(minutes=30)

        if "start_time" not in st.session_state:
            st.session_state.start_time = datetime.now()

        remaining_seconds = int(
            (st.session_state.test_end_time - now).total_seconds()
        )
        if remaining_seconds < 0:
            remaining_seconds = 0

        time_up = remaining_seconds <= 0

        mins, secs = divmod(remaining_seconds, 60)

        # UI color only (no logic change)
        timer_border_color = "red" if remaining_seconds <= 60 else "green"

        st.markdown(
            f"""
            <div style="
                padding: 6px 8px;
                border-radius: 8px;
                background-image: url('YOUR_IMAGE_URL_HERE');
                background-size: cover;
                background-position: center;
                border: 2px solid {timer_border_color};
                color: #111827;
                text-align: center;
                font-size: 16px;
                font-weight: 600;
                margin-bottom: 8px;
                box-shadow: 0 2px 6px rgba(0,0,0,0.15);
            ">
                ⏱️ Time Remaining: {mins:02d}:{secs:02d}
            </div>
            """,
            unsafe_allow_html=True
        )

        answers = st.session_state.get("answers", {})

        # -------------------------
        # FORCE DICT (CRITICAL FIX)
        # -------------------------
        if isinstance(answers, list):
            answers = {
                str(i): a
                for i, a in enumerate(answers)
            }

        if not isinstance(answers, dict):
            answers = {}

        # 🔥 IMPORTANT: persist back to session state
        st.session_state.answers = answers

        # -------------------------
        # Progress calculation
        # -------------------------
        total_questions = len(st.session_state.questions)

        answered = 0

        for q in st.session_state.questions:

            qid = str(q["id"])

            ans = st.session_state.answers.get(qid, "")

            # support dict answer format
            if isinstance(ans, dict):
                value = ans.get("selected", "")
            else:
                value = ans

            if str(value).strip():
                answered += 1

        percent = (
            round(answered * 100 / total_questions)
            if total_questions > 0
            else 0
        )

        st.markdown(
            f"""
            <div style="
                padding: 6px 10px;
                border-radius: 8px;
                background-color: #7abaa1;
                border: 2px solid {timer_border_color};
                color: #111827;
                text-align: center;
                font-size: 16px;
                font-weight: 600;
                margin-bottom: 8px;
                box-shadow: 0 2px 6px rgba(0,0,0,0.15);
            ">
                📊 Progress: {answered}/{total_questions} answered — {percent}%
            </div>
            """,
            unsafe_allow_html=True
        )



        # -------------------------
        # Render current question
        # -------------------------
        questions = st.session_state.questions
        current_q_idx = st.session_state.current_q


        if not questions:
            st.warning("🚨 Questions failed to load. Check upload or loader.")
            st.stop()



        # ✅ SAFE NOW
        show_question_tracker(
            st.session_state.questions,
            st.session_state.current_q,
            st.session_state.answers
        )

        # -------------------------
        # DEBUG
        # -------------------------


        q = questions[current_q_idx]
        question_text = q.get("text", "No question text")
        st.markdown(
            f"""
            <div class="question-text">
                Q{current_q_idx + 1}: {question_text}
            </div>
            """,
            unsafe_allow_html=True
        )

        # -------------------------
        # Answer input (OBJECTIVE vs SUBJECTIVE)
        # -------------------------
        question_type = field(q, "question_type", st.session_state.test_type)

        # Ensure answer exists for this question (DICT-BASED)
        question_id = str(q["id"])

        if question_id not in st.session_state.answers:

            question_id = str(q["id"])

            if not isinstance(st.session_state.answers, dict):
                st.session_state.answers = {}

            if question_id not in st.session_state.answers:
                st.session_state.answers[question_id] = ""

        # Get previous answer safely
        prev_answer = st.session_state.answers.get(question_id, "")


        # -------------------------
        # 🟦 OBJECTIVE QUESTION
        # -------------------------
        if question_type == "objective":

            raw_options = field(q, "options", [])
            options = parse_options(raw_options)

            clean_options = [
                str(opt).strip().strip('"').strip("'")
                for opt in options
            ]

            choices = ["Choose answer"] + clean_options

            selected_index = (
                choices.index(prev_answer)
                if prev_answer in choices
                else 0
            )

            selected_option = st.radio(
                "Choose an option:",
                choices,
                index=selected_index,
                key=f"q_{current_q_idx}",
                disabled=time_up or st.session_state.get("submitted", False)
            )

            st.session_state.answers[question_id] = (
                ""
                if selected_option == "Choose answer"
                else selected_option
            )

        # -------------------------
        # 🟩 SUBJECTIVE QUESTION
        # -------------------------
        elif question_type == "subjective":

            qid = str(q["id"])



            import streamlit.components.v1 as components

            # -------------------------
            # Ensure answers exist (DICT)
            # -------------------------
            if "answers" not in st.session_state:
                st.session_state.answers = {}

            question_id = str(q["id"])

            if question_id not in st.session_state.answers:
                st.session_state.answers[question_id] = ""

            # -------------------------
            # Session keys
            # -------------------------
            current_key = f"text_{question_id}"

            if current_key not in st.session_state:

                val = st.session_state.answers.get(question_id, "")

                if val is None:
                    val = ""
                else:
                    val = str(val)

                st.session_state[current_key] = val

            # -------------------------
            # Disabled state
            # -------------------------
            time_up_or_submitted = (
                    time_up
                    or is_submitted
                    or is_locked
            )

            from streamlit_javascript import st_javascript
            # -------------------------
            # Initialize violation counter
            # -------------------------
            if "copy_paste_count" not in st.session_state:
                st.session_state.copy_paste_count = 0

            # -------------------------
            # COPY/PASTE DETECTION
            # -------------------------
            components.html(
                """
                <script>

                const doc = window.parent.document;

                if (!window.violationListenersAdded) {

                    window.violationListenersAdded = true;

                    function reportViolation(type) {

                        alert("⚠️ " + type + " detected!");

                        console.log("Violation:", type);
                    }

                    doc.addEventListener(
                        "copy",
                        () => reportViolation("Copy")
                    );

                    doc.addEventListener(
                        "cut",
                        () => reportViolation("Cut")
                    );

                    doc.addEventListener(
                        "paste",
                        () => reportViolation("Paste")
                    );
                }
                </script>
                """,
                height=0
            )
            # -------------------------
            # Text area
            # -------------------------
            if st.button("TEST VIOLATION"):
                log_violation(
                    progress_id=record.get("id"),
                    student_id=student_id,
                    subject_id=selected_subject_id,
                    question_id=q["id"],
                    school_id=school_id_int,
                    test_type="subjective",
                    event_type="paste"
                )

                st.success("Violation logged")

            # -------------------------
            # Use question_id as single source of truth
            # -------------------------
            qid = str(q["id"])

            saved = st.session_state.answers.get(qid, {})

            if isinstance(saved, dict):
                current_answer = saved.get("selected", "")
            else:
                current_answer = str(saved) if saved else ""

            # -------------------------
            # Input field
            # -------------------------
            answer = st.text_area(
                "Type your answer:",
                value=current_answer,
                key=current_key,
                height=150,
                disabled=time_up_or_submitted
            )

            # -------------------------
            # Save answer (ONLY dict model)
            # -------------------------
            if not (is_submitted or is_locked):
                st.session_state.answers[qid] = {
                    "question_id": qid,
                    "selected": answer,
                    "correct": "",
                    "is_correct": False
                }


            # -------------------------
            # Sticky warning
            # -------------------------
            st.markdown(
                """
                <div style="
                    padding: 6px 8px;
                    border-radius: 8px;
                    background-color:#cbd5c0;
                    border: 2px solid #f59e0b;
                    color: #111827;
                    text-align: center;
                    font-size: 16px;
                    font-weight: 600;
                    margin-bottom: 8px;
                    box-shadow: 0 2px 6px rgba(0,0,0,0.15);
                ">
                    ⚠️ Copying and Pasting is prohibited during this test. Violations may be recorded automatically.
                </div>
                """,
                unsafe_allow_html=True
            )


            # -------------------------
            # Submitted state
            # -------------------------
            if is_submitted or is_locked:
                st.info(
                    "✅ You have submitted this test. "
                    "Answers are now locked."
                )


        # -------------------------
        # Navigation & Submit Buttons
        # -------------------------
        col1, col2, col3 = st.columns([1, 1, 1])

        with col1:

            if st.button(
                    "⬅️ Previous",
                    disabled=current_q_idx == 0,
                    key="prev_btn"
            ):
                st.session_state.current_q -= 1
                persist_progress()
                st.rerun()

        with col2:

            if st.button(
                    "➡️ Next",
                    disabled=current_q_idx >= len(questions) - 1,
                    key="next_btn"
            ):
                st.session_state.current_q += 1
                print("NEXT clicked")
                print("session current_q =", st.session_state.current_q)
                persist_progress()
                st.rerun()



        with col3:
            # -------------------------
            # 1️⃣ User clicks submit
            # -------------------------
            if st.button(
                    "✅ Submit Test",
                    key=f"submit_{current_q_idx}"
            ):

                if not student_id or not school_id_int or not class_id:
                    st.toast(
                        "🚫 Student session incomplete. Please log in again."
                    )

                    st.stop()

                answers = st.session_state.get("answers", {})

                if not isinstance(answers, dict):
                    answers = {}

                answered_count = 0

                for a in answers.values():

                    if isinstance(a, dict):
                        value = a.get("selected", "")
                    else:
                        value = a

                    if str(value).strip():
                        answered_count += 1

                unanswered = (
                        len(questions)
                        - answered_count
                )

                st.session_state.answered_count = answered_count
                st.session_state.unanswered = unanswered

                if unanswered > 0:

                    st.session_state.confirm_submit = True

                else:

                    st.session_state.final_submit = True

            # -------------------------
            # 2️⃣ Show dialog
            # -------------------------
            if st.session_state.get(
                    "confirm_submit",
                    False
            ):
                confirm_submit_dialog()

            # -------------------------
            # 3️⃣ Auto-submit state
            # -------------------------
            auto_submit_triggered = (
                st.session_state.get(
                    "auto_submitted",
                    False
                )
            )

            # -------------------------
            # 4️⃣ Real submission starts
            # -------------------------
            if (
                    st.session_state.get(
                        "final_submit",
                        False
                    )
                    or auto_submit_triggered
            ):

                if auto_submit_triggered:
                    st.error(
                        "🚫 Test automatically submitted "
                        "due to multiple copy/paste violations."
                    )

                st.session_state.test_started = False
                st.session_state.final_submit = False

                st.session_state.copy_paste_count = 0
                st.session_state.auto_submitted = False

                answered_count = st.session_state.get(
                    "answered_count",
                    0
                )

                st.toast(
                    f"You answered "
                    f"{answered_count}/{len(questions)} questions."
                )

                start_time_ts = (
                    st.session_state.start_time.timestamp()
                    if isinstance(
                        st.session_state.start_time,
                        datetime
                    )
                    else st.session_state.start_time
                )

                subject_id = selected_subject["id"]
                test_type = st.session_state.test_type




     # =====================================================
     # SUBJECTIVE TEST SUBMISSION
     # =====================================================
                if test_type == "subjective":

                    try:

                        # -------------------------
                        # Build subjective payload
                        # -------------------------
                        subjective_payload = []

                        answers = st.session_state.get("answers", {})
                        if not isinstance(answers, dict):
                            answers = {}

                        for q in st.session_state.questions:
                            qid = str(q["id"])
                            raw = answers.get(qid, "")
                            ans = raw.get("selected", "") if isinstance(raw, dict) else raw

                            subjective_payload.append({
                                "question_id": qid,
                                "question": q.get("question_text") or q.get("text") or "No Question",
                                "answer": ans
                            })


                        # -------------------------
                        # Save subjective submission
                        # -------------------------
                        result = handle_subjective_submission(

                            student_id=student_id,

                            school_id=school_id_int,

                            subject_id=subject_id,

                            answers=subjective_payload,

                            questions=st.session_state.questions
                        )

                        if result == "already_submitted":
                            st.info(
                                "📌 You have already submitted this retake."
                            )

                            st.stop()


                        # -------------------------
                        # Update progress safely
                        # -------------------------
                        db = get_session()

                        try:

                            progress = db.query(StudentProgress).filter_by(
                                student_id=student_id,
                                subject_id=subject_id,
                                class_id=class_id,
                                school_id=school_id_int,
                                test_type="subjective"
                            ).order_by(
                                StudentProgress.created_at.desc()
                            ).first()

                            if progress:
                                finalize_submission(
                                    db=db,
                                    progress=progress,
                                    answers=subjective_payload,
                                    score=None,
                                    test_type="subjective"
                                )


                        except Exception as e:

                            db.rollback()

                            st.error(f"❌ Failed updating progress: {e}")


                        finally:

                            db.close()
                        # -------------------------
                        # Consume retake
                        # -------------------------
                        db = get_session()

                        try:

                            student_obj = db.query(Student).filter_by(
                                access_code=access_code,
                                school_id=school_id_int
                            ).first()

                            if student_obj:
                                decrement_retake(
                                    student_id=student_obj.id,
                                    subject_id=subject_id,
                                    school_id=school_id_int,
                                    test_type="subjective"
                                )

                        except Exception as e:

                            st.error(f"❌ Retake update failed: {e}")

                        finally:

                            db.close()

                        # -------------------------
                        # Prepare PDF state
                        # -------------------------
                        st.session_state.pdf_ready = True

                        st.session_state.pdf_data = {
                            "details": subjective_payload
                        }

                        # -------------------------
                        # Reset session state
                        # -------------------------
                        st.session_state.show_submission_message = True

                        # ⚠️ KEEP answers temporarily
                        # PDF generation still needs them
                        # st.session_state.answers = []

                        st.session_state.copy_paste_count = 0
                        st.session_state.current_q = 0
                        st.session_state.submitted = True
                        st.session_state.test_started = False

                        st.success(
                            "✅ Subjective test submitted successfully."
                        )

                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Subjective submission failed: {e}")


                # =====================================================
                # OBJECTIVE TEST SUBMISSION
                # =====================================================
                elif test_type == "objective":



                    db = get_session()

                    try:

                        # -------------------------
                        # Grade answers
                        # -------------------------

                        correct_count = 0
                        details = []

                        for q in st.session_state.questions:

                            qid = str(q["id"])

                            ans = st.session_state.answers.get(qid, "")

                            selected_answer = ""

                            if isinstance(ans, dict):
                                selected_answer = (
                                        ans.get("selected")
                                        or ans.get("answer")
                                        or ""
                                )
                            else:
                                selected_answer = str(ans or "")

                            correct_answer = (
                                    q.get("correct_answer")
                                    or q.get("correct_answer_text")
                                    or q.get("answer")
                                    or ""
                            )

                            # ALWAYS define is_correct
                            selected_answer_clean = str(selected_answer).strip().lower()
                            correct_answer_clean = str(correct_answer).strip().lower()

                            is_correct = (
                                    selected_answer_clean == correct_answer_clean
                            )

                            if is_correct:
                                correct_count += 1

                            details.append({
                                "question_id": q["id"],
                                "question_text": q.get("text", "No question text"),
                                "selected": selected_answer or "—",
                                "correct": correct_answer or "—",
                                "is_correct": is_correct
                            })


                        # 👇 PUT DEBUG HERE


                        for item in details[:3]:
                            st.write(item)

                        # 👇 EXISTING CODE CONTINUES
                        total_questions = len(details)

                        percent = (
                            (correct_count / total_questions) * 100
                            if total_questions
                            else 0
                        )


                        # -------------------------
                        # Progress
                        # -------------------------
                        progress = db.query(
                            StudentProgress
                        ).filter_by(
                            student_id=student_id,
                            subject_id=subject_id,
                            class_id=class_id,
                            school_id=school_id_int,
                            test_type="objective"
                        ).order_by(
                            StudentProgress.created_at.desc()
                        ).first()

                        if progress:
                            progress.current_q = st.session_state.current_q

                            progress.start_time = start_time_ts

                            progress.duration = st.session_state.duration

                            progress.questions = [
                                q["id"]
                                for q in st.session_state.questions
                            ]

                            finalize_submission(
                                db=db,
                                progress=progress,
                                answers=details,
                                score=correct_count,
                                test_type="objective"
                            )


                        # -------------------------
                        # Save Student Answers
                        # -------------------------
                        if progress:

                            for q in st.session_state.questions:

                                qid = str(q["id"])

                                ans = st.session_state.answers.get(qid, "")

                                if isinstance(ans, dict):

                                    clean_answer = (
                                            ans.get("selected")
                                            or ans.get("answer")
                                            or ""
                                    )

                                else:

                                    clean_answer = str(ans)

                                existing = db.query(
                                    StudentAnswer
                                ).filter_by(
                                    progress_id=progress.id,
                                    question_id=q["id"]
                                ).first()

                                if existing:

                                    existing.answer = clean_answer

                                else:

                                    db.add(
                                        StudentAnswer(
                                            progress_id=progress.id,
                                            question_id=q["id"],
                                            answer=clean_answer
                                        )
                                    )


                        # -------------------------
                        # Save Result
                        # -------------------------
                        db.add(
                            TestResult(
                                student_id=student_id,
                                class_id=class_id,
                                subject_id=subject_id,
                                score=correct_count,
                                total=total_questions,
                                percentage=percent,
                                school_id=school_id_int
                            )
                        )

                        db.commit()

                        # Save PDF state
                        st.session_state.pdf_ready = True

                        st.session_state.pdf_data = {

                            "correct": correct_count,
                            "total": total_questions,
                            "percent": percent,
                            "details": details

                        }

                        st.session_state.submitted = True
                        st.session_state.test_started = False

                        st.success(
                            "✅ Objective test submitted successfully."
                        )

                    except Exception as e:

                        db.rollback()

                        st.error(
                            f"❌ Objective submission failed: {e}"
                        )

                    finally:

                        db.close()


                # =====================================================
                # PERSISTENT PDF
                # =====================================================
                if st.session_state.get("pdf_ready"):

                    data = st.session_state.pdf_data

                    pdf_test_type = st.session_state.get(
                        "test_type",
                        "objective"
                    )

                    # -------------------------
                    # OBJECTIVE FEEDBACK
                    # -------------------------
                    # -------------------------
                    # FEEDBACK MESSAGE
                    # -------------------------

                    if pdf_test_type == "objective":

                        percent_score = float(
                            data.get("percent", 0)
                        )

                        if percent_score >= 80:

                            st.balloons()

                            st.success(
                                "🏆 Excellent Performance!"
                            )

                        elif percent_score >= 50:

                            st.success(
                                "👍 Good Job!"
                            )

                        else:

                            st.warning(
                                "📘 Keep Practicing."
                            )

                    # -------------------------
                    # SUBJECTIVE MESSAGE
                    # -------------------------

                    else:

                        st.info(
                            "🟡 Subjective test submitted successfully.\n\n"
                            "Awaiting teacher review."
                        )

                    st.divider()


                    # -------------------------
                    # SUBJECTIVE PDF DATA
                    # -------------------------
                    if pdf_test_type == "subjective":

                        # ✅ USE SAVED PAYLOAD
                        pdf_data = data.get("details", [])

                        # ✅ Subjective values
                        pdf_correct = 0
                        pdf_total = len(pdf_data)
                        pdf_percent = 0
                    # -------------------------
                    # OBJECTIVE PDF DATA
                    # -------------------------
                    else:

                        pdf_data = data["details"]

                        # ✅ Objective values
                        pdf_correct = data.get("correct", 0)
                        pdf_total = data.get("total", 0)
                        pdf_percent = data.get("percent", 0)



                    # -------------------------
                    # Generate PDF
                    # -------------------------
                    pdf_bytes = generate_pdf(

                        name=student.get(
                            "name",
                            "Unknown"
                        ),

                        class_name=st.session_state.get(
                            "class_name",
                            "Unknown Class"
                        ),

                        subject=selected_subject["name"],

                        correct=pdf_correct,

                        total=pdf_total,

                        percent=pdf_percent,

                        details=pdf_data,

                        school_name=st.session_state.get(
                            "school_name",
                            "Unknown School"
                        ),

                        school_id=school_id_int,

                        test_type=pdf_test_type
                    )

                    # -------------------------
                    # Download
                    # -------------------------
                    st.download_button(

                        "📄 Download Test Result PDF",

                        pdf_bytes,

                        file_name=(
                            f"{student.get('name', 'student')}_"
                            f"{selected_subject['name']}_"
                            f"{pdf_test_type}_result.pdf"
                        ),

                        mime="application/pdf"
                    )





