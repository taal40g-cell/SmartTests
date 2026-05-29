import streamlit as st
from backend.database import get_session
from backend.models import ObjectiveQuestion
from backend.models import SubjectiveQuestion,AntiCheatLog,TestResult
from backend.db_helpers import save_progress
from backend.db_helpers import calculate_score_db
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
    from backend.models import StudentProgress
    from datetime import datetime

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

def get_objective_questions(class_id: int, subject_id: int, school_id: int | None = None):
    """Fetch all active objective questions for a given class and subject."""
    db = get_session()
    try:
        query = db.query(ObjectiveQuestion).filter(
            ObjectiveQuestion.class_id == class_id,
            ObjectiveQuestion.subject_id == subject_id,
            ObjectiveQuestion.school_id == school_id if school_id is not None else True,
        ).order_by(ObjectiveQuestion.id.asc())

        return query.all()
    finally:
        db.close()



# =========================================
#
# =========================================
def render_subjective_test(questions, subject):
    """Render one-question-per-page subjective test with compact buttons."""
    st.markdown(
        f"<h3 style='text-align:center; color:#2c3e50;'>✍️ {subject} — Subjective Test</h3>",
        unsafe_allow_html=True
    )

    # === Initialize session ===
    st.session_state.setdefault("page", 1)
    total_questions = len(questions)
    st.session_state.setdefault("subj_answers", [""] * total_questions)
    st.session_state.setdefault("subj_files", [None] * total_questions)

    # === Ensure equal array lengths ===
    st.session_state.subj_answers = st.session_state.subj_answers[:total_questions] + [""] * max(0, total_questions - len(st.session_state.subj_answers))
    st.session_state.subj_files = st.session_state.subj_files[:total_questions] + [None] * max(0, total_questions - len(st.session_state.subj_files))

    # === Pagination ===
    page = max(1, min(st.session_state.page, total_questions))
    st.session_state.page = page
    q_index = page - 1
    q = questions[q_index]

    # Load subjective question text safely (supports different key names)
    question_text = (
            q.get("question_text")
            or q.get("question")
            or q.get("text")
            or q.get("title")
    )

    if not question_text:
        question_text = "No question text"

    # === Question Box ===
    st.markdown(f"""
        <div style="background-color:#f9f9ff; padding:0.8rem; border-radius:10px; border:1px solid #e5e5e5; margin-bottom:12px;">
          <b style="color:#34495e;">Q{q_index + 1}.</b> {question_text}
            <span style="color:#7f8c8d;">({q.get('marks', 10)} marks)</span>
        </div>
    """, unsafe_allow_html=True)

    # === Answer field ===
    st.session_state.subj_answers[q_index] = st.text_area(
        "✏️ Your Answer:",
        value=st.session_state.subj_answers[q_index],
        height=120,
        key=f"subj_text_{q_index}"
    ).strip()

    # === Optional file upload ===
    st.session_state.subj_files[q_index] = st.file_uploader(
        "📎 Upload (optional)",
        type=["jpg", "jpeg", "png", "pdf", "docx"],
        key=f"subj_file_{q_index}"
    )

    # === Navigation buttons (compact centered layout) ===
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col1:
        if page > 1:
            if st.button("⬅ Prev", key=f"prev_{q_index}"):
                st.session_state.page -= 1
                st.rerun()

    with col2:
        st.markdown(
            f"<div style='text-align:center; color:#6c757d; font-size:0.85rem;'>Question {q_index + 1} of {total_questions}</div>",
            unsafe_allow_html=True
        )

    with col3:
        if page < total_questions:
            if st.button("Next ➡", key=f"next_{q_index}"):
                st.session_state.page += 1
                st.rerun()
        else:
            if st.button("🎯 Submit Test", key="submit_final"):
                handle_subjective_submission(questions, subject)

    # =========================================
    # Pagination Buttons (Centered + Slim)
    # =========================================
    # === Navigation Buttons ===
    col1, col2, col3 = st.columns([1, 1, 1])

    # PREV BUTTON
    with col1:
        if st.session_state.page > 0:
            st.button(
                "⬅ Prev",
                key=f"subj_prev_{page}",
                on_click=lambda: setattr(st.session_state, "page", st.session_state.page - 1)
            )

    # QUESTION COUNTER
    with col2:
        st.markdown(
            f"<div style='text-align:center;font-weight:600;'>Question {q_index + 1} of {total_questions}</div>",
            unsafe_allow_html=True
        )

    # NEXT / SUBMIT BUTTON
    with col3:
        if page < total_questions - 1:
            st.button(
                "Next ➡",
                key=f"subj_next_{page}",
                on_click=lambda: setattr(st.session_state, "page", st.session_state.page + 1)
            )
        else:
            st.markdown('<div class="submit-btn" style="text-align:center;">', unsafe_allow_html=True)
            st.button(
                "✅ Submit Test",
                key="subj_submit_final",
                on_click=lambda: handle_subjective_submission(questions, subject)
            )
            st.markdown('</div>', unsafe_allow_html=True)








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



from backend.models import StudentAnswer,Class
from datetime import datetime

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

