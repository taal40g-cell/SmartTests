# ==============================
# Third-Party Imports
# ==============================
import streamlit as st
from passlib.context import CryptContext
from passlib.exc import UnknownHashError
from sqlalchemy.orm import Session
import json
from typing import List, Dict, Any


from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, func


# ==============================
# Local Imports
# ==============================
from database import get_session, test_db_connection
from models import (
    Admin,
    User,
    Student,
    Question,
    Submission,
    Retake,
    TestResult,
    Config,
)

# ==============================
# Password Hashing Context
# ==============================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ==============================
# Password Helpers
# ==============================
def hash_password(password: str) -> str:
    """Hash a plain password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against its hashed value.
    Supports multiple hash formats (via passlib).
    """
    try:
        return pwd_context.verify(password, hashed_password)
    except UnknownHashError:
        return False


# ==============================
# Admin CRUD
# ==============================
def set_admin(username: str, password: str, role: str = "admin") -> bool:
    """
    Create or update an admin.
    Always stores the password as a bcrypt hash.
    """
    db = get_session()
    try:
        username = username.strip()
        hashed_pw = hash_password(password)

        admin = db.query(Admin).filter(Admin.username.ilike(username)).first()
        if admin:
            admin.password_hash = hashed_pw
            admin.role = role
        else:
            admin = Admin(
                username=username,
                password_hash=hashed_pw,
                role=role
            )
            db.add(admin)

        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Error creating/updating admin: {e}")
        return False
    finally:
        db.close()


def add_admin(username: str, password: str, role: str = "admin") -> bool:
    """
    Add a new admin (bcrypt).
    Returns False if the username already exists.
    """
    db = get_session()
    try:
        if db.query(Admin).filter(Admin.username.ilike(username.strip())).first():
            return False

        hashed_pw = hash_password(password)
        db.add(Admin(username=username.strip(), password_hash=hashed_pw, role=role))
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Error adding admin: {e}")
        return False
    finally:
        db.close()


def get_admin(username: str) -> Admin | None:
    """Retrieve an admin by username (case-insensitive)."""
    db = get_session()
    try:
        return db.query(Admin).filter(Admin.username.ilike(username.strip())).first()
    finally:
        db.close()


def get_admins(as_dict: bool = False):
    """
    Get all admins.
    If as_dict=True, returns {username: role}.
    """
    db = get_session()
    try:
        result = db.query(Admin).all()
        if as_dict:
            return {a.username: a.role for a in result}
        return result
    finally:
        db.close()


def verify_admin(username: str, password: str) -> Admin | None:
    """
    Verify admin credentials.
    Returns the Admin object on success, None on failure.
    """
    admin = get_admin(username)
    if admin and verify_password(password, admin.password_hash):
        return admin
    return None


def update_admin_password(username: str, new_password: str) -> bool:
    """
    Update an admin's password.
    Caller must pass a plain password; it will be hashed before saving.
    """
    db = get_session()
    try:
        admin = db.query(Admin).filter(Admin.username.ilike(username.strip())).first()
        if not admin:
            return False
        admin.password_hash = hash_password(new_password)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Error updating admin password: {e}")
        return False
    finally:
        db.close()


# ==============================
# Ensure Super Admin Exists
# ==============================
def ensure_super_admin_exists():
    """
    Ensure a default super_admin exists.
    If missing, creates super_admin with password "1234".
    If present, ensures role is correct and password is valid.
    """
    db = get_session()
    try:
        admin = db.query(Admin).filter_by(username="super_admin").first()
        default_pass = hash_password("1234")

        if not admin:
            db.add(
                Admin(
                    username="super_admin",
                    password_hash=default_pass,
                    role="super_admin"
                )
            )
            db.commit()
            print("✅ Created default super_admin (username=super_admin, password=1234)")
        else:
            updated = False
            # Ensure correct role
            if admin.role != "super_admin":
                admin.role = "super_admin"
                updated = True
            # Ensure default password works
            if not verify_password("1234", admin.password_hash):
                admin.password_hash = default_pass
                updated = True
            if updated:
                db.commit()
                print("🔄 Updated super_admin role or password as needed")
    finally:
        db.close()


# Run on module load
ensure_super_admin_exists()


# ==============================
# Admin Login UI (Streamlit)
# ==============================
def require_admin_login():
    """
    Streamlit login flow for admins.
    - Checks session state for existing login.
    - Validates username/password.
    - Allows super_admin to reset any password.
    """
    # ✅ Already logged in
    if st.session_state.get("admin_logged_in", False):
        return True

    st.subheader("🔑 Admin Login")

    username = st.text_input("Username", key="admin_username_input")
    password = st.text_input("Password", type="password", key="admin_password_input")

    col1, col2 = st.columns([3, 1])

    # --------------------------
    # Standard Login
    # --------------------------
    with col1:
        if st.button("Login"):
            admin = get_admin(username.strip())
            if admin and verify_password(password, admin.password_hash):
                # Save session state
                st.session_state.admin_username = admin.username
                st.session_state.admin_logged_in = True
                st.session_state.admin_role = admin.role
                st.success(f"✅ Logged in as {admin.username} ({admin.role})")
                st.rerun()
            else:
                st.error("❌ Invalid username or password")

    # --------------------------
    # Super Admin Reset Option
    # --------------------------
    with col2:
        if st.button("Reset Password (Super Admin Only)"):
            st.session_state.show_reset_pw = True

    if st.session_state.get("show_reset_pw", False):
        st.info("🔐 Super Admin Password Reset")

        super_admin = st.text_input("Super Admin Username", key="super_admin_user")
        super_pass = st.text_input("Super Admin Password", type="password", key="super_admin_pass")

        if st.button("Authenticate Super Admin"):
            sa = get_admin(super_admin.strip())
            if sa and sa.role == "super_admin" and verify_password(super_pass, sa.password_hash):
                st.session_state.super_admin_authenticated = True
                st.success("✅ Super Admin authenticated! You can now reset any admin password.")
            else:
                st.error("❌ Invalid super admin credentials")

        # --------------------------
        # Password Reset Flow
        # --------------------------
        if st.session_state.get("super_admin_authenticated", False):
            reset_user = st.text_input("Username to Reset", key="reset_target_user")
            new_password = st.text_input("New Password", type="password", key="reset_new_pw")

            if st.button("Confirm Reset"):
                target = get_admin(reset_user.strip())
                if target:
                    update_admin_password(reset_user.strip(), new_password)
                    st.success(f"✅ Password for {reset_user} reset successfully!")
                    # Reset state
                    st.session_state.show_reset_pw = False
                    st.session_state.super_admin_authenticated = False
                else:
                    st.error("❌ User not found")

    return False

# -----------------------------
# Student Management
# -----------------------------
import random, string, uuid


def generate_access_code(length=6, db=None):
    """Generate a unique access code for students (short and user-friendly)."""
    close_db = False
    if db is None:
        db = get_session()
        close_db = True
    try:
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
            if not db.query(Student).filter_by(access_code=code).first():
                return code
    finally:
        if close_db:
            db.close()

# db_helpers.py
from database import get_session
from contextlib import contextmanager

@contextmanager
def db_session():
    """Context manager for safely using database sessions."""
    db = get_session()
    try:
        yield db
    finally:
        db.close()



def generate_unique_id(db=None):
    """Generate a unique internal ID for tracking students (UUID shortened)."""
    close_db = False
    if db is None:
        db = get_session()
        close_db = True
    try:
        while True:
            unique_id = str(uuid.uuid4())[:8]
            if not db.query(Student).filter_by(unique_id=unique_id).first():
                return unique_id
    finally:
        if close_db:
            db.close()



def add_student_db(name, class_name, db=None):
    """
    Adds a single student. If a db session is provided, it reuses it.
    Otherwise, it opens and closes its own session.

    Returns:
        {
            "id": int,
            "unique_id": str,
            "name": str,
            "class_name": str,
            "access_code": str,
            "status": "new" | "reused"
        }
    """
    own_session = False
    if db is None:
        db = get_session()
        own_session = True

    try:
        # Strip to avoid whitespace mismatches
        name = name.strip()
        class_name = class_name.strip()

        # Check if student already exists (same name and class)
        existing = db.query(Student).filter_by(name=name, class_name=class_name).first()
        if existing:
            return {
                "id": existing.id,
                "unique_id": existing.unique_id,
                "name": existing.name,
                "class_name": existing.class_name,
                "access_code": existing.access_code,
                "status": "reused",
            }

        # Generate new access code and unique_id
        access_code = generate_access_code()
        unique_id = uuid.uuid4().hex[:8]  # 8-char lowercase unique id (e.g., 'f2a1d9b3')

        # Create and save new student
        new_student = Student(
            unique_id=unique_id,
            name=name,
            class_name=class_name,
            access_code=access_code,
            can_retake=True,
            submitted=False,
        )
        db.add(new_student)
        db.commit()
        db.refresh(new_student)

        return {
            "id": new_student.id,
            "unique_id": new_student.unique_id,
            "name": new_student.name,
            "class_name": new_student.class_name,
            "access_code": new_student.access_code,
            "status": "new",
        }

    except Exception as e:
        db.rollback()
        raise e
    finally:
        if own_session:
            db.close()


def bulk_add_students_db(student_list):
    """
    Adds multiple students in bulk.
    Skips and reuses if student already exists.
    student_list: list of tuples [(name, class_name), ...]

    Returns:
        {
            "students": [...],
            "summary": {"new": count_new, "reused": count_reused}
        }
    """
    results = []
    count_new, count_reused = 0, 0

    db = get_session()
    try:
        for name, class_name in student_list:
            student_data = add_student_db(name, class_name, db=db)
            results.append(student_data)

            if student_data["status"] == "new":
                count_new += 1
            else:
                count_reused += 1

        return {
            "students": results,
            "summary": {"new": count_new, "reused": count_reused},
        }

    finally:
        db.close()


def get_student_by_access_code_db(access_code):
    """Fetch student ORM object by access code (case-insensitive)."""
    clean_code = access_code.strip().upper()
    db = get_session()
    try:
        student = (
            db.query(Student)
            .filter(func.upper(Student.access_code) == clean_code)
            .first()
        )
        return student
    finally:
        db.close()

    # =====================================
    # Student Helpers
    # =====================================



def get_student_by_code(db: Session, access_code: str):
    """
    Fetch a student record by their unique access code.
    Returns None if not found.
    """
    try:
        return db.query(Student).filter_by(access_code=access_code).first()
    except Exception as e:
        print(f"❌ Error fetching student by code: {e}")
        return None


def update_student_submission_db(access_code):
    """Mark student as submitted = True."""
    db = get_session()
    try:
        code = normalize_code(access_code)
        student = db.query(Student).filter(Student.access_code == code).first()
        if student:
            student.submitted = True
            db.commit()
    finally:
        db.close()


def reset_student_retake_db(access_code):
    """Reset student so they can retake (submitted = False)."""
    db = get_session()
    try:
        code = normalize_code(access_code)
        student = db.query(Student).filter(Student.access_code == code).first()
        if student:
            student.submitted = False
            db.commit()
    finally:
        db.close()


def get_users():
    """Return all students as dict keyed by access code."""
    db = get_session()
    try:
        students = db.query(Student).all()
        return {
            s.access_code.strip().upper(): {
                "id": s.id,
                "name": s.name,
                "class_name": s.class_name,
                "unique_id": s.unique_id,
                "access_code": s.access_code.strip().upper(),
                "submitted": bool(s.submitted)
            }
            for s in students
        }
    finally:
        db.close()

# -----------------------------
# Question Management
# -----------------------------

def add_question_db(class_name: str, subject: str, text: str, options: List[str], correct: str):
    """Add a single question to the DB."""
    db = get_session()
    try:
        db.add(Question(
            class_name=class_name.strip().upper(),
            subject=subject.strip().capitalize(),
            question_text=text.strip(),
            options=json.dumps([opt.strip() for opt in options]),
            answer=correct.strip()
        ))
        db.commit()
    finally:
        db.close()


def get_questions_db(class_name: str, subject: str = None) -> List[Dict[str, Any]]:
    """Fetch questions for a class (optionally filtered by subject)."""
    db = get_session()
    try:
        query = db.query(Question).filter(Question.class_name.ilike(class_name.strip()))
        if subject:
            query = query.filter(Question.subject.ilike(subject.strip()))
        rows = query.all()

        result = []
        for q in rows:
            try:
                opts = json.loads(q.options) if isinstance(q.options, str) else q.options
            except:
                opts = [q.options] if isinstance(q.options, str) else []
            result.append({
                "id": q.id,
                "class_name": q.class_name,
                "subject": q.subject,
                "question": q.question_text,
                "options": opts,
                "answer": q.answer,
                "archived": q.archived  # <-- Add this!
            })
        return result
    finally:
        db.close()


def validate_question(q: Dict[str, Any]) -> bool:
    """Validate a single question dict structure."""
    if not isinstance(q, dict):
        return False
    if not all(k in q for k in ("question", "options", "answer")):
        return False
    if not isinstance(q["options"], list) or len(q["options"]) < 2:
        return False
    if not isinstance(q["answer"], str):
        return False
    if q["answer"].strip() not in [opt.strip() for opt in q["options"]]:
        return False
    return True


def handle_uploaded_questions(class_name, subject, valid_questions):
    db = get_session()
    try:
        class_name_lower = class_name.strip().lower()
        subject_lower = subject.strip().lower()

        deleted_count = (
            db.query(Question)
            .filter(
                Question.class_name == class_name_lower,
                Question.subject == subject_lower
            )
            .delete(synchronize_session=False)
        )

        new_records = [
            Question(
                class_name=class_name_lower,
                subject=subject_lower,
                question_text=q["question"].strip(),
                options=json.dumps([opt.strip() for opt in q["options"]]),
                answer=q["answer"].strip(),
            )
            for q in valid_questions
        ]

        db.add_all(new_records)
        db.commit()

        return {"success": True, "inserted": len(new_records), "deleted": deleted_count}

    except Exception as e:
        print("Upload error:", e)
        db.rollback()
        return {"success": False, "error": str(e)}

    finally:
        db.close()




@st.cache_data(ttl=60)
def load_questions_db(class_name: str, subject: str, limit: int = 30) -> List[Dict[str, Any]]:
    """Fetch randomized questions from DB (default max 30)."""
    db = get_session()
    try:
        questions = (
            db.query(Question)
            .filter(
                func.lower(Question.class_name) == class_name.strip().lower(),
                func.lower(Question.subject) == subject.strip().lower()
            )
            .order_by(func.random())
            .limit(limit)
            .all()
        )
        ...
        result = []
        for q in questions:
            try:
                opts = json.loads(q.options) if isinstance(q.options, str) else q.options
            except:
                opts = [q.options] if isinstance(q.options, str) else []
            result.append({
                "id": q.id,
                "question": q.question_text,
                "options": opts,
                "answer": q.answer
            })

        return result
    finally:
        db.close()


# db_helpers.py
def delete_student_db(student_identifier):
    """
    Delete a student record using either integer ID or access_code.
    """
    db = get_session()
    try:
        # Determine if the input looks like an integer ID or string access code
        if isinstance(student_identifier, int) or str(student_identifier).isdigit():
            student = db.query(Student).filter_by(id=int(student_identifier)).first()
        else:
            student = db.query(Student).filter_by(access_code=str(student_identifier).strip()).first()

        if not student:
            print(f"⚠️ No student found for identifier: {student_identifier}")
            return False

        db.delete(student)
        db.commit()
        print(f"✅ Deleted student: {student.name} ({student.access_code})")
        return True

    except Exception as e:
        db.rollback()
        print("❌ Error deleting student:", e)
        return False
    finally:
        db.close()

# -----------------------------
# Submissions & Results
# -----------------------------
def normalize_text(text: str) -> str:
    """Normalize text for consistent comparison."""
    if not text:
        return ""
    return (
        str(text).strip().lower()
        .replace("₂", "2")
        .replace("₃", "3")
        .replace("₄", "4")
        .replace("’", "'")
    )


def save_student_answers(access_code: str, subject: str, questions: list, answers: list):
    """
    Save student answers to the database.
    Converts indexed answers into option text, calculates score,
    and calls add_submission_db() to persist results.
    """
    student = get_student_by_access_code_db(access_code)
    if not student:
        raise ValueError("Invalid student access code")

    submissions, correct = [], 0
    total = len(questions)

    for i, q in enumerate(questions):
        # Ensure options is a list
        opts = q.get("options", [])
        if isinstance(opts, str):
            try:
                opts = json.loads(opts)
            except Exception:
                opts = [o.strip() for o in opts.split(",") if o.strip()]

        idx = answers[i] if i < len(answers) else -1
        selected = opts[idx] if 0 <= idx < len(opts) else None

        if selected:
            sel_norm = normalize_text(selected)
            correct_ans = normalize_text(q.get("correct_answer_text", ""))
            is_correct = sel_norm == correct_ans
            if is_correct:
                correct += 1

            submissions.append({
                "question_id": q["id"],
                "selected": sel_norm,
                "is_correct": is_correct
            })

    score = correct
    percentage = (score / total) * 100 if total else 0

    print("📝 Debug save_student_answers()")
    print(f"Student: {student.name} | Subject: {subject}")
    print(f"✅ Final Score: {score}/{total} ({percentage:.1f}%)")

    # Save results to DB
    add_submission_db(student.id, subject, submissions, score, total, percentage)


def add_submission_db(student_id: int, subject: str, submissions: list, score: int, total: int, percentage: float):
    """
    Save per-question submissions and a TestResult summary.
    """
    db = get_session()
    try:
        student = db.query(Student).filter_by(id=student_id).first()
        if not student:
            raise ValueError("Invalid student ID")

        # Save each per-question submission
        for sub in submissions:
            db.add(Submission(
                student_id=student.id,
                question_id=sub["question_id"],
                selected_answer=sub["selected"],
                correct=sub["is_correct"],
                subject=subject
            ))

        # Save test result summary
        db.add(TestResult(
            student_id=student.id,
            subject=subject,
            score=score,
            total=total,
            percentage=percentage
        ))

        db.commit()
        print(f"✅ Saved {len(submissions)}/{total} answers for {student.name} ({score} correct)")

    except Exception as e:
        db.rollback()
        print(f"❌ Failed to save submissions: {e}")
        raise
    finally:
        db.close()


# -----------------------------
# Submissions
# -----------------------------
def set_submission_db(access_code, subject, questions, answers):
    """
    Save student submissions (answers = indices).
    Converts index → option text to compare with correct_answer.
    """
    student = get_student_by_access_code_db(access_code)
    if not student:
        raise ValueError("Invalid student access code")

    db = get_session()
    try:
        for i, q in enumerate(questions):
            opts = q.get("options", [])
            if isinstance(opts, str):
                try:
                    opts = json.loads(opts)
                except Exception:
                    opts = [o.strip() for o in opts.split(",") if o.strip()]

            idx = answers[i] if i < len(answers) else -1
            selected = opts[idx] if 0 <= idx < len(opts) else "No Answer"

            correct = str(selected).strip().lower() == str(q.get("answer", "")).strip().lower()

            db.add(Submission(
                student_id=student.id,
                question_id=q.get("id"),
                selected_answer=selected,
                correct=correct,
                subject=subject
            ))

        db.commit()
        print(f"✅ Saved submissions for {student.name} ({access_code})")

    finally:
        db.close()


def get_all_submissions_db():
    """Return all submissions in the database."""
    db = get_session()
    try:
        return db.query(Submission).all()
    except Exception as e:
        print(f"[DB ERROR] Failed to fetch submissions: {e}")
        return []
    finally:
        db.close()


# -----------------------------
# Retakes
# -----------------------------
def get_retake_db(access_code: str, subject: str) -> bool:
    """Check if a student has retake permission for a subject."""
    db = get_session()
    try:
        student = db.query(Student).filter_by(access_code=access_code).first()
        if not student:
            return False
        retake = db.query(Retake).filter_by(student_id=student.id, subject=subject).first()
        return bool(retake and retake.can_retake)
    finally:
        db.close()


def decrement_retake(access_code: str, subject: str) -> None:
    """Reduce the remaining retake count for a student by 1."""
    db = get_session()
    try:
        student = db.query(Student).filter_by(access_code=access_code).first()
        if not student:
            raise ValueError("Invalid student access code")

        retake = db.query(Retake).filter_by(student_id=student.id, subject=subject).first()
        if retake and retake.can_retake > 0:
            retake.can_retake -= 1
            db.commit()
    finally:
        db.close()


def set_retake_db(access_code: str, subject: str, can_retake: bool = True):
    """Create or update a student's retake permission for a subject."""
    db = get_session()
    try:
        student = db.query(Student).filter_by(access_code=access_code).first()
        if not student:
            raise ValueError("Invalid student access code")

        retake = db.query(Retake).filter_by(student_id=student.id, subject=subject).first()
        if retake:
            retake.can_retake = can_retake
        else:
            db.add(Retake(student_id=student.id, subject=subject, can_retake=can_retake))
        db.commit()
    finally:
        db.close()


# -----------------------------
# Score Calculation
# -----------------------------
def calculate_score_db(student_name, subject, questions, answers_dict):
    """Compare answers_dict against correct answers and return score details."""
    correct, wrong, details = 0, 0, []

    for q in questions:
        qid = q["id"]
        correct_answer = str(q.get("answer", "")).strip().lower()
        user_answer = str(answers_dict.get(qid, "")).strip().lower()

        if user_answer == correct_answer:
            correct += 1
            result = "correct"
        else:
            wrong += 1
            result = "wrong"

        details.append({
            "student_name": student_name,
            "subject": subject,
            "question_id": qid,
            "question": q.get("question_text", ""),
            "user_answer": user_answer,
            "correct_answer": correct_answer,
            "result": result
        })

    return correct, wrong, details


# -----------------------------
# Submission Helpers
# -----------------------------
def get_submission_db(student_id, subject=None):
    """Fetch submissions for a student (optionally filtered by subject)."""
    db = get_session()
    try:
        query = db.query(Submission).filter_by(student_id=student_id)
        if subject:
            query = query.filter_by(subject=subject)
        return query.all()
    finally:
        db.close()


def can_take_test(access_code: str, subject: str) -> tuple[bool, str]:
    """Check if a student is allowed to take a test."""
    student = get_student_by_access_code_db(access_code)
    if not student:
        return False, "🛑 Invalid student access code."

    submissions = get_submission_db(student.id, subject)
    can_retake = get_retake_db(access_code, subject)

    if submissions and not can_retake:
        return False, "🛑 You have already submitted this test."

    return True, ""


# -----------------------------
# Question Tracker (UI only)
# -----------------------------
def show_question_tracker(questions, answers):
    """Streamlit UI tracker: progress + grid navigator."""
    import uuid

    total = len(questions)
    marked = set(st.session_state.get("marked_for_review", []))

    # Stable unique test ID
    if "test_id" not in st.session_state:
        st.session_state.test_id = str(uuid.uuid4())
    test_id = st.session_state.test_id

    student_id = st.session_state.get("student", {}).get("id", "anon")
    subject = st.session_state.get("subject", "global")

    # Progress summary
    answered = sum(1 for ans in answers if ans not in [-1, None])
    percent = int((answered / total) * 100) if total else 0
    st.markdown(
        f"<div style='background:#f9f9f9; padding:8px; border-radius:6px; "
        f"border:1px solid #ddd; margin-bottom:6px;'>"
        f"<b>📊 Progress:</b> {answered}/{total} answered — <b>{percent}%</b></div>",
        unsafe_allow_html=True
    )
    st.progress(answered / total if total else 0)

    # Question navigator
    def get_color(idx):
        if idx in marked:
            return "#FFA500"  # marked
        elif idx < len(answers) and answers[idx] not in [-1, None]:
            return "#2ECC71"  # answered
        return "#E74C3C"  # unanswered

    with st.expander("🔽 Question Navigator"):
        for row_start in range(0, total, 10):
            cols = st.columns(10)
            for i in range(row_start, min(row_start + 10, total)):
                color = get_color(i)
                btn_key = f"jump_{subject}_{student_id}_{test_id}_{i}"

                if cols[i % 10].button("", key=btn_key, help=f"Go to Q{i+1}"):
                    st.session_state.page = i + 1
                    st.rerun()

                cols[i % 10].markdown(
                    f"""
                    <div style="
                        background:{color};
                        color:white;
                        font-weight:bold;
                        text-align:center;
                        border-radius:50%;
                        width:30px;
                        height:30px;
                        line-height:30px;
                        margin:auto;
                        font-size:12px;
                    ">{i+1}</div>
                    """,
                    unsafe_allow_html=True
                )
# ==============================
# 🕒 Test Duration Helpers
# ==============================

def get_test_duration(default=30):
    """
    Fetch test duration (in minutes) from DB and return it in SECONDS.
    Falls back to default minutes if not set.
    """
    db = get_session()
    try:
        config = db.query(Config).filter_by(key="test_duration").first()
        if config:
            return int(config.value) * 60
        return default * 60
    finally:
        db.close()


def set_test_duration(duration):
    """
    Save or update test duration in DB (stored as MINUTES).
    """
    db = get_session()
    try:
        config = db.query(Config).filter_by(key="test_duration").first()
        if config:
            config.value = str(duration)
        else:
            db.add(Config(key="test_duration", value=str(duration)))
        db.commit()
    finally:
        db.close()


# ==============================
# 📋 Question Helpers
# ==============================
def preview_questions_db(class_name=None, subject=None, limit=5):
    """
    Preview a limited number of questions for a given class & subject.
    Returns list of dicts.
    """
    db = get_session()
    try:
        query = db.query(Question)

        if class_name:
            query = query.filter(Question.class_name == class_name.strip().lower())
        if subject:
            query = query.filter(Question.subject == subject.strip().lower())

        results = query.limit(limit).all()

        return [
            {
                "id": q.id,
                "class": q.class_name,
                "subject": q.subject,
                "question": q.question_text
            }
            for q in results
        ]
    finally:
        db.close()


def count_questions_db(class_name=None, subject=None):
    """
    Count total questions in DB for given class and subject.
    """
    db = get_session()
    try:
        query = db.query(Question)
        if class_name:
            query = query.filter(Question.class_name == class_name.strip().lower())
        if subject:
            query = query.filter(Question.subject == subject.strip().lower())

        return query.count()
    finally:
        db.close()


def clear_questions_db():
    """Delete all questions."""
    db = get_session()
    try:
        db.query(Question).delete()
        db.commit()
    finally:
        db.close()


def save_questions_db(questions):
    """
    Save one or multiple Question objects to the database.
    Returns number of inserted rows.
    """
    db = get_session()
    inserted = 0
    try:
        if not questions:
            return 0
        if not isinstance(questions, (list, tuple)):
            questions = [questions]
        for q in questions:
            db.add(q)
            inserted += 1
        db.commit()
        return inserted
    finally:
        db.close()


# ==============================
# 👨‍🎓 Student Helpers
# ==============================

def clear_students_db():
    """Delete all students."""
    db = get_session()
    try:
        db.query(User).delete()
        db.commit()
    finally:
        db.close()


def update_student_db(student_id, new_name, new_class):
    db = get_session()
    try:
        # ✅ Query by primary key (integer)
        student = db.query(Student).filter_by(id=student_id).first()

        if not student:
            st.error("Student not found.")
            return

        student.name = new_name
        student.class_name = new_class
        db.commit()
        st.success("Student record updated successfully.")
    except Exception as e:
        db.rollback()
        st.error(f"Error updating student: {e}")
    finally:
        db.close()


# ==============================
# 📝 Submission Helpers
# ==============================

def clear_submissions_db():
    """Delete all submissions."""
    db = get_session()
    try:
        db.query(Submission).delete()
        db.commit()
    finally:
        db.close()


# ==============================
# 🔑 Utility
# ==============================

def normalize_code(code: str) -> str:
    """Normalize access code: remove spaces and uppercase."""
    if not code:
        return ""
    return code.strip().upper()



from datetime import datetime

def archive_question(session: Session, question_id: int) -> bool:
    """Mark a question as archived."""
    q = session.query(Question).get(question_id)
    if not q:
        return False
    q.archived = True
    q.archived_at = datetime.utcnow()
    session.commit()
    return True


def restore_question(session: Session, question_id: int) -> bool:
    """Restore an archived question back to active."""
    q = session.query(Question).get(question_id)
    if not q:
        return False
    q.archived = False
    q.archived_at = None
    session.commit()
    return True

def get_archived_questions(session: Session, class_name=None, subject=None):
    """Return all archived questions (optionally filtered)."""
    query = session.query(Question).filter(Question.archived.is_(True))

    if class_name:
        query = query.filter(Question.class_name == class_name)
    if subject:
        query = query.filter(Question.subject == subject)

    return query.order_by(Question.archived_at.desc()).all()


def reset_test(student_id: int):
    """
    Reset a student's test submission and retake status.
    """
    db = get_session()
    try:
        student = db.query(Student).filter_by(id=student_id).first()
        if not student:
            return False

        student.submitted = False
        student.can_retake = True
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Error resetting test: {e}")
        return False
    finally:
        db.close()



def has_submitted_test(access_code: str, subject: str) -> bool:
    db = get_session()
    try:
        exists = (
            db.query(TestResult)
            .filter_by(access_code=access_code, subject=subject)
            .first()
        )
        return exists is not None
    finally:
        db.close()



# db_helpers.py
from database import get_session
from models import StudentProgress
from sqlalchemy.exc import SQLAlchemyError

# ==============================
# 🧠 Save Ongoing Test Progress
# ==============================
def save_progress(access_code: str, subject: str, answers: list, current_q: int, start_time: float, duration: int, questions: list):
    """Insert or update ongoing test progress."""
    db = get_session()
    try:
        record = db.query(StudentProgress).filter_by(access_code=access_code, subject=subject).first()

        if record:
            record.answers = answers
            record.current_q = current_q
            record.start_time = start_time
            record.duration = duration
            record.questions = questions
        else:
            record = StudentProgress(
                access_code=access_code,
                subject=subject,
                answers=answers,
                current_q=current_q,
                start_time=start_time,
                duration=duration,
                questions=questions
            )
            db.add(record)

        db.commit()
    except SQLAlchemyError as e:
        print("❌ Save progress error:", e)
        db.rollback()
    finally:
        db.close()

# ==============================
# 📥 Load Saved Progress
# ==============================

from typing import Optional, Dict, List
@st.cache_data(ttl=300)  # cache for 5 minutes
def load_progress(access_code: str, subject: str) -> Optional[Dict]:
    """Return saved progress for a student and subject."""
    db = get_session()
    try:
        record = db.query(StudentProgress).filter_by(access_code=access_code, subject=subject).first()
        if record:
            return {
                "answers": record.answers,
                "current_q": record.current_q,
                "start_time": record.start_time,
                "duration": record.duration,
                "questions": record.questions,
            }
        return None
    except SQLAlchemyError as e:
        print("❌ Load progress error:", e)
        return None
    finally:
        db.close()
# ==============================
# 🧹 Clear Progress After Submission
# ==============================
def clear_progress(access_code: str, subject: str):
    """Remove saved progress after test submission."""
    db = get_session()
    try:
        db.query(StudentProgress).filter_by(access_code=access_code, subject=subject).delete()
        db.commit()
    except SQLAlchemyError as e:
        print("❌ Clear progress error:", e)
        db.rollback()
    finally:
        db.close()
