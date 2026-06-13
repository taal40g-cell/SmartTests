import json
import random
from datetime import datetime, timedelta
import streamlit as st
from sqlalchemy.orm import joinedload
# Backend modules
from backend.models import Student
from backend.database import get_session
from backend.ui import  generate_pdf
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
    load_question_cache,
    render_test_type_selector,
    render_test_entry_controls,

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


@st.cache_data(ttl=300)
def get_class_name_by_id(class_id: int) -> str:
    if not class_id:
        return "Unknown"

    db = get_session()
    try:
        cls = db.query(Class).get(class_id)  # <-- use Class, not Classes
        return cls.name if cls else "Unknown"
    finally:
        db.close()


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

    # -------------------------
    # Session state defaults
    # -------------------------
    st.session_state.setdefault("confirm_submit", False)
    st.session_state.setdefault("final_submit", False)
    st.session_state.setdefault("answered_count", 0)
    st.session_state.setdefault("unanswered", 0)

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
    # 📊 STUDENT MODE ENTRY POINT
    # =========================================================

    student = render_student_login()

    # -------------------------
    # LOGIN GATE
    # -------------------------
    if not student:
        st.stop()

    # -------------------------
    # SESSION INITIALIZATION (ONLY ONCE)
    # -------------------------
    if not st.session_state.get("logged_in"):
        st.session_state.update({
            "logged_in": True,
            "student": student,
            "student_id": student["id"],
            "school_id": student["school_id"],
            "class_id": student["class_id"],
            "subject": None
        })

    # -------------------------
    # SOURCE OF TRUTH (SESSION ONLY)
    # -------------------------
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
    # 📊 RESULTS CENTER (SAFE TO CALL NOW)
    # =========================================================
    import time

    t0 = time.time()

    render_results_center()

    st.write(
        f"⏱ render_results_center: {time.time() - t0:.3f} sec"
    )
    # =========================================================
    # 📦 LOAD CLASSES (CACHE)
    # =========================================================
    if "classes" not in st.session_state:
        db = get_session()
        try:
            st.session_state.classes = db.query(Class).all()
        finally:
            db.close()

    # =========================================================
    # 📚 LOAD SUBJECTS (CACHE)
    # =========================================================
    import time

    if "subjects" not in st.session_state:
        try:
            t0 = time.time()

            st.session_state.subjects = load_subjects(
                school_id=school_id_int,
                class_id=class_id_int
            )

            st.write(
                f"⏱ load_subjects: {time.time() - t0:.3f} sec"
            )

        except Exception as e:
            st.error(f"Failed to load subjects: {e}")
            st.session_state.subjects = []



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
        key="subject_select_box"
    )

    selected_subject_id = selected_subject.get("id")
    selected_subject_name = selected_subject.get("name")

    # =========================================================
    # 🔄 SUBJECT SWITCH RESET
    # =========================================================
    if st.session_state.subject is None:
        st.session_state.subject = selected_subject_name

    elif st.session_state.subject != selected_subject_name:
        reset_keys = [
            "test_started", "submitted", "answers", "questions",
            "current_q", "current_page", "marked_for_review",
            "start_time", "test_end_time", "five_min_warned",
            "saved_to_db", "last_auto_save",
            "confirm_submit", "final_submit",
            "answered_count", "unanswered"
        ]

        for key in reset_keys:
            st.session_state[key] = (
                set() if key == "marked_for_review"
                else [] if key in ["answers", "questions"]
                else False
            )

        st.session_state.subject = selected_subject_name
        st.rerun()


    if selected_subject_id is None:
        st.info(f"🚫 Subject ID not found for '{selected_subject}'")
        st.stop()

    # -------------------------
    # ❓ LOAD QUESTIONS (CACHED)
    # -------------------------
    import time

    objective_questions, subjective_questions = (
        load_question_cache(
            selected_subject_id=selected_subject_id,
            class_id=class_id_int,
            school_id=school_id_int
        )
    )



    # -------------------------
    # 🧩 TEST TYPE SELECTION
    # -------------------------
    test_type = render_test_type_selector(
        class_id=class_id,
        subject_id=selected_subject_id
    )


    # -------------------------
    # 👤 VALIDATE STUDENT
    # -------------------------
    student_info = st.session_state.get("student")
    access_code = st.session_state.student.get("access_code", "").strip()

    if not student_info or not student_info.get("id"):
        st.info("🚫 Student ID missing. Please log in again.")
        st.stop()

    student_id = student_info["id"]


    record = get_or_create_student_progress(
        student_id=student_id,
        access_code=access_code,
        subject_id=selected_subject_id,
        class_id=class_id_int,
        school_id=school_id_int,
        test_type=st.session_state.test_type
    )

    is_locked = record.locked
    is_submitted = record.submitted

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

    if not st.session_state.get("test_started", False):
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

            st.write(f"⏱ question_bank selection: {time.time() - t0:.3f} sec")

            # ✅ FORCE REAL LIST
            t0 = time.time()

            question_bank = list(question_bank)
            random.shuffle(question_bank)

            st.write(f"⏱ shuffle: {time.time() - t0:.3f} sec")

            # ✅ TRUE RANDOMIZATION
            t0 = time.time()



            st.write(f"⏱ shuffle: {time.time() - t0:.3f} sec")


            # -------------------------
            # Normalize questions
            # -------------------------
            t0 = time.time()

            normalized_questions = [
                normalize_question(q)
                for q in question_bank
            ]

            st.write(
                f"⏱ normalize_questions: {time.time() - t0:.3f} sec"
            )

            # ✅ SAVE RANDOMIZED ORDER
            st.session_state.questions = normalized_questions
            st.session_state.test_started = True


            # -------------------------
            # Reset state
            # -------------------------
            st.session_state.answers = [""] * len(normalized_questions)

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
            # Save progress
            # -------------------------
            t0 = time.time()

            save_progress(
                access_code=access_code,
                subject_id=selected_subject_id,
                class_id=class_id_int,
                school_id=school_id_int,
                test_type=st.session_state.test_type,
                answers=json.dumps([
                    {
                        "question_id": q["id"],
                        "selected": "",
                        "correct": "",
                        "is_correct": False
                    }
                    for q in normalized_questions
                ]),
                current_q=0,
                start_time=st.session_state.start_time,
                duration=st.session_state.duration,
                questions=json.dumps([
                    q["id"]
                    for q in normalized_questions
                ]),
                student_id=student_id,
                submitted=False
            )

            st.write(
                f"⏱ save_progress: {time.time() - t0:.3f} sec"
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

            st.write(
                f"⏱ load_progress: {time.time() - t0:.3f} sec"
            )

            # 🚫 No progress found
            if not saved_progress:
                st.warning("⚠️ No unfinished test to resume.")
                st.session_state.test_started = False
                st.session_state.test_action = None
                st.stop()

            # 🚫 Already submitted
            if saved_progress.get("submitted", False):
                st.warning("⚠️ This test was already submitted.")
                st.session_state.test_started = False
                st.session_state.test_action = None
                st.stop()

            saved_start_time = saved_progress.get("start_time")
            saved_duration = saved_progress.get("duration")

            # 🚫 Corrupt or empty timing data
            if not saved_start_time or not saved_duration:
                st.warning("⚠️ No valid test session to resume.")
                st.session_state.test_started = False
                st.session_state.test_action = None
                st.stop()


            # -------------------------
            # ✅ SAFE RESTORE
            # -------------------------

            question_bank = (
                objective_questions
                if st.session_state.test_type == "objective"
                else subjective_questions
            )

            saved_questions = saved_progress.get("questions", [])

            if isinstance(saved_questions, str):

                try:
                    saved_questions = json.loads(saved_questions)
                except:
                    saved_questions = []

            # ✅ normalize questions
            # -------------------------
            # Normalize questions (SAFE SINGLE FORMAT)
            # -------------------------
            normalized_questions = [
                normalize_question(q)
                for q in question_bank
            ]

            if saved_questions:

                qmap = {q["id"]: q for q in normalized_questions}

                rebuilt = [
                    qmap[qid]
                    for qid in saved_questions
                    if qid in qmap
                ]

                st.session_state.questions = (
                    rebuilt if rebuilt else normalized_questions
                )

            else:
                st.session_state.questions = normalized_questions
            saved_answers = saved_progress.get(
                "answers",
                [""] * len(st.session_state.questions)
            )

            # ✅ FIX: decode JSON/string answers safely
            if isinstance(saved_answers, str):

                try:

                    saved_answers = json.loads(saved_answers)

                except Exception:
                    saved_answers = [""] * len(st.session_state.questions)

            # ✅ ensure answers is always a list
            if not isinstance(saved_answers, list):
                saved_answers = [""] * len(st.session_state.questions)

            st.session_state.answers = saved_answers

            st.session_state.current_q = min(
                max(saved_progress.get("current_q", 0), 0),
                len(st.session_state.questions) - 1
            )

            st.session_state.start_time = datetime.fromtimestamp(saved_start_time)
            st.session_state.duration = int(saved_duration)

            st.session_state.test_end_time = (
                    st.session_state.start_time +
                    timedelta(seconds=st.session_state.duration)
            )

            st.session_state.auto_submitted = False
            st.session_state.test_action = None

        # -------------------------
        # ⏱️ TIMER
        # -------------------------
        now_ts = datetime.now().timestamp()
        start_ts = st.session_state.start_time.timestamp()

        elapsed = now_ts - start_ts
        remaining = st.session_state.duration - elapsed

        mins = int(remaining // 60)
        secs = int(remaining % 60)



        # -------------------------
        # 🔴 AUTO SUBMIT (RUN FIRST)
        # -------------------------
        if remaining <= 0:

            if not st.session_state.get("auto_submitted", False):
                st.session_state.auto_submitted = True

                st.warning("⏰ Time is up! Submitting your test automatically...")

                # -------------------------
                # Build structured answers (IMPORTANT FIX)
                # -------------------------
                details = []

                for q, ans in zip(st.session_state.questions, st.session_state.answers):
                    correct_answer = q.get("correct_answer", "")

                    is_correct = (
                            str(ans).strip().lower()
                            == str(correct_answer).strip().lower()
                    )

                    details.append({
                        "question_id": q.get("id"),
                        "question_text": q.get("text", ""),
                        "selected": ans or "—",
                        "correct": correct_answer or "—",
                        "is_correct": is_correct
                    })

                # -------------------------
                # Save to DB (FIXED FORMAT)
                # -------------------------
                save_progress(
                    access_code=access_code,
                    subject_id=selected_subject_id,
                    class_id=class_id_int,
                    school_id=school_id_int,
                    test_type=st.session_state.test_type,
                    answers=json.dumps(details),
                    current_q=st.session_state.current_q,
                    start_time=st.session_state.start_time,
                    duration=st.session_state.duration,
                    questions=[q["id"] for q in st.session_state.questions],
                    student_id=student_id,
                    submitted=True
                )

                st.success("✅ Test submitted automatically.")

                st.session_state.test_started = False
                st.stop()





        # ✅ AUTO-INITIALIZE TEST (CRITICAL FIX)
        import time

        t0 = time.time()

        if st.session_state.get("test_started") and not st.session_state.get("test_end_time"):
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

            st.session_state.answers = [
                {
                    "question_id": q["id"],
                    "selected": "",
                    "correct": "",
                    "is_correct": False
                }
                for q in st.session_state.questions
            ]

            st.session_state.current_q = 0
            st.session_state.start_time = datetime.now()
            st.session_state.duration = duration_minutes * 60

            st.session_state.test_end_time = (
                    st.session_state.start_time +
                    timedelta(seconds=st.session_state.duration)
            )

            st.session_state.marked_for_review = set()
            st.session_state.paste_count = 0

        st.write(
            f"⏱ auto_initialize: {time.time() - t0:.3f} sec"
        )


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

        # =============================
        # 📊 PROGRESS INFO (UI ONLY)
        # =============================

        answered = sum(
            1 for a in st.session_state.answers
            if a not in (None, "", [])
        )

        total_questions = len(st.session_state.questions)

        percent = int((answered / total_questions) * 100) if total_questions else 0

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
        # ⛔ Auto-submit when time is up
        # -------------------------
        # ==============================
        # ⏰ AUTO SUBMIT (OPTIMIZED)
        # ==============================
        if remaining_seconds <= 0 and not is_submitted:

            st.warning("⏰ Time is up! Submitting your test automatically...")

            # ------------------------------
            # Safe timestamp handling
            # ------------------------------
            start_time_ts = (
                st.session_state.start_time.timestamp()
                if isinstance(st.session_state.start_time, datetime)
                else st.session_state.start_time
            )

            subject_id = selected_subject["id"]

            # ------------------------------
            # 1️⃣ Save final progress (single source of truth)
            # ------------------------------
            save_progress(
                access_code=access_code,
                student_id=student_id,
                subject_id=subject_id,
                class_id=class_id_int,
                school_id=school_id_int,
                test_type=st.session_state.test_type,
                answers=st.session_state.answers,
                current_q=st.session_state.current_q,
                start_time=start_time_ts,
                duration=st.session_state.duration,
                questions=[q["id"] for q in st.session_state.questions],
                submitted=True
            )

            # ------------------------------
            # 2️⃣ Persist answers (FAST BULK UPDATE)
            # ------------------------------
            db = get_session()

            try:
                progress = db.query(StudentProgress).filter_by(
                    student_id=student_id,
                    subject_id=subject_id,
                    class_id=class_id_int,
                    school_id=school_id_int,
                    test_type=st.session_state.test_type
                ).first()

                if progress:

                    # --------------------------
                    # BULK FETCH existing answers (NO LOOP QUERIES)
                    # --------------------------
                    existing_map = {
                        a.question_id: a
                        for a in db.query(StudentAnswer)
                        .filter_by(progress_id=progress.id)
                        .all()
                    }

                    questions = st.session_state.questions
                    answers = st.session_state.answers

                    # --------------------------
                    # UPDATE IN MEMORY ONLY
                    # --------------------------
                    for i in range(len(questions)):

                        q = questions[i]
                        ans = answers[i] if i < len(answers) else ""

                        qid = q["id"]

                        existing = existing_map.get(qid)

                        if existing:
                            existing.answer = ans
                        else:
                            db.add(
                                StudentAnswer(
                                    progress_id=progress.id,
                                    question_id=qid,
                                    answer=ans
                                )
                            )

                    db.commit()

            except Exception as e:
                db.rollback()
                print("Auto-submit error:", e)

            finally:
                db.close()

            # ------------------------------
            # 3️⃣ End session cleanly
            # ------------------------------
            st.success("✅ Test submitted automatically.")
            st.session_state.test_started = False
            st.stop()


        # -------------------------
        # Render current question
        # -------------------------
        questions = st.session_state.questions
        current_q_idx = st.session_state.current_q


        if not questions:
            st.warning("🚨 Questions failed to load. Check upload or loader.")
            st.stop()



        current_q_idx = min(max(current_q_idx, 0), len(questions) - 1)
        st.session_state.current_q = current_q_idx

        # ✅ SAFE NOW
        show_question_tracker(
            st.session_state.questions,
            st.session_state.current_q,
            st.session_state.answers
        )


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
        # Ensure answers list is sized
        while len(st.session_state.answers) <= current_q_idx:
            st.session_state.answers.append("")

        prev_answer = st.session_state.answers[current_q_idx]
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

            # Save only in session state
            st.session_state.answers[current_q_idx] = (
                ""
                if selected_option == "Choose answer"
                else selected_option
            )
        # -------------------------
        # 🟩 SUBJECTIVE QUESTION
        # -------------------------
        elif question_type == "subjective":

            import streamlit.components.v1 as components

            # -------------------------
            # Ensure answers exist
            # -------------------------
            if "answers" not in st.session_state:
                st.session_state.answers = [""] * len(questions)

            while len(st.session_state.answers) <= current_q_idx:
                st.session_state.answers.append("")

            # -------------------------
            # Session keys
            # -------------------------
            current_key = f"text_{current_q_idx}"

            if current_key not in st.session_state:

                val = st.session_state.answers[current_q_idx]

                if val is None:
                    val = ""
                elif isinstance(val, dict):
                    val = val.get("answer", "")
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

                if (!window.violationListenersAdded){

                    window.violationListenersAdded=true;

                    function reportViolation(type){

                        alert("⚠️ " + type + " detected!");

                        const url=new URL(window.parent.location);

                        url.searchParams.set(
                            "violation",
                            type
                        );

                        url.searchParams.set(
                            "time",
                            Date.now()
                        );

                        window.parent.location.href=url.toString();
                    }

                    doc.addEventListener(
                        "copy",
                        ()=>reportViolation("Copy")
                    );

                    doc.addEventListener(
                        "cut",
                        ()=>reportViolation("Cut")
                    );

                    doc.addEventListener(
                        "paste",
                        ()=>reportViolation("Paste")
                    );

                }

                </script>
                """,
                height=0
            )



            # -------------------------
            # Initialize counter
            # -------------------------
            query_params = st.query_params


            # -------------------------
            # Detect violation
            # -------------------------
            if "violation" in st.query_params:

                try:

                    violation_type = st.query_params.get("violation")

                    # Streamlit may return list
                    if isinstance(violation_type, list):
                        violation_type = violation_type[0]

                    violation_type = str(
                        violation_type
                    ).strip().lower()

                    # -------------------------
                    # Safe IDs
                    # -------------------------
                    progress_id = getattr(record, "id", None)

                    question_id = None

                    if isinstance(q, dict):
                        question_id = q.get("id")

                    # -------------------------
                    # Save violation
                    # -------------------------
                    log_violation(
                        progress_id=progress_id,
                        student_id=student_id,
                        subject_id=selected_subject.id,
                        question_id=question_id,
                        school_id=school_id_int,
                        test_type="subjective",
                        event_type=violation_type
                    )

                    # -------------------------
                    # Increase counter
                    # -------------------------
                    st.session_state.copy_paste_count += 1

                    st.warning(
                        f"⚠️ {violation_type.upper()} detected "
                        f"and logged."
                    )

                except Exception as e:

                    st.error(
                        f"Violation logging failed: {e}"
                    )

                finally:

                    # Prevent duplicate triggers
                    st.query_params.clear()
            # -------------------------
            # Text area
            # -------------------------


            current_answer = ""

            if len(st.session_state.answers) > current_q_idx:

                saved_answer = st.session_state.answers[current_q_idx]

                if isinstance(saved_answer, dict):

                    current_answer = (
                            saved_answer.get("answer")
                            or saved_answer.get("selected")
                            or ""
                    )

                elif saved_answer is None:

                    current_answer = ""

                else:

                    current_answer = str(saved_answer)

            answer = st.text_area(
                "Type your answer:",
                value=current_answer,
                key=current_key,
                height=150,
                disabled=time_up_or_submitted
            )

            if not (is_submitted or is_locked):

                if (
                        isinstance(st.session_state.answers[current_q_idx], dict)
                ):

                    st.session_state.answers[current_q_idx]["selected"] = answer

                else:

                    st.session_state.answers[current_q_idx] = {
                        "question_id": q["id"],
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
                save_progress(
                    access_code=access_code,
                    student_id=student_id,
                    subject_id=selected_subject["id"],
                    class_id=class_id_int,
                    school_id=school_id_int,
                    test_type=st.session_state.test_type,
                    answers=st.session_state.answers,
                    current_q=current_q_idx,
                    start_time=st.session_state.start_time,
                    duration=st.session_state.duration,
                    questions=[
                        q["id"]
                        for q in st.session_state.questions
                    ]
                )

                st.session_state.current_q -= 1
                st.rerun()

        with col2:

            if st.button(
                    "➡️ Next",
                    disabled=current_q_idx >= len(questions) - 1,
                    key="next_btn"
            ):
                save_progress(
                    access_code=access_code,
                    student_id=student_id,
                    subject_id=selected_subject["id"],
                    class_id=class_id_int,
                    school_id=school_id_int,
                    test_type=st.session_state.test_type,
                    answers=st.session_state.answers,
                    current_q=current_q_idx,
                    start_time=st.session_state.start_time,
                    duration=st.session_state.duration,
                    questions=[
                        q["id"]
                        for q in st.session_state.questions
                    ]
                )

                st.session_state.current_q += 1
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

                answers = st.session_state.get(
                    "answers",
                    []
                )

                answered_count = sum(
                    1 for a in answers
                    if is_answered(a)
                )

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

                        for q, ans in zip(
                                st.session_state.questions,
                                st.session_state.answers
                        ):

                            # normalize safely
                            if isinstance(ans, dict):

                                clean_answer = (
                                        ans.get("answer")
                                        or ans.get("selected")
                                        or ""
                                )

                            else:

                                clean_answer = str(ans)

                            subjective_payload.append({

                                "question_id": q.get("id"),

                                "question": (

                                        q.get("question_text")

                                        or q.get("text")

                                        or "No Question"

                                ),

                                "answer": clean_answer

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
                                progress.submitted = True

                                # 🚨 DO NOT LOCK HERE
                                # Admin grading needs updates later
                                progress.locked = False

                                progress.review_status = "pending"
                                progress.reviewed_at = None

                            db.commit()

                        except Exception as e:
                            db.rollback()
                            st.error(f"❌ Failed updating progress: {e}")

                        finally:
                            db.close()

                        # -------------------------
                        # Consume retake
                        # -------------------------
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

                        for q, ans in zip(
                                st.session_state.questions,
                                st.session_state.answers
                        ):

                            # FIX: extract answer if dict
                            if isinstance(ans, dict):
                                selected_answer = (
                                        ans.get("selected")
                                        or ans.get("answer")
                                        or ""
                                )
                            else:
                                selected_answer = str(ans)

                            correct_answer = q.get(
                                "correct_answer",
                                ""
                            )

                            is_correct = (
                                    selected_answer.strip().lower()
                                    ==
                                    str(correct_answer).strip().lower()
                            )

                            if is_correct:
                                correct_count += 1


                            details.append({
                                "question_id": q.get("id"),
                                "question_text": q.get(
                                    "text",
                                    "No question text"
                                ),
                                "selected": selected_answer or "—",
                                "correct": correct_answer or "—",
                                "is_correct": is_correct
                            })


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
                            progress.answers = json.dumps(
                                details
                            )

                            progress.current_q = (
                                st.session_state.current_q
                            )

                            progress.start_time = (
                                start_time_ts
                            )

                            progress.duration = (
                                st.session_state.duration
                            )

                            progress.questions = json.dumps(
                                [
                                    q["id"]
                                    for q in st.session_state.questions
                                ]
                            )

                            progress.score = correct_count
                            progress.submitted = True
                            progress.locked = True
                            progress.review_status = "reviewed"
                            progress.reviewed_at = datetime.utcnow()

                        # -------------------------
                        # Save Student Answers
                        # -------------------------
                        if progress:

                            for q, ans in zip(
                                    st.session_state.questions,
                                    st.session_state.answers
                            ):

                                # FIX HERE
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