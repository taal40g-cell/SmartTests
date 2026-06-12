import streamlit as st
import json
from backend.database import get_session
from datetime import datetime, timedelta
from backend.models import ObjectiveQuestion
from backend.models import(
    SubjectiveQuestion,
    AntiCheatLog,
    TestResult,
    School,


)

from backend.db_helpers import (
    save_progress,get_student_by_access_code,
    calculate_score_db,StudentProgress,Student,
    normalize_objective,parse_json_field,
    normalize_subjective,load_progress
)

from sqlalchemy.orm import joinedload
from backend.ui import  generate_pdf
# ======================================================
# 🧠 SUBJECTIVE TEST HELPERS
# ======================================================
def add_subjective_question(school_id, class_name, subject_id, question_text, marks=10):
    """Admin adds a new subjective question."""
# ✅ adjust path if different


    db = get_session()
    try:
        new_q = SubjectiveQuestion(
            school_id=school_id,
            class_name=class_name,
            subject_id=subject_id,
            question_text=question_text,
            marks=marks,
            created_at=datetime.utcnow(),
        )
        db.add(new_q)
        db.commit()
        return True, "✅ Question added successfully."
    except Exception as e:
        db.rollback()
        return False, f"❌ Failed to add question: {e}"
    finally:
        db.close()


# =====================================================
#
# =====================================================
def get_subjective_questions(class_id, subject_id, school_id):
    """Return all subjective questions for a class + subject + school"""

    from backend.database import get_session
    db = get_session()

    try:
        questions = (
            db.query(SubjectiveQuestion)
            .filter(
                SubjectiveQuestion.class_id == class_id,
                SubjectiveQuestion.subject_id == subject_id,
                SubjectiveQuestion.school_id == school_id
            )
            .all()
        )

        return questions

    finally:
        db.close()





# =====================================================
#
# =====================================================
def grade_subjective_answer(school_id, answer_id, teacher_id, score, comment=""):
    """Teacher grades a student's subjective answer."""
    from models import SubjectiveGrade

    db = get_session()
    try:
        grade = SubjectiveGrade(
            school_id=school_id,
            answer_id=answer_id,
            teacher_id=teacher_id,
            score=score,
            comment=comment,
            graded_on=datetime.utcnow(),
        )
        db.add(grade)
        db.commit()

        # Optional: update answer status
        from models import SubjectiveAnswer
        ans = db.query(SubjectiveAnswer).filter_by(id=answer_id).first()
        if ans:
            ans.status = "Graded"
            db.commit()

        return True, "✅ Answer graded successfully."
    except Exception as e:
        db.rollback()
        return False, f"❌ Grading failed: {e}"
    finally:
        db.close()





# =============================================
# SAVE: Student Answers (Objective + Subjective)
# =============================================
def save_student_answers(access_code, subject, questions, answers):
    """
    Save student answers:
    - Objective → submissions table
    - Subjective → student_answers linked to student_progress
    """
    from backend.models import Student,  StudentProgress, StudentAnswer
    db = get_session()

    try:
        # ---------------------------------------------
        # 1️⃣ Get student by access code
        # ---------------------------------------------
        student = db.query(Student).filter(Student.access_code == access_code).first()
        if not student:
            print("❌ Student not found for access code:", access_code)
            return

        student_id = student.id
        school_id = student.school_id

        # ---------------------------------------------
        # 2️⃣ Separate objective vs subjective questions
        # ---------------------------------------------
        objective_items = []
        subjective_items = []

        for q, ans in zip(questions, answers):
            q_type = q.get("type", "objective").lower()
            if q_type == "objective":
                objective_items.append((q, ans))
            else:
                subjective_items.append((q, ans))

        # ---------------------------------------------
        # 3️⃣ Save objective answers into submissions
        # ---------------------------------------------
        for q, ans in objective_items:
            qid = q.get("id")
            correct_answer = q.get("correct_answer_text", "")
            db.add(
                TestResult(
                    student_id=student_id,
                    question_id=qid,
                    selected_answer=ans,
                    correct=...
                )
            )
        # ---------------------------------------------
        # 4️⃣ Handle subjective answers → student_progress + student_answers
        # ---------------------------------------------
        if subjective_items:
            # Check if progress exists, else create
            progress = db.query(StudentProgress).filter_by(
                student_id=student_id,
                subject=subject,
                school_id=school_id
            ).first()

            if not progress:
                progress = StudentProgress(
                    student_id=student_id,
                    subject=subject,
                    school_id=school_id,
                    submitted=True,      # Mark as submitted
                    review_status="pending",
                    reviewed_at=None,
                    score=None,
                    locked=True
                )
                db.add(progress)
                db.flush()  # ensure progress.id is populated
            else:
                # Update existing progress
                progress.submitted = True
                progress.locked = True
                progress.review_status = "pending"
                progress.reviewed_at = None
                progress.score = None
                db.add(progress)
                db.flush()

            # Add each subjective answer
            for q, ans in subjective_items:
                db.add(
                    StudentAnswer(
                        progress_id=progress.id,
                        question_id=q.get("id"),
                        answer=ans
                    )
                )

        # ---------------------------------------------
        # 5️⃣ Commit all changes
        # ---------------------------------------------
        db.commit()
        print("✅ Saved all answers successfully")

    except Exception as e:
        db.rollback()
        print("❌ Error saving answers:", e)

    finally:
        db.close()




# -----------------------------------------------------
#
# -----------------------------------------------------
def handle_subjective_submission(
    student_id,
    school_id,
    subject_id,
    answers,
    questions
):

    db = get_session()

    try:
        progress = (
            db.query(StudentProgress)
            .filter_by(
                student_id=student_id,
                subject_id=subject_id,
                school_id=school_id,
                test_type="subjective"
            )
            .first()
        )

        if not progress:
            raise Exception("Progress record not found.")

        # 🚨 HARD PROTECTION
        if progress.locked or progress.review_status == "reviewed":
            return "finalized"

        # 🚨 Prevent resubmission
        if progress.submitted:
            return "already_submitted"

        # ---------------------------------
        # Normalize question IDs
        # ---------------------------------
        question_ids = []

        for q in questions:

            # SQLAlchemy object
            if hasattr(q, "id"):
                question_ids.append(q.id)

            # dictionary question
            elif isinstance(q, dict):
                qid = q.get("id")

                if qid is not None:
                    question_ids.append(qid)

            # raw numeric/string id
            else:
                try:
                    question_ids.append(int(q))
                except:
                    pass
        # ---------------------------------
        # Save answers
        # ---------------------------------
        progress.answers = list(answers)
        progress.questions = question_ids
        progress.submitted = True
        progress.review_status = "pending"
        progress.reviewed_at = None
        progress.score = None

        db.commit()

        return "submitted"

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


    # =========================================
    #
    # =========================================

@st.cache_data(ttl=300)
def get_objective_questions(
    class_id: int,
    subject_id: int,
    school_id: int | None = None
):
    db = get_session()

    try:
        questions = (
            db.query(ObjectiveQuestion)
            .filter(
                ObjectiveQuestion.class_id == class_id,
                ObjectiveQuestion.subject_id == subject_id,
                ObjectiveQuestion.school_id == school_id
                if school_id is not None
                else True,
            )
            .order_by(ObjectiveQuestion.id.asc())
            .all()
        )

        return [
            {
                "id": q.id,
                "question_text": q.question_text,
                "options": q.options,
                "correct_answer": q.correct_answer,
            }
            for q in questions
        ]

    finally:
        db.close()


# =========================================
#
# =========================================
def force_submit_test(reason="Violation detected"):
    """
    Force-submit the current test session.
    Used for anti-cheat, timeout, or abnormal behavior.
    """
    if st.session_state.get("submitted"):
        return  # Prevent double submission

    st.session_state.submitted = True
    st.session_state.auto_submitted = True
    st.session_state.auto_submit_reason = reason

    # 🔹 Calculate score
    correct, wrong, details = calculate_score_db(
        st.session_state.student_name,
        st.session_state.selected_subject,
        st.session_state.questions,
        st.session_state.answers
    )

    # 🔹 Save progress to DB
    save_progress(
        access_code=st.session_state.access_code,
        subject_id=st.session_state.selected_subject_id,
        class_id=st.session_state.class_id,
        answers=st.session_state.answers,
        current_q=st.session_state.current_q if "current_q" in st.session_state else 0,
        start_time=st.session_state.start_time if "start_time" in st.session_state else None,
        duration=st.session_state.duration if "duration" in st.session_state else 0,
        questions=st.session_state.questions,
        school_id=st.session_state.school_id,
        test_type=st.session_state.test_type,
        student_id=st.session_state.student_id,
        submitted=True
    )

    st.error(f"🚫 Test auto-submitted: {reason}")
    st.stop()

def log_anti_cheat_event(progress_id, student_id, subject_id, school_id, test_type, event_type):

    db = get_session()

    try:
        log = AntiCheatLog(
            progress_id=progress_id,
            student_id=student_id,
            subject_id=subject_id,
            school_id=school_id,
            test_type=test_type,
            event_type=event_type,
            timestamp=datetime.utcnow()
        )

        db.add(log)
        db.commit()

    except Exception as e:
        db.rollback()
        print("❌ Anti-cheat log error:", e)

    finally:
        db.close()



# =========================================
#
# =========================================
def handle_violation(event_type, progress_id, student_id, subject_id, school_id):

    # 🔒 Log violation in database
    log_anti_cheat_event(
        progress_id=progress_id,
        student_id=student_id,
        subject_id=subject_id,
        school_id=school_id,
        test_type=st.session_state.test_type,
        event_type=event_type
    )

    key_map = {
        "TAB_HIDDEN": "tab_hidden_count",
        "WINDOW_BLUR": "window_blur_count",
        "RIGHT_CLICK": "right_click_count",
        "COPY_PASTE": "copy_paste_count",
        "DEVTOOLS_ATTEMPT": "devtools_attempt_count",
        "DEVTOOLS_OPEN": "devtools_open_count"
    }

    key = key_map.get(event_type)

    if key:
        st.session_state[key] = st.session_state.get(key, 0) + 1

    # 🚨 Enforcement
    if (
        st.session_state.get("tab_hidden_count", 0) >= 3 or
        st.session_state.get("window_blur_count", 0) >= 5 or
        st.session_state.get("right_click_count", 0) >= 3 or
        st.session_state.get("copy_paste_count", 0) >= 3 or
        st.session_state.get("devtools_attempt_count", 0) >= 1 or
        st.session_state.get("devtools_open_count", 0) >= 1
    ):
        st.info("🚫 Anti-cheat violation limit reached. Test submitted automatically To Prevent exam\n\n "
                "Mal-Practise and Assure exam Fairness.")

        st.session_state.submitted = True

        force_submit_test(reason="Anti-cheat violation")

        st.stop()


# =========================================
#
# =========================================
from backend.models import StudentAnswer,Class
def save_answer(db, progress_id, question_id, answer):
    """
    Save or update a single answer for a test session.
    """

    try:

        # Check if answer already exists
        existing = db.query(StudentAnswer).filter_by(
            progress_id=progress_id,
            question_id=question_id
        ).first()

        if existing:

            # Update existing answer
            existing.answer = answer
            existing.created_at = datetime.utcnow()

        else:

            # Create new answer
            new_answer = StudentAnswer(
                progress_id=progress_id,
                question_id=question_id,
                answer=answer
            )

            db.add(new_answer)

        db.commit()

    except Exception as e:

        db.rollback()

        print(f"save_answer error: {e}")

        raise e



# =========================================
#
# =========================================
def normalize_question(q):
    # supports BOTH dict and ORM safely
    return {
        "id": q["id"] if isinstance(q, dict) else getattr(q, "id", None),

        "text": (
                    q.get("question_text")
                    if isinstance(q, dict) else getattr(q, "question_text", None)
                )
                or (
                    q.get("question")
                    if isinstance(q, dict) else getattr(q, "question", None)
                )
                or (
                    q.get("text")
                    if isinstance(q, dict) else getattr(q, "text", None)
                )
                or "No Question",

        "options": (
            q.get("options", [])
            if isinstance(q, dict) else getattr(q, "options", [])
        ),

        "correct_answer": (
            q.get("correct_answer", "")
            if isinstance(q, dict) else getattr(q, "correct_answer", "")
        )
    }



    # =========================================================
    # 📊 RESULTS CENTER
    # =========================================================
def render_results_center():

    with st.sidebar:

        st.header("📊 Results Center")

        school_id = st.session_state.get("school_id")
        student_id = st.session_state.get("student_id")

        objective_records = []
        subjective_records = []
        records = []

        if school_id and student_id:

            db = get_session()

            try:
                stud = (
                    db.query(Student)
                    .filter(
                        Student.id == student_id,
                        Student.school_id == school_id
                    )
                    .first()
                )

                if stud:
                    records = (
                        db.query(StudentProgress)
                        .options(joinedload(StudentProgress.subject))
                        .filter(
                            StudentProgress.student_id == student_id,
                            StudentProgress.school_id == school_id,
                            StudentProgress.submitted == True
                        )
                        .order_by(StudentProgress.created_at.desc())
                        .all()
                    )

            finally:
                db.close()

            objective_records = [
                r for r in records if r.test_type == "objective"
            ]

            subjective_records = [
                r for r in records if r.test_type == "subjective"
            ]

        # =====================================================
        # OBJECTIVE TESTS
        # =====================================================

        st.markdown("### 📘 Objective Tests")

        if not objective_records:
            st.caption("No objective tests yet.")
        else:
            for r in objective_records:

                subject_name = r.subject.name if r.subject else "Unknown"

                details = normalize_objective(parse_json_field(r.answers))

                total_q = len(details)

                correct = sum(
                    1 for d in details
                    if d.get("is_correct", False)
                )

                percent = (correct / total_q * 100) if total_q else 0

                with st.expander(f"{subject_name} — {int(percent)}%"):

                    st.write(f"Score: {correct}/{total_q}")

                    st.write(
                        f"Date: {r.created_at.strftime('%Y-%m-%d %H:%M')}"
                    )

                    if st.toggle("View Breakdown", key=f"obj_{r.id}"):

                        for i, d in enumerate(details, start=1):
                            st.markdown(f"**Q{i}**")
                            st.write(d["question_text"])
                            st.write(f"Your Answer: {d['selected']}")
                            st.write(f"Correct: {d['correct']}")
                            st.write("✅ Correct" if d["is_correct"] else "❌ Wrong")
                            st.markdown("---")

                pdf_bytes = generate_pdf(
                    name=stud.name,
                    class_name=st.session_state.get("class_name", "Unknown Class"),
                    subject=subject_name,
                    correct=correct,
                    total=total_q,
                    percent=percent,
                    details=details,
                    school_name=st.session_state.get("school_name"),
                    school_id=school_id,
                    test_type="objective"
                )

                st.download_button(
                    "📄 Download PDF",
                    pdf_bytes,
                    file_name=f"{stud.name}_{subject_name}_objective.pdf",
                    mime="application/pdf",
                    key=f"obj_pdf_{r.id}"
                )

        st.markdown("---")

        # =====================================================
        # SUBJECTIVE TESTS
        # =====================================================

        st.markdown("### ✍️ Subjective Tests")

        if not subjective_records:
            st.caption("No subjective tests yet.")
            return

        pending_count = sum(
            1 for r in subjective_records
            if r.review_status == "pending"
        )

        if pending_count:
            st.markdown(
                f"""
                <div style="
                    background-color:#eef7ff;
                    border-left:5px solid #4da3ff;
                    color:#0f3d66;
                    padding:12px 15px;
                    border-radius:8px;
                    font-weight:600;
                    margin-bottom:15px;
                ">
                🔔 You have {pending_count} subjective test(s)
                awaiting teacher review.
                </div>
                """,
                unsafe_allow_html=True
            )

        for r in subjective_records:

            subject_name = r.subject.name if r.subject else "Unknown"

            details = normalize_subjective(parse_json_field(r.answers))

            total_q = len(details)

            score = r.score if r.score is not None else 0

            percent = (score / total_q * 100) if total_q else 0

            pending = (r.review_status == "pending")

            title = (
                f"{subject_name} — 🟡 Awaiting Review"
                if pending
                else f"{subject_name} — ✅ Reviewed"
            )

            with st.expander(title):

                if not pending:
                    st.success(f"✅ Final Score: {score}/{total_q}")

                st.write(
                    f"📅 Submitted: {r.created_at.strftime('%d %b %Y, %I:%M %p')}"
                )

                if st.toggle("View Breakdown", key=f"subj_{r.id}"):

                    for i, d in enumerate(details, start=1):
                        st.markdown(f"### Q{i}")
                        st.write(f"Question: {d.get('question', 'No Question')}")
                        st.write(f"Answer: {d.get('answer', 'No Answer')}")
                        st.write(f"Teacher Score: {d.get('teacher_score', 'Pending')}")
                        st.markdown("---")

                pdf_bytes = generate_pdf(
                    name=stud.name,
                    class_name=st.session_state.get("class_name", "Unknown Class"),
                    subject=subject_name,
                    correct=score,
                    total=total_q,
                    percent=percent,
                    details=details,
                    school_name=st.session_state.get("school_name"),
                    school_id=school_id,
                    test_type="subjective"
                )

                st.download_button(
                    "📄 Download PDF",
                    pdf_bytes,
                    file_name=f"{stud.name}_{subject_name}_subjective.pdf",
                    mime="application/pdf",
                    key=f"subj_pdf_{r.id}"
                )



# =========================================
#
# =========================================
def render_student_login():

    # Already logged in
    if st.session_state.get("logged_in", False):
        return st.session_state.get("student")

    # Load schools
    db = get_session()

    try:
        schools = (
            db.query(School)
            .filter(School.is_system == False)
            .all()
        )

    finally:
        db.close()

    if not schools:
        st.warning("❌ No schools found. Contact admin.")
        return None

    school_map = {
        s.name: s.id
        for s in schools
    }

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

    if not login_btn:
        return None

    if not selected_school_name:
        st.warning("Select a school")
        return None

    access_code = access_code_input.strip().upper()

    if not access_code:
        st.warning("Enter access code")
        return None

    selected_school_id = school_map.get(
        selected_school_name
    )

    student_obj = get_student_by_access_code(
        access_code,
        school_id=selected_school_id
    )

    if not student_obj:
        st.error(
            "❌ Invalid code for selected school"
        )
        return None

    student = {
        "id": student_obj.id,
        "unique_id": getattr(student_obj, "unique_id", ""),
        "name": student_obj.name,
        "class_id": student_obj.class_id,
        "school_id": student_obj.school_id,
        "access_code": access_code,
        "can_retake": bool(
            getattr(student_obj, "can_retake", True)
        ),
    }

    db = get_session()

    try:

        class_obj = (
            db.query(Class)
            .filter_by(id=student["class_id"])
            .first()
        )

        school_obj = (
            db.query(School)
            .filter_by(id=student["school_id"])
            .first()
        )

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

    finally:
        db.close()

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

    st.rerun()





# =========================================
#
# =========================================
def render_start_resume_controls(
    saved_progress,
    retake_allowed,
    start_disabled,
    selected_subject_id
):
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

    resume_clicked = False

    if saved_progress:
        resume_clicked = col2.button(
            "🔄 Resume Test",
            key=f"resume_btn_{selected_subject_id}_{st.session_state.test_type}",
            disabled=resume_disabled
        )

    return start_clicked, resume_clicked


# =========================================
#
# =========================================
def handle_test_actions(
    start_clicked,
    resume_clicked,
    saved_progress
):

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

                saved_end_time = (
                    datetime.fromtimestamp(saved_start_time)
                    + timedelta(seconds=saved_duration)
                )

                if datetime.now() < saved_end_time:
                    st.warning(
                        "⚠️ You have an unfinished test. Please resume instead."
                    )
                    st.stop()

        st.session_state["test_action"] = "start"
        st.session_state["test_started"] = True
        st.rerun()

    if resume_clicked:
        st.session_state["test_action"] = "resume"
        st.session_state["test_started"] = True




# =========================================
#
# =========================================
def get_saved_progress(
        access_code,
        subject_id,
        class_id,
        school_id,
        test_type,
        student_id
):
    progress = load_progress(
        access_code=access_code,
        subject_id=subject_id,
        class_id=class_id,
        school_id=school_id,
        test_type=test_type,
        student_id=student_id
    )

    if not progress:
        st.warning("⚠️ No unfinished test to resume.")
        st.session_state.test_started = False
        st.session_state.test_action = None
        st.stop()

    if progress.get("submitted", False):
        st.warning("⚠️ This test was already submitted.")
        st.session_state.test_started = False
        st.session_state.test_action = None
        st.stop()

    if not progress.get("start_time") or not progress.get("duration"):
        st.warning("⚠️ No valid test session to resume.")
        st.session_state.test_started = False
        st.session_state.test_action = None
        st.stop()

    return progress





# =========================================
#
# =========================================
def restore_test_session(
        saved_progress,
        objective_questions,
        subjective_questions
):
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

    normalized_questions = [
        normalize_question(q)
        for q in question_bank
    ]

    if saved_questions:

        qmap = {
            q["id"]: q
            for q in normalized_questions
        }

        rebuilt = [
            qmap[qid]
            for qid in saved_questions
            if qid in qmap
        ]

        st.session_state.questions = (
            rebuilt
            if rebuilt
            else normalized_questions
        )

    else:
        st.session_state.questions = normalized_questions

    saved_answers = saved_progress.get(
        "answers",
        [""] * len(st.session_state.questions)
    )

    if isinstance(saved_answers, str):
        try:
            saved_answers = json.loads(saved_answers)
        except:
            saved_answers = [""] * len(st.session_state.questions)

    if not isinstance(saved_answers, list):
        saved_answers = [""] * len(st.session_state.questions)

    st.session_state.answers = saved_answers

    st.session_state.current_q = min(
        max(saved_progress.get("current_q", 0), 0),
        len(st.session_state.questions) - 1
    )

    st.session_state.start_time = datetime.fromtimestamp(
        saved_progress["start_time"]
    )

    st.session_state.duration = int(
        saved_progress["duration"]
    )

    st.session_state.test_end_time = (
        st.session_state.start_time +
        timedelta(seconds=st.session_state.duration)
    )

    st.session_state.auto_submitted = False
    st.session_state.test_action = None


def calculate_remaining_time():
    now_ts = datetime.now().timestamp()

    start_ts = (
        st.session_state.start_time.timestamp()
    )

    elapsed = now_ts - start_ts

    remaining = (
            st.session_state.duration - elapsed
    )

    return remaining




def get_or_create_student_progress(
    student_id,
    access_code,
    subject_id,
    class_id,
    school_id,
    test_type
):
    db = get_session()

    try:
        record = db.query(StudentProgress).filter_by(
            student_id=student_id,
            access_code=access_code,
            subject_id=subject_id,
            class_id=class_id,
            school_id=school_id,
            test_type=test_type
        ).first()

        if record is None:
            record = StudentProgress(
                student_id=student_id,
                access_code=access_code,
                subject_id=subject_id,
                class_id=class_id,
                school_id=school_id,
                test_type=test_type,
                start_time=None,
                duration=None,
                submitted=False,
                locked=False
            )

            db.add(record)
            db.commit()
            db.refresh(record)

        return record

    finally:
        db.close()




def load_question_cache(
    selected_subject_id,
    class_id,
    school_id
):
    key_obj = (
        f"objective_{selected_subject_id}_{class_id}_{school_id}"
    )

    key_subj = (
        f"subjective_{selected_subject_id}_{class_id}_{school_id}"
    )

    if key_obj not in st.session_state:
        st.session_state[key_obj] = (
            get_objective_questions(
                class_id=class_id,
                subject_id=selected_subject_id,
                school_id=school_id
            ) or []
        )

    if key_subj not in st.session_state:
        st.session_state[key_subj] = (
            get_subjective_questions(
                class_id=class_id,
                subject_id=selected_subject_id,
                school_id=school_id
            ) or []
        )

    return (
        st.session_state[key_obj],
        st.session_state[key_subj]
    )






def render_test_type_selector(
    class_id,
    subject_id
):
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

    default_index = (
        0
        if st.session_state.test_type == "objective"
        else 1
    )

    test_choice = st.radio(
        "Choose type",
        test_options,
        index=default_index,
        horizontal=True,
        key=f"test_type_radio_{class_id}_{subject_id}"
    )

    selected_type = test_choice.lower()

    if selected_type != st.session_state.test_type:
        st.session_state.test_type = selected_type

    return st.session_state.test_type




from backend.db_helpers import get_test_duration
def get_duration_minutes(
    class_id,
    subject_id,
    school_id
):
    return (
        get_test_duration(
            class_id=class_id,
            subject_id=subject_id,
            school_id=school_id
        )
        or 30
    )





def render_test_entry_controls(
    access_code,
    subject_id,
    class_id,
    school_id,
    student_id,
    test_type,
    is_submitted,
    is_locked,
    retake_allowed
):
    saved_progress = load_progress(
        access_code=access_code,
        subject_id=subject_id,
        class_id=class_id,
        school_id=school_id,
        test_type=test_type,
        student_id=student_id
    )

    start_clicked, resume_clicked = render_start_resume_controls(
        saved_progress=saved_progress,
        retake_allowed=retake_allowed,
        start_disabled=(is_submitted and not retake_allowed) or (is_locked and not retake_allowed),
        selected_subject_id=subject_id
    )

    handle_test_actions(start_clicked, resume_clicked, saved_progress)

    return saved_progress