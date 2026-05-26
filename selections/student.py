import json
import pandas as pd
from datetime import datetime, timedelta
import streamlit as st

# Backend modules
from backend.models import Student
from sqlalchemy.orm import joinedload
from backend.database import get_session
from backend.ui import  generate_pdf,get_student_display
from backend.helpers import (
    get_subjective_questions,
    get_objective_questions,
    save_answer,
    handle_subjective_submission
)
from backend.db_helpers import (
    show_question_tracker,
    can_take_test,
    get_users,
    load_subjects,
    get_test_duration,
    get_student_by_access_code,
    load_progress,
    save_progress,parse_json_field,
    decrement_retake,is_answered,
    log_violation,normalize_objective,normalize_subjective
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




@st.cache_data(ttl=600)
def get_class_school_names(
    class_id: int,
    school_id: int
):
    session = get_session()

    try:
        class_obj = session.get(
            Class,
            class_id
        )

        school_obj = session.get(
            School,
            school_id
        )

        return (
            class_obj.name if class_obj else "Unknown Class",
            school_obj.name if school_obj else "Unknown School"
        )

    finally:
        session.close()




# ==============================
# Main Student Mode
# ==============================
def run_student_mode():

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

            if st.button(
                "✅ Submit Anyway"
            ):

                st.session_state.confirm_submit = False
                st.session_state.final_submit = True
                st.rerun()

        with col2:

            if st.button(
                "🚫 Go Back to Test"
            ):

                st.session_state.confirm_submit = False
                st.rerun()


    # continue rest of student mode below...
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

        if st.button("⬅ Return to Test Portal"):
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
    # Header & Banner
    # -----------------------------
    st.markdown(
        """
        <div style="
             padding: 6px 8px;
            border-radius: 8px;
            background-color:#cbd5c0;
            border: 2px solid #F54927;
            color: #111827;
            text-align: center;
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 8px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.15);
        ">
            ⚠️ Retakes are controlled by Admins! 
            Submit your test before time runs out.
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("### Student Portal")
    st.markdown("Welcome to your personalized test center.")


    from backend.database import get_session
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
    # Load schools
    # -------------------------
    # -------------------------
    # LOGIN (School + Access Code)
    # -------------------------
    if not st.session_state.get("logged_in", False):

        # -------------------------
        # Load schools (cached)
        # -------------------------
        @st.cache_data(ttl=300)
        def get_schools():
            session = get_session()
            try:
                return session.query(School).filter(
                    School.is_system == False
                ).all()
            finally:
                session.close()

        schools = get_schools()

        if not schools:
            st.warning("❌ No schools found. Contact admin.")
            st.stop()

        school_map = {
            school.name: school.id
            for school in schools
        }

        # -------------------------
        # Login Form
        # -------------------------
        with st.form("student_login"):

            selected_school_name = st.selectbox(
                "Select School",
                options=list(school_map.keys()),
                index=None,
                placeholder="-- Select School --"
            )

            access_code_input = st.text_input(
                "Access Code",
                placeholder="Code issued by Admin"
            )

            login_btn = st.form_submit_button(
                "Login"
            )

        # -------------------------
        # Login Logic
        # -------------------------
        if login_btn:

            if not selected_school_name:
                st.warning("Select a school")
                st.stop()

            access_code = access_code_input.strip().upper()

            if not access_code:
                st.warning("Enter access code")
                st.stop()

            selected_school_id = school_map.get(
                selected_school_name
            )

            if selected_school_id is None:
                st.warning("Invalid school selection")
                st.stop()

            student_obj = get_student_by_access_code(
                access_code,
                school_id=selected_school_id
            )

            if not student_obj:
                st.info(
                    "❌ Invalid code for selected school"
                )
                st.stop()

            # -------------------------
            # Convert ORM → dict
            # -------------------------
            student = {
                "id": student_obj.id,
                "unique_id": getattr(student_obj, "unique_id", ""),
                "name": student_obj.name,
                "class_id": student_obj.class_id,
                "school_id": student_obj.school_id,
                "access_code": access_code,
                "can_retake": bool(getattr(student_obj, "can_retake", True)),
            }


            # -------------------------
            # Resolve names
            # -------------------------
            @st.cache_data(ttl=600)
            def get_class_school_names(
                    class_id,
                    school_id
            ):
                db = get_session()

                try:
                    class_obj = db.query(Class).get(class_id)

                    school_obj = db.query(School).get(school_id)

                    class_name = (
                        class_obj.name
                        if class_obj
                        else "Unknown Class"
                    )

                    school_name = (
                        school_obj.name
                        if school_obj
                        else "Unknown School"
                    )

                    return class_name, school_name

                finally:
                    db.close()

            class_name, school_name = (
                get_class_school_names(
                    student["class_id"],
                    student["school_id"]
                )
            )
            # -------------------------
            # Persist session (LOGIN SUCCESS)
            # -------------------------
            st.session_state.update({
                "logged_in": True,
                "student": student,
                "student_id": student["id"],
                "school_id": student["school_id"],
                "class_id": student["class_id"],
                "class_name": class_name,
                "school_name": school_name,
                "subject": None
            })

            # -------------------------
            # Reset stale session state
            # -------------------------
            reset_keys = [
                "test_started",
                "submitted",
                "questions",
                "answers",
                "current_q",
                "marked_for_review",
                "start_time",
                "duration",
                "saved_to_db",
                "test_phase",
                "test_type"
            ]

            for k in reset_keys:
                st.session_state.pop(k, None)

            # -------------------------
            # Clean Welcome UI
            # -------------------------
            st.success(f"Welcome {student['name']} 🎉")

            st.markdown(f"""
            ### 👋 Welcome, {student['name']}
            🏫 **School:** {school_name}  
            🎓 **Class:** {class_name}  
            📘 **Subject:** Select Subject
            """, unsafe_allow_html=True)

            # -------------------------
            # Final rerun (ONLY ONCE)
            # -------------------------
            st.rerun()

    # =========================================================
    # 📊 RESULTS CENTER
    # =========================================================
    with st.sidebar:

        st.header("📊 Results Center")

        school_id = st.session_state.get("school_id")
        student_id = st.session_state.get("student_id")

        objective_records = []
        subjective_records = []
        records = []

        if school_id and student_id:


            # ---------------------------------
            # Normalize objective data
            # ---------------------------------
            db = get_session()

            try:

                records = (
                    db.query(StudentProgress)
                    .options(
                        joinedload(
                            StudentProgress.subject
                        )
                    )
                    .filter(
                        StudentProgress.student_id == student_id,
                        StudentProgress.school_id == school_id,
                        StudentProgress.submitted == True
                    )
                    .order_by(
                        StudentProgress.created_at.desc()
                    )
                    .all()
                )

            finally:
                db.close()

            # ---------------------------------
            # Split records
            # ---------------------------------

            objective_records = [
                r for r in records
                if str(r.test_type).strip().lower() == "objective"
            ]

            subjective_records = [
                r for r in records
                if str(r.test_type).strip().lower() == "subjective"
            ]


        # =====================================================
        # OBJECTIVE
        # =====================================================

        st.markdown("### 📘 Objective Tests")

        if not objective_records:

            st.caption(
                "No objective tests yet."
            )

        else:

            for r in objective_records:

                subject_name = (
                    r.subject.name
                    if r.subject
                    else "Unknown"
                )

                details = normalize_objective(
                    parse_json_field(
                        r.answers
                    )
                )

                total_q = len(details)

                correct = sum(

                    1
                    for d in details
                    if d.get(
                        "is_correct",
                        False
                    )
                )

                percent = (

                    correct / total_q * 100

                    if total_q

                    else 0

                )

                with st.expander(
                        f"{subject_name} — {int(percent)}%"
                ):

                    st.write(
                        f"Score: {correct}/{total_q}"
                    )

                    st.write(
                        f"Date: "
                        f"{r.created_at.strftime('%Y-%m-%d %H:%M')}"
                    )

                    if st.toggle(
                            "View Breakdown",
                            key=f"obj_{r.id}"
                    ):

                        for i, d in enumerate(
                                details,
                                start=1
                        ):
                            st.markdown(
                                f"**Q{i}**"
                            )

                            st.write(
                                d["question_text"]
                            )

                            st.write(
                                f"Your Answer: "
                                f"{d['selected']}"
                            )

                            st.write(
                                f"Correct: "
                                f"{d['correct']}"
                            )

                            st.write(

                                "✅ Correct"

                                if d["is_correct"]

                                else "❌ Wrong"

                            )

                            st.markdown("---")

                    student_name = (
                        st.session_state.get(
                            "student",
                            {}
                        ).get(
                            "name",
                            "Student"
                        )
                    )

                    pdf_bytes = generate_pdf(

                        name=student_name,

                        class_name="",

                        subject=subject_name,

                        correct=correct,

                        total=total_q,

                        percent=percent,

                        details=details,

                        school_name=st.session_state.get(
                            "school_name"
                        ),

                        school_id=school_id,

                        test_type="objective"
                    )

                    st.download_button(

                        "📄 Download PDF",

                        pdf_bytes,

                        file_name=(
                            f"{student_name}_"
                            f"{subject_name}_objective.pdf"
                        ),

                        mime="application/pdf",

                        key=f"obj_pdf_{r.id}"

                    )

                    st.markdown("---")

        # =====================================================
        # ✍️ SUBJECTIVE TESTS
        # =====================================================

        st.markdown(
            "### ✍️ Subjective Tests"
        )

        if not subjective_records:

            st.caption(
                "No subjective tests yet."
            )

        else:

            # -------------------------
            # GLOBAL PENDING ALERT
            # -------------------------

            pending_count = sum(

                1 for r in subjective_records

                if r.review_status == "pending"

            )

            if pending_count:
                st.warning(
                    f"🟡 You have {pending_count} subjective "
                    f"test(s) awaiting teacher review."
                )
            # -------------------------
            # SUBJECTIVE RECORDS
            # -------------------------

            for r in subjective_records:

                subject_name = (

                    r.subject.name

                    if r.subject

                    else "Unknown"

                )

                details = normalize_subjective(

                    parse_json_field(
                        r.answers
                    )

                )

                total_q = len(details)

                score = (

                    r.score

                    if r.score is not None

                    else 0

                )

                percent = (

                    (score / total_q) * 100

                    if total_q

                    else 0

                )

                pending = (

                        r.review_status == "pending"

                )

                # -------------------------
                # EXPANDER TITLE
                # -------------------------

                expander_title = (

                    f"{subject_name} — 🟡 Awaiting Review"

                    if pending

                    else

                    f"{subject_name} — ✅ Reviewed"

                )

                with st.expander(
                        expander_title
                ):

                    # -------------------------
                    # STATUS
                    # -------------------------

                    if not pending:
                        st.success(
                            f"✅ Final Score: "
                            f"{score}/{total_q}"
                        )
                    # -------------------------
                    # DATE
                    # -------------------------

                    st.write(

                        f"Date: "

                        f"{r.created_at.strftime('%Y-%m-%d %H:%M')}"

                    )

                    # -------------------------
                    # BREAKDOWN
                    # -------------------------

                    show_breakdown = st.toggle(

                        "View Breakdown",

                        key=f"subj_{r.id}"

                    )

                    if show_breakdown:

                        for i, d in enumerate(
                                details,
                                start=1
                        ):
                            st.markdown(
                                f"### Q{i}"
                            )

                            st.write(
                                f"Question: "
                                f"{d.get('question', 'No Question')}"
                            )

                            st.write(
                                f"Answer: "
                                f"{d.get('answer', 'No Answer')}"
                            )

                            st.write(
                                f"Teacher Score: "
                                f"{d.get('teacher_score', 'Pending')}"
                            )

                            st.markdown("---")


                    # -------------------------
                    # PDF
                    # -------------------------

                    student_name = (
                        st.session_state.get(
                            "student",
                            {}
                        ).get(
                            "name",
                            "Student"
                        )
                    )

                    pdf_bytes = generate_pdf(

                        name=student_name,

                        class_name=st.session_state.get(
                            "class_name",
                            ""
                        ),

                        subject=subject_name,

                        correct=score,

                        total=total_q,

                        percent=percent,

                        details=details,

                        school_name=st.session_state.get(
                            "school_name"
                        ),

                        school_id=school_id,

                        test_type="subjective"

                    )

                    st.download_button(

                        "📄 Download PDF",

                        pdf_bytes,

                        file_name=(

                            f"{student_name}_"

                            f"{subject_name}_subjective.pdf"

                        ),

                        mime="application/pdf",

                        key=f"subj_pdf_{r.id}"

                    )


    # -------------------------
    # Main Student UI
    # -------------------------
    if not st.session_state.get("logged_in"):
        st.stop()

    student = st.session_state.get("student")

    if not student:
        st.info("🚫Student session not initialized.")
        st.stop()

    school_id = student.get("school_id")
    class_id = student.get("class_id")

    if school_id is None or class_id is None:
        st.info("🚫Student is missing school or class assignment.")
        st.stop()

    school_id_int = int(school_id)
    class_id_int = int(class_id)

    # -------------------------
    # 📦 LOAD CLASSES (ONCE)
    # -------------------------
    if "classes" not in st.session_state:
        db = get_session()
        try:
            st.session_state.classes = db.query(Class).all()
        finally:
            db.close()

    # -------------------------
    # 📚 LOAD SUBJECTS (CACHED)
    # -------------------------
    if "subjects" not in st.session_state:
        try:
            st.session_state.subjects = load_subjects(
                school_id=school_id_int,
                class_id=class_id_int
            )
        except Exception as e:
            st.error(f"Failed to load subjects: {e}")
            st.session_state.subjects = []

    subjects = st.session_state.subjects

    if not subjects:
        st.info("🚫 No subjects available for your class. Contact admin.")
        st.stop()
    # -------------------------
    # 📘 SUBJECT SELECTION
    # -------------------------
    st.markdown("#### 📘 Select Subject")

    selected_subject = st.selectbox(
        "Subject",
        subjects,
        format_func=lambda s: s.name,
        key="subject_select_box"
    )

    selected_subject_id = selected_subject.id
    selected_subject_name = selected_subject.name

    # -------------------------
    # 🔄 SUBJECT CHANGE RESET
    # -------------------------
    if st.session_state.subject is None:
        st.session_state.subject = selected_subject_name

    elif st.session_state.subject != selected_subject_name:
        reset_keys = [
            "test_started", "submitted", "answers", "questions",
            "current_q", "current_page", "marked_for_review",
            "start_time", "test_end_time", "five_min_warned",
            "saved_to_db", "last_auto_save", "confirm_submit",
            "final_submit", "answered_count", "unanswered"
        ]

        for key in reset_keys:
            st.session_state[key] = (
                set() if key == "marked_for_review"
                else [] if key in ["answers", "questions"]
                else False if isinstance(st.session_state.get(key), bool)
                else None
            )

        st.session_state.subject = selected_subject_name
        st.rerun()

    if selected_subject_id is None:
        st.info(f"🚫 Subject ID not found for '{selected_subject}'")
        st.stop()

    # -------------------------
    # ❓ LOAD QUESTIONS (CACHED)
    # -------------------------
    key_obj = f"objective_{selected_subject_id}_{class_id_int}_{school_id_int}"
    key_subj = f"subjective_{selected_subject_id}_{class_id_int}_{school_id_int}"

    if key_obj not in st.session_state:
        st.session_state[key_obj] = get_objective_questions(
            class_id=class_id,
            subject_id=selected_subject_id,
            school_id=school_id_int
        ) or []

    if key_subj not in st.session_state:
        st.session_state[key_subj] = get_subjective_questions(
            class_id=class_id,
            subject_id=selected_subject_id,
            school_id=school_id_int
        ) or []

    objective_questions = st.session_state[key_obj]
    subjective_questions = st.session_state[key_subj]
    # -------------------------

    # -------------------------
    # 🧩 TEST TYPE SELECTION
    # -------------------------
    st.markdown(
        """
        <div style='font-size:20px; font-weight:bold;
        color:#f3f6f6; border-bottom:4px solid #4CAF50;
        padding-bottom:2px; margin-bottom:10px;'>
        🧩 Choose Test Type
        </div>
        """,
        unsafe_allow_html=True
    )

    if "test_type" not in st.session_state:
        st.session_state.test_type = "objective"

    test_options = ["Objective", "Subjective"]
    default_index = 0 if st.session_state.test_type == "objective" else 1

    test_choice = st.radio(
        "Choose type",
        test_options,
        index=default_index,
        horizontal=True,
        key=f"test_type_radio_{class_id}_{selected_subject_id}"
    )

    selected_type = test_choice.lower()

    if selected_type != st.session_state.test_type:
        st.session_state.test_type = selected_type

    # -------------------------
    # 👤 VALIDATE STUDENT
    # -------------------------
    student_info = st.session_state.get("student")

    access_code = (
        student_info.get(
            "access_code",
            ""
        ).strip()
    )

    if not student_info or not student_info.get("id"):
        st.info("🚫 Student ID missing. Please log in again.")
        st.stop()

    student_id = student_info["id"]

    # -------------------------
    # CACHE PROGRESS
    # -------------------------
    progress_key = (
        f"progress_"
        f"{student_id}_"
        f"{selected_subject_id}_"
        f"{class_id_int}_"
        f"{school_id_int}_"
        f"{st.session_state.test_type}"
    )

    if progress_key not in st.session_state:

        db = get_session()

        try:

            record = (
                db.query(StudentProgress)
                .filter_by(
                    student_id=student_id,
                    access_code=access_code,
                    subject_id=selected_subject_id,
                    class_id=class_id_int,
                    school_id=school_id_int,
                    test_type=st.session_state.test_type
                )
                .first()
            )

            if record is None:
                record = StudentProgress(
                    student_id=student_id,
                    access_code=access_code,
                    subject_id=selected_subject_id,
                    class_id=class_id_int,
                    school_id=school_id_int,
                    test_type=st.session_state.test_type,
                    start_time=None,
                    duration=None,
                    submitted=False,
                    locked=False
                )

                db.add(record)
                db.commit()
                db.refresh(record)

            st.session_state[progress_key] = record

        finally:
            db.close()

    record = st.session_state[progress_key]

    # -------------------------
    # FLAGS
    # -------------------------
    is_locked = bool(record.locked)

    is_submitted = bool(record.submitted)

    # -------------------------
    # RETAKE
    # -------------------------
    retake_allowed = can_take_test(
        student_id,
        selected_subject_id,
        school_id_int,
        st.session_state.test_type
    )

    start_disabled = (
            (is_submitted and not retake_allowed)
            or
            (is_locked and not retake_allowed)
    )

    # -------------------------
    # 🚀 START / RESUME UI
    # -------------------------
    start_clicked = False
    resume_clicked = False
    saved_progress = None

    if not st.session_state.get("test_started", False):

        # -------------------------
        # CACHE DB PROGRESS
        # -------------------------
        progress_key = (
            f"progress_"
            f"{student_id}_"
            f"{selected_subject_id}_"
            f"{st.session_state.test_type}"
        )

        if progress_key not in st.session_state:
            st.session_state[progress_key] = load_progress(
                access_code=access_code,
                subject_id=selected_subject_id,
                class_id=class_id_int,
                school_id=school_id_int,
                test_type=st.session_state.test_type,
                student_id=student_id
            )

        saved_progress = st.session_state[progress_key]

        # -------------------------
        # Resume button logic
        # -------------------------
        # -------------------------
        # Resume button logic
        # -------------------------
        resume_disabled = False

        if saved_progress:
            resume_disabled = (
                    saved_progress.get("submitted", False)
                    and not retake_allowed
            )

        col1, col2 = st.columns(2)

        start_clicked = col1.button(
            "🚀 Start Test",
            key=f"start_btn_{selected_subject_id}_{st.session_state.test_type}",
            disabled=start_disabled
        )

        if saved_progress:
            resume_clicked = col2.button(
                "🔄 Resume Test",
                key=f"resume_btn_{selected_subject_id}_{st.session_state.test_type}",
                disabled=resume_disabled
            )


    # -------------------------
    # ACTION HANDLING
    # -------------------------
    if start_clicked:

        if saved_progress and not saved_progress.get(
                "submitted",
                False
        ):

            saved_start_time = saved_progress.get(
                "start_time"
            )

            saved_duration = saved_progress.get(
                "duration"
            )

            if saved_start_time and saved_duration:

                if isinstance(
                        saved_start_time,
                        datetime
                ):
                    saved_end_time = (
                            saved_start_time +
                            timedelta(
                                seconds=saved_duration
                            )
                    )

                else:
                    saved_end_time = (
                            datetime.fromtimestamp(
                                saved_start_time
                            ) +
                            timedelta(
                                seconds=saved_duration
                            )
                    )

                if datetime.now() < saved_end_time:
                    st.warning(
                        "⚠️ You have an unfinished test. Please resume instead."
                    )
                    st.stop()

        st.session_state.test_action = "start"
        st.session_state.test_started = True
        st.rerun()

    if resume_clicked:
        st.session_state.test_action = "resume"
        st.session_state.test_started = True
        st.rerun()

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
    # -------------------------
    # 🎯 MAIN TEST FLOW
    # -------------------------
    if st.session_state.get("test_started"):

        action = st.session_state.get("test_action")

        # ---------------------------------
        # Cache duration once
        # ---------------------------------
        if "duration_minutes" not in st.session_state:
            st.session_state.duration_minutes = (
                    get_test_duration(
                        class_id=class_id,
                        subject_id=selected_subject_id,
                        school_id=school_id_int
                    ) or 30
            )

        duration_minutes = st.session_state.duration_minutes


        # -------------------------
        # 🔵 START NEW TEST
        # -------------------------
        if action == "start":

            import random

            # -------------------------
            # Get question bank
            # -------------------------
            question_bank = (
                objective_questions
                if st.session_state.test_type == "objective"
                else subjective_questions
            )

            # ✅ FORCE REAL LIST
            question_bank = list(question_bank)

            # ✅ TRUE RANDOMIZATION
            random.shuffle(question_bank)

            # -------------------------
            # Normalize questions
            # -------------------------
            normalized_questions = []

            for q in question_bank:

                question_dict = {
                    "id": q.id,
                    "text": q.question_text,
                }

                if st.session_state.test_type == "objective":

                    question_dict["options"] = getattr(q, "options", [])

                    question_dict["correct_answer"] = getattr(
                        q,
                        "correct_answer",
                        ""
                    )

                else:

                    question_dict["options"] = None
                    question_dict["correct_answer"] = None

                normalized_questions.append(question_dict)

            # ✅ SAVE RANDOMIZED ORDER
            st.session_state.questions = normalized_questions

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

                # ✅ SAVE RANDOMIZED ORDER
                questions=json.dumps([
                    q["id"]
                    for q in normalized_questions
                ]),

                student_id=student_id,

                submitted=False
            )

            st.session_state.test_action = None

            st.rerun()


        # -------------------------
        # 🟩 RESUME TEST
        # -------------------------
        elif action == "resume":

            saved_progress = load_progress(
                access_code=access_code,
                subject_id=selected_subject_id,
                class_id=class_id_int,
                school_id=school_id_int,
                test_type=st.session_state.test_type,
                student_id=student_id
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
            normalized_questions = [
                {
                    "id": q.id,
                    "text": q.question_text,
                    "options": getattr(q, "options", None),
                    "correct_answer": getattr(q, "correct_answer", "")
                }
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

        # -------------------------
        # 💾 CONTINUOUS SAVE (SAFE)
        # -------------------------
        if not is_submitted:

            # IMPORTANT: keep DB format consistent
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
                submitted=False
            )

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


        # ✅ AUTO-INITIALIZE TEST (CRITICAL FIX)
        if st.session_state.get("test_started") and not st.session_state.get("test_end_time"):
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

            # IMPORTANT: initialize in STRUCTURED format (not strings)
            st.session_state.answers = [
                {
                    "question_id": q.id if hasattr(q, "id") else q.get("id"),
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
                    st.session_state.start_time
                    + timedelta(seconds=st.session_state.duration)
            )

            st.session_state.marked_for_review = set()
            st.session_state.paste_count = 0

        # =============================
        # ⏱️ TIMER (BEFORE RENDER)
        # =============================
        now = datetime.now()

        # ✅ FIX: ensure test is initialized
        if not st.session_state.get("test_end_time"):
            st.warning("Initializing test...")
            st.stop()  # ⛔ stops execution BEFORE crash

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
                background-color:#cbd5c0;
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
                background-color:#cbd5c0;
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
        if remaining_seconds <= 0 and not is_submitted:

            st.warning("⏰ Time is up! Submitting your test automatically...")

            start_time_ts = (
                st.session_state.start_time.timestamp()
                if isinstance(st.session_state.start_time, datetime)
                else st.session_state.start_time
            )

            subject_id = selected_subject.id

            # 1️⃣ Save final progress (submitted=True)
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
                questions=[q.id for q in st.session_state.questions],
                submitted=True
            )

            # 2️⃣ Persist answers safely
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

                    # Mark submitted
                    progress.submitted = True

                    # Subjective review queue
                    if st.session_state.test_type == "subjective":
                        progress.review_status = "pending"

                    for i, q in enumerate(st.session_state.questions):

                        ans = (
                            st.session_state.answers[i]
                            if i < len(st.session_state.answers)
                            else ""
                        )

                        existing = db.query(StudentAnswer).filter_by(
                            progress_id=progress.id,
                            question_id=q["id"]
                        ).first()

                        if existing:

                            existing.answer = ans

                        else:

                            db.add(
                                StudentAnswer(
                                    progress_id=progress.id,
                                    question_id=q["id"],
                                    answer=ans
                                )
                            )

                    db.commit()
            finally:
                db.close()

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

            clean_options = [str(opt).strip().strip('"').strip("'") for opt in options]
            choices = ["Choose answer"] + clean_options

            selected_index = choices.index(prev_answer) if prev_answer in choices else 0

            selected_option = st.radio(
                "Choose an option:",
                choices,
                index=selected_index,
                key=f"q_{current_q_idx}",
                disabled=time_up or st.session_state.get("submitted", False)
            )


            st.session_state.answers[current_q_idx] = (
                "" if selected_option == "Choose answer" else selected_option
            )

            # Save to DB
            db = get_session()
            try:
                save_answer(
                    db=db,
                    progress_id=record.id,
                    question_id=q["id"],
                    answer=st.session_state.answers[current_q_idx]
                )
            finally:
                db.close()


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
            # Initialize counter once
            # -------------------------
            if "copy_paste_count" not in st.session_state:
                st.session_state.copy_paste_count = 0

            # -------------------------
            # Detect violation
            # -------------------------
            violation_type = st.query_params.get("violation")

            if isinstance(violation_type, list):
                violation_type = violation_type[0]

            violation_type = str(violation_type).strip().lower() if violation_type else None

            if violation_type not in (None, "", "none"):
                try:

                    # Streamlit may return list
                    if isinstance(violation_type, list):
                        violation_type = violation_type[0]

                    violation_type = str(
                        violation_type
                    ).strip().lower()

                    progress_id = getattr(
                        record,
                        "id",
                        None
                    )

                    question_id = (
                        q.get("id")
                        if isinstance(q, dict)
                        else None
                    )

                    # Save violation
                    log_violation(
                        progress_id=progress_id,
                        student_id=student_id,
                        subject_id=selected_subject.id,
                        question_id=question_id,
                        school_id=school_id_int,
                        test_type="subjective",
                        event_type=violation_type
                    )

                    # Increase counter
                    st.session_state.copy_paste_count += 1

                    st.warning(
                        f"⚠️ {violation_type.upper()} detected "
                        f"({st.session_state.copy_paste_count})"
                    )

                    # Auto-submit after limit
                    if st.session_state.copy_paste_count >= 3:
                        st.error(
                            "🚫 Multiple violations detected. "
                            "Test auto-submitted."
                        )

                        st.session_state.auto_submitted = True
                        st.session_state.final_submit = True
                        st.rerun()

                except Exception as e:

                    st.error(
                        f"Violation logging failed: {e}"
                    )

                finally:

                    # Clear query params
                    st.query_params.pop("violation", None)
                    st.query_params.pop("time", None)

            # -------------------------
            # Restore current answer
            # -------------------------
            current_answer = ""

            if current_q_idx < len(
                    st.session_state.answers
            ):

                saved = st.session_state.answers[
                    current_q_idx
                ]

                if isinstance(saved, dict):

                    current_answer = (
                            saved.get("answer")
                            or saved.get("selected")
                            or ""
                    )

                elif saved:

                    current_answer = str(saved)

            # -------------------------
            # Text area
            # -------------------------
            answer = st.text_area(
                "Type your answer:",
                value=current_answer,
                key=current_key,
                height=150,
                disabled=time_up_or_submitted
            )

            # -------------------------
            # Save session answer
            # -------------------------
            if not (
                    is_submitted
                    or is_locked
            ):
                st.session_state.answers[
                    current_q_idx
                ] = answer

            # -------------------------
            # Sticky warning
            # -------------------------
            st.markdown(
                f"""
                <div style="
                     padding: 6px 8px;
                    border-radius: 8px;
                    background-color:#cbd5c0;
                    border: 2px solid {timer_border_color};
                    color: #111827;
                    text-align: center;
                    font-size: 16px;
                    font-weight: 600;
                    margin-bottom: 8px;
                    box-shadow: 0 2px 6px rgba(0,0,0,0.15);
                ">
                    ⚠️ Copy/Paste activity is monitored.
                    Multiple violations may auto-submit the test.
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
            # Save answer only if changed
            # -------------------------
            answer_key = (
                f"saved_answer_"
                f"{current_q_idx}"
            )

            previous = st.session_state.get(
                answer_key
            )

            if previous != answer:

                st.session_state[
                    answer_key
                ] = answer

                db = get_session()

                try:

                    save_answer(
                        db=db,
                        progress_id=record.id,
                        question_id=q["id"],
                        answer=answer
                    )

                finally:

                    db.close()




            # -------------------------
            # Navigation & Submit Buttons
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

                subject_id = selected_subject.id
                test_type = st.session_state.test_type

                # SUBJECTIVE / OBJECTIVE
                # KEEP YOUR EXISTING BLOCK BELOW
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

                            progress = db.query(
                                StudentProgress
                            ).filter_by(
                                student_id=student_id,
                                subject_id=subject_id,
                                class_id=class_id,
                                school_id=school_id_int,
                                test_type="subjective"
                            ).order_by(
                                StudentProgress.created_at.desc()
                            ).first()

                            if progress:

                                # Required for Awaiting Review list
                                progress.submitted = True

                                # Do not lock; teacher still grades
                                progress.locked = False

                                # Put into review queue
                                progress.review_status = "pending"

                                # reset review fields
                                progress.reviewed_at = None
                                progress.reviewed_by = None

                                # mark auto-submit source
                                if auto_submit_triggered:
                                    progress.review_comment = (
                                        "Auto-submitted after "
                                        "multiple copy/paste violations"
                                    )

                            db.commit()

                        except Exception as e:

                            db.rollback()

                            st.error(
                                f"❌ Failed updating progress: {e}"
                            )

                        finally:

                            db.close()

                        # -------------------------
                        # Consume retake
                        # -------------------------
                        try:

                            db = get_session()

                            student_obj = db.query(
                                Student
                            ).filter_by(
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

                            st.error(
                                f"❌ Retake update failed: {e}"
                            )

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

                        subject=selected_subject.name,

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
                            f"{selected_subject.name}_"
                            f"{pdf_test_type}_result.pdf"
                        ),

                        mime="application/pdf"
                    )
