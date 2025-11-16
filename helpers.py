import streamlit as st
from database import get_session
import time
import json
# -----------------------------------------------------
# Add a new subjective question
# -----------------------------------------------------
from sqlalchemy import and_
from datetime import datetime
from sqlalchemy.orm import joinedload
from models import SubjectiveQuestion,Submission
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


def submit_subjective_answer(school_id, student_id, access_code, class_name, subject_id, question_id, answer_text):
    """Student submits an answer to a subjective question."""

    from models import SubjectiveAnswer

    db = get_session()
    try:
        new_answer = SubjectiveAnswer(
            school_id=school_id,
            student_id=student_id,
            access_code=access_code,
            class_name=class_name,
            subject_id=subject_id,
            question_id=question_id,
            answer_text=answer_text,
            submitted_on=datetime.utcnow(),
            status="Pending Review",
        )
        db.add(new_answer)
        db.commit()
        return True, "✅ Answer submitted successfully."
    except Exception as e:
        db.rollback()
        return False, f"❌ Submission failed: {e}"
    finally:
        db.close()


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


def get_student_subjective_results(student_id, school_id):
    """Fetch a student's graded subjective answers with questions."""
    from models import SubjectiveAnswer, SubjectiveQuestion, SubjectiveGrade

    db = get_session()
    try:
        results = (
            db.query(SubjectiveAnswer, SubjectiveQuestion, SubjectiveGrade)
            .join(SubjectiveQuestion, SubjectiveAnswer.question_id == SubjectiveQuestion.id)
            .outerjoin(SubjectiveGrade, SubjectiveGrade.answer_id == SubjectiveAnswer.id)
            .filter(
                and_(
                    SubjectiveAnswer.student_id == student_id,
                    SubjectiveAnswer.school_id == school_id,
                )
            )
            .options(joinedload(SubjectiveAnswer.question))
            .all()
        )
        return results
    finally:
        db.close()


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

    # === Question Box ===
    st.markdown(f"""
        <div style="background-color:#f9f9ff; padding:0.8rem; border-radius:10px; border:1px solid #e5e5e5; margin-bottom:12px;">
          <b style="color:#34495e;">Q{q_index + 1}.</b> {q.get('question', '')}
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
    # Sleek Fully-Rounded (Pill) Button Styling
    # =========================================

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


# =============================================
# SAVE: Objective Answers (DB Only)
# =============================================
def save_student_answers(access_code, subject, questions, answers):
    """
    Save student answers.
    - Objective → submissions table (one row per question)
    - Subjective → subjective_submissions table (one row for the whole test)
    """
    from models import Submission, SubjectiveSubmission, Student
    from sqlalchemy.orm import Session
    import json

    db = get_session()
    try:
        # ---------------------------------------------
        # 1. Get student by access code
        # ---------------------------------------------
        student = db.query(Student).filter(Student.access_code == access_code).first()
        if not student:
            print("❌ Student not found for access code:", access_code)
            return

        student_id = student.id
        school_id = student.school_id

        # ---------------------------------------------
        # 2. Separate objective vs subjective questions
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
        # ✅ OBJECTIVE: Save into submissions table
        # ---------------------------------------------
        for q, ans in objective_items:
            qid = q.get("id")
            correct_answer = q.get("correct_answer_text", "")

            db.add(
                Submission(
                    student_id=student_id,
                    question_id=qid,
                    selected_answer=ans,
                    correct=str(ans).strip().lower() == str(correct_answer).strip().lower(),
                    subject=subject,
                    school_id=school_id
                )
            )

        # ---------------------------------------------
        # ✅ SUBJECTIVE: Save into subjective_submissions table
        # ---------------------------------------------
        if subjective_items:
            sub_answers = {}

            for idx, (q, ans) in enumerate(subjective_items):
                sub_answers[q.get("id")] = ans

            db.add(
                SubjectiveSubmission(
                    student_id=student_id,
                    school_id=school_id,
                    subject=subject,
                    answers=sub_answers,
                )
            )

        db.commit()
        print("✅ Saved all answers successfully")

    except Exception as e:
        db.rollback()
        print("❌ Error saving answers:", e)

    finally:
        db.close()


# =============================================
# SAVE: Objective Answers (DB Only)
# =============================================
def save_subjective_submission(
    student_id: int,
    school_id: int,
    subject: str,
    answers: dict,
    attachments: list | None = None
):
    """
    Save or update a subjective submission.
    - answers: dict {question_index: answer_text}
    - attachments: list of file paths
    Stored as plain text in DB.
    """
    db = get_session()
    try:
        from models import SubjectiveSubmission

        # Convert dict / list to plain text
        answers_text = "\n".join([f"Q{k}: {v}" for k, v in answers.items()])
        attachments_text = ",".join(attachments) if attachments else ""

        # Check for existing submission
        existing = (
            db.query(SubjectiveSubmission)
            .filter_by(student_id=student_id, school_id=school_id, subject=subject)
            .first()
        )

        if existing:
            existing.answers = answers_text
            existing.attachments = attachments_text
            existing.status = "Pending Review"
            db.commit()
            db.refresh(existing)
            return existing.id

        # New submission
        new_sub = SubjectiveSubmission(
            student_id=student_id,
            school_id=school_id,
            subject=subject,
            answers=answers_text,
            attachments=attachments_text,
            status="Pending Review"
        )

        db.add(new_sub)
        db.commit()
        db.refresh(new_sub)
        return new_sub.id

    except Exception as e:
        db.rollback()
        print(f"❌ Failed to save subjective submission: {e}")
        return None
    finally:
        db.close()

# =============================================
# SAVE: Subjective Answers (DB Only)
# =============================================
def handle_subjective_submission(questions, subject):
    """Handle saving and finalizing subjective test responses."""
    student = st.session_state.get("student", {})
    if not student:
        st.error("❌ Student information missing!")
        return

    student_id = student.get("id")
    school_id = student.get("school_id")
    if not student_id or not school_id:
        st.error("❌ Student ID or school ID missing!")
        return

    # Convert list of answers to dict {Q_index: answer_text}
    answers_list = st.session_state.get("subj_answers", [])
    answers_dict = {i + 1: ans for i, ans in enumerate(answers_list)}

    # Files list
    files_list = st.session_state.get("subj_files", [])

    # Save to DB
    submission_id = save_subjective_submission(
        student_id=student_id,
        school_id=school_id,
        subject=subject,
        answers=answers_dict,
        attachments=files_list
    )

    if submission_id:
        st.session_state.submitted = True
        st.success("✅ Subjective test submitted successfully! Await teacher review.")
        st.balloons()
        st.stop()
    else:
        st.error("❌ Failed to submit subjective test.")



# ====================================================
# 🎯 Load Objective Questions
# ====================================================
def get_objective_questions(class_name: str, subject: str, school_id=None):
    from models import ObjectiveQuestion
    db = get_session()
    try:
        normalized_class = class_name.strip().lower().replace(" ", "")
        normalized_subject = subject.strip().lower().replace(" ", "")

        print(f"\n🔍 OBJECTIVE DEBUG:")
        print(f"Class: {class_name} | Subject: {subject} | School ID: {school_id}")

        query = db.query(ObjectiveQuestion)
        total = query.count()
        print(f"Total in table: {total}")

        # School filter
        if school_id and str(school_id).isdigit():
            query = query.filter(ObjectiveQuestion.school_id == int(school_id))
        elif school_id:
            query = query.filter(ObjectiveQuestion.school_id == school_id)

        rows = query.all()
        print(f"📊 After school filter: {len(rows)} found")

        result_rows = []
        for q in rows:
            db_class = (q.class_name or "").strip().lower().replace(" ", "")
            db_subj = (q.subject or "").strip().lower().replace(" ", "")
            if db_class == normalized_class and db_subj == normalized_subject:
                result_rows.append(q)

        print(f"✅ Matches after filter: {len(result_rows)}")

        result = []
        for q in result_rows:
            options = q.options
            if isinstance(options, str):
                try:
                    options = json.loads(options)
                except:
                    options = [options]

            result.append({
                "id": q.id,
                "question": q.question_text,
                "options": options,
                "answer": q.correct_answer,
                "type": "objective"
            })
        return result

    except Exception as e:
        print("❌ Error loading objective questions:", e)
        return []
    finally:
        db.close()


# ====================================================
# ✍️ Load Subjective Questions
# ====================================================
def get_subjective_questions(class_name: str, subject: str, school_id=None):
    from models import SubjectiveQuestion
    db = get_session()
    try:
        normalized_class = class_name.strip().lower().replace(" ", "")
        normalized_subject = subject.strip().lower().replace(" ", "")

        print(f"\n🔍 SUBJECTIVE DEBUG:")
        print(f"Class: {class_name} | Subject: {subject} | School ID: {school_id}")

        query = db.query(SubjectiveQuestion)
        total = query.count()
        print(f"Total in table: {total}")

        # Normalize school_id to int if possible
        if school_id and str(school_id).isdigit():
            query = query.filter(SubjectiveQuestion.school_id == int(school_id))
        elif school_id:
            query = query.filter(SubjectiveQuestion.school_id == school_id)

        # Fetch all to debug
        rows = query.all()
        print(f"📊 After school filter: {len(rows)} found")

        # Apply class and subject filters manually
        result_rows = []
        for q in rows:
            db_class = (q.class_name or "").strip().lower().replace(" ", "")
            db_subj = (q.subject or "").strip().lower().replace(" ", "")
            if db_class == normalized_class and db_subj == normalized_subject:
                result_rows.append(q)

        print(f"✅ Matches after filter: {len(result_rows)}")

        return [{
            "id": q.id,
            "question": q.question_text,
            "options": [],
            "answer": "",
            "marks": q.marks,
            "type": "subjective"
        } for q in result_rows]

    except Exception as e:
        print("❌ Error loading subjective questions:", e)
        return []
    finally:
        db.close()

# -------------------------------
# Load All Questions for a Test
# -------------------------------
def load_test_questions(class_name: str, subject: str, school_id: int | None = None):
    """Combine objective and subjective questions into a single shuffled list."""
    objective_qs = get_objective_questions(class_name, subject, school_id)
    subjective_qs = get_subjective_questions(class_name, subject, school_id)

    all_questions = objective_qs + subjective_qs
    if not all_questions:
        return []

    import random
    random.shuffle(all_questions)

    # Prepare each question for session
    for q in all_questions:
        if q["type"] == "objective":
            opts = q.get("options", [])
            correct_text = q.get("answer", "").strip()
            random.shuffle(opts)
            q["options"] = opts
            q["correct_answer_text"] = correct_text
            q["answer_index"] = opts.index(correct_text) if correct_text in opts else -1
            q.pop("answer", None)
        else:
            q["options"] = []

    return all_questions



def highlight_score(val):
    """
    Apply background color based on score percentage string.
    Example: "85%" -> green, "60%" -> yellow, "45%" -> red.
    """
    if not isinstance(val, str):
        return ''  # Only process strings

    try:
        num = float(val.strip().rstrip('%'))
    except (ValueError, TypeError):
        return ''  # Invalid or non-numeric input safely ignored

    if num >= 70:
        color = '#a6f1a6'  # Green for good
    elif num >= 50:
        color = '#fff6a6'  # Yellow for average
    else:
        color = '#f7a6a6'  # Red for poor

    return f'background-color: {color}'
