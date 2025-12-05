# ==============================
# Third-Party Imports
# ==============================
import streamlit as st
from passlib.context import CryptContext
from passlib.exc import UnknownHashError
from sqlalchemy.orm import Session
import json
import random
import string
import uuid
# db_helpers.py
from models import StudentProgress,School,Subject,TestDuration,ArchivedQuestion
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional, Dict, List, Any
from sqlalchemy import func


# ==============================
# Local Imports
# ==============================
from database import get_session, test_db_connection
from models import (
    Admin,
    Student,
    Question,
    Submission,
    Retake,
    TestResult,

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
# Admin CRUD (Multi-Tenant)
# ==============================
def set_admin(username: str, password: str, role: str = "admin", school_id: int | None = None) -> bool:
    """
    Create or update an admin for a specific school.
    Always stores the password as a bcrypt hash.
    school_id=None means super_admin.
    """
    db = get_session()
    try:
        username = username.strip()
        hashed_pw = hash_password(password)

        admin = db.query(Admin).filter(
            Admin.username.ilike(username),
            Admin.school_id == school_id
        ).first()
        if admin:
            admin.password_hash = hashed_pw
            admin.role = role
        else:
            admin = Admin(
                username=username,
                password_hash=hashed_pw,
                role=role,
                school_id=school_id
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


def add_admin(username: str, password: str, role: str = "admin", school_id: int | None = None) -> bool:
    """
    Add a new admin (bcrypt) for a specific school.
    Returns False if the username already exists in that school.
    """
    db = get_session()
    try:
        if db.query(Admin).filter(
            Admin.username.ilike(username.strip()),
            Admin.school_id == school_id
        ).first():
            return False

        hashed_pw = hash_password(password)
        db.add(Admin(
            username=username.strip(),
            password_hash=hashed_pw,
            role=role,
            school_id=school_id
        ))
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Error adding admin: {e}")
        return False
    finally:
        db.close()



def get_all_admins(as_dict=False, school_id=None):
    db = get_session()
    try:
        query = db.query(Admin)
        if school_id:
            query = query.filter_by(school_id=school_id)
        admins = query.all()

        if as_dict:
            return {a.username: a.role for a in admins}
        return admins
    finally:
        db.close()


def verify_admin(username: str, password: str, school_id: int | None = None) -> Admin | None:
    """
    Verify admin credentials for a specific school.
    Returns the Admin object on success, None on failure.
    """
    db = get_session()
    try:
        admin = db.query(Admin).filter(
            Admin.username.ilike(username.strip()),
            Admin.school_id == school_id
        ).first()

        if admin and verify_password(password, admin.password_hash):
            return admin
        return None
    finally:
        db.close()


def update_admin_password(username: str, new_password: str, school_id: int | None = None) -> bool:
    """
    Update an admin's password for a specific school.
    Caller must pass a plain password; it will be hashed before saving.
    """
    db = get_session()
    try:
        admin = db.query(Admin).filter(
            Admin.username.ilike(username.strip()),
            Admin.school_id == school_id
        ).first()
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
# Ensure Super Admin Exists (Fixed)
# ==============================
def ensure_super_admin_exists():
    """
    Ensure a default super_admin exists.
    - If missing, creates super_admin with password "1234".
    - If present, only ensures correct role (does NOT overwrite password).
    """
    db = get_session()
    try:
        admin = db.query(Admin).filter_by(username="super_admin").first()

        if not admin:
            default_pass = hash_password("1234")
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
            # Only fix the role if it's wrong — no password reset
            if admin.role != "super_admin":
                admin.role = "super_admin"
                db.commit()
                print("🔄 Fixed super_admin role (password unchanged).")
    except Exception as e:
        db.rollback()
        print(f"Error ensuring super_admin: {e}")
    finally:
        db.close()


# ✅ Run on module load
ensure_super_admin_exists()
# ===============================================
# Admin Login (Multi-Tenant / Super Admin support)
# ===============================================
def require_school_context():
    """
    Ensure a valid school_id is available for admin operations.
    Super Admins can bypass this (they can manage all schools).
    """
    import streamlit as st

    role = st.session_state.get("admin_role")
    school_id = (
        st.session_state.get("school_id")
        or st.session_state.get("admin_school_id")
        or st.session_state.get("current_school_id")
    )

    # ✅ Allow super_admin even if no school_id is set
    if role == "super_admin":
        return school_id or 0  # placeholder id for universal access

    # 🚫 Block normal admins if no school assigned
    if not school_id:
        st.error("❌ No school assigned. Please log in again or contact the super admin.")
        st.stop()

    return school_id

# ===============================================
# Admin Login (Multi-Tenant / Super Admin support)
# ===============================================
def require_admin_login(tenant_school_id: int | None = None):
    """
    Streamlit login flow for admins.
    Handles:
      - super_admin → full access
      - school_admin → scoped to assigned school
    """

    # -------------------------------------------------------
    # ✅ Persistent Login Check
    # -------------------------------------------------------
    if (
        "admin_logged_in" in st.session_state
        and st.session_state.admin_logged_in
        and "admin_username" in st.session_state
        and "admin_role" in st.session_state
    ):
        st.sidebar.success(
            f"✅ Logged in as {st.session_state.admin_username} "
            f"({st.session_state.admin_role})"
        )
        return True

    # -------------------------------------------------------
    # 🔐 Super Admin Password Reset Helper
    # -------------------------------------------------------
    def show_super_admin_reset():
        st.info("🔐 Super Admin Password Reset")

        super_admin_user = st.text_input("Super Admin Username", key="super_admin_user")
        super_admin_pass = st.text_input("Super Admin Password", type="password", key="super_admin_pass")

        if st.button("Authenticate Super Admin"):
            sa = get_all_admins(super_admin_user.strip())
            if sa and sa.role == "super_admin" and verify_password(super_admin_pass, sa.password_hash):
                st.session_state.super_admin_authenticated = True
                st.success("✅ Super Admin authenticated! You can now reset admin passwords.")
            else:
                st.error("❌ Invalid Super Admin credentials")

        if st.session_state.get("super_admin_authenticated", False):
            reset_username = st.text_input("Username to Reset", key="reset_target_user")
            new_pw = st.text_input("New Password", type="password", key="reset_new_pw")

            if st.button("Confirm Reset"):
                target = get_all_admins(reset_username.strip())
                if target:
                    update_admin_password(reset_username.strip(), new_pw)
                    st.success(f"✅ Password for '{reset_username}' reset successfully!")
                    st.session_state.super_admin_authenticated = False
                else:
                    st.error("❌ User not found")

    # -------------------------------------------------------
    # 🧩 Admin Login Form
    # -------------------------------------------------------
    st.subheader("🔑 Admin Login")

    col1, col2 = st.columns([3, 1])
    with col1:
        username = st.text_input("Username", key="admin_username_input")
        password = st.text_input("Password", type="password", key="admin_password_input")

    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        login_button = st.button("🔐 Login", use_container_width=True)
        reset_button = st.button("🔁 Reset", use_container_width=True)

    if reset_button:
        st.session_state.show_reset_pw = not st.session_state.get("show_reset_pw", False)
        st.rerun()

    if st.session_state.get("show_reset_pw", False):
        show_super_admin_reset()
        return False

    # -------------------------------------------------------
    # 🚪 Login Button Logic
    # -------------------------------------------------------
    if login_button and username and password:
        db = get_session()
        try:
            query = db.query(Admin).filter(Admin.username.ilike(username.strip()))
            if tenant_school_id:
                query = query.filter(
                    (Admin.school_id == tenant_school_id) | (Admin.role == "super_admin")
                )
            admin = query.first()

            if not admin:
                st.error("❌ Username not found or unauthorized for this school.")
                return False

            if not verify_password(password, admin.password_hash):
                st.error("❌ Invalid password.")
                return False

            # ✅ Safe session setup
            st.session_state.update({
                "admin_logged_in": True,
                "admin_username": admin.username,
                "admin_role": admin.role,
                "admin_school_id": admin.school_id,
                "school_name": admin.school.name if admin.school else "Global",
                "school_id": admin.school_id,
                "current_school_id": admin.school_id if admin.role != "super_admin" else None,
                "admin": {
                    "username": admin.username,
                    "role": admin.role,
                    "school_id": admin.school_id,
                    "school_name": admin.school.name if admin.school else "Global"
                }
            })

            st.sidebar.success(f"✅ Logged in as {admin.username} ({admin.role})")
            st.rerun()

        except Exception as e:
            st.error(f"⚠️ Login error: {e}")
        finally:
            db.close()

    # -------------------------------------------------------
    # 🔄 Password Reset Request (placed *after* login logic)
    # -------------------------------------------------------
    if reset_button:
        st.session_state.show_reset_pw = True
        st.rerun()

    if st.session_state.get("show_reset_pw", False):
        st.info("🔑 Super Admin authentication required to reset passwords.")
        show_super_admin_reset()
        return False


# -----------------------------
# Student Management
# -----------------------------
def generate_access_code(length=6, db=None, school_id=None):
    """Generate a unique access code for students (short and user-friendly) per school."""
    close_db = False
    if db is None:
        db = get_session()
        close_db = True
    try:
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
            # Ensure uniqueness within the same school
            query = db.query(Student).filter_by(access_code=code)
            if school_id:
                query = query.filter_by(school_id=school_id)
            if not query.first():
                return code
    finally:
        if close_db:
            db.close()


def generate_unique_id(db=None, school_id=None):
    """Generate a unique internal ID for tracking students (UUID shortened) per school."""
    close_db = False
    if db is None:
        db = get_session()
        close_db = True
    try:
        while True:
            unique_id = str(uuid.uuid4())[:8]
            query = db.query(Student).filter_by(unique_id=unique_id)
            if school_id:
                query = query.filter_by(school_id=school_id)
            if not query.first():
                return unique_id
    finally:
        if close_db:
            db.close()


def add_student_db(name, class_name, school_id, db=None):
    """Add a new student and associate with the correct school."""
    close_db = False
    if db is None:
        db = get_session()
        close_db = True

    try:
        # Generate unique codes/IDs using your helpers
        access_code = generate_access_code(db=db, school_id=school_id)
        unique_id = generate_unique_id(db=db, school_id=school_id)

        # ✅ FIX: include unique_id in the student model
        student = Student(
            unique_id=unique_id,          # <-- THIS WAS MISSING
            name=name.strip(),
            class_name=class_name,
            access_code=access_code,
            can_retake=True,
            submitted=False,
            school_id=school_id
        )

        db.add(student)
        db.commit()
        db.refresh(student)
        return student

    except Exception as e:
        db.rollback()
        raise e

    finally:
        if close_db:
            db.close()



def bulk_add_students_db(students_list, school_id, db=None):
    """Bulk add multiple students under the same school."""
    close_db = False
    if db is None:
        db = get_session()
        close_db = True

    added_students = []
    summary = {"new": 0, "reused": 0}

    try:
        for entry in students_list:
            if not isinstance(entry, (list, tuple)) or len(entry) != 2:
                raise ValueError(f"Invalid student entry format: {entry}")
            name, class_name = entry
            name, class_name = name.strip(), class_name.strip()

            existing = (
                db.query(Student)
                .filter_by(name=name, class_name=class_name, school_id=school_id)
                .first()
            )

            if existing:
                added_students.append({
                    "name": existing.name,
                    "class_name": existing.class_name,
                    "access_code": existing.access_code,
                    "status": "reused"
                })
                summary["reused"] += 1
                continue

            access_code = generate_access_code(db=db, school_id=school_id)
            unique_id = generate_unique_id(db=db, school_id=school_id)

            student = Student(
                unique_id=unique_id,
                name=name,
                class_name=class_name,
                access_code=access_code,
                can_retake=True,
                submitted=False,
                school_id=school_id
            )
            db.add(student)
            db.flush()

            added_students.append({
                "name": student.name,
                "class_name": student.class_name,
                "access_code": student.access_code,
                "unique_id": student.unique_id,
                "status": "new"
            })
            summary["new"] += 1

        db.commit()
        return {"students": added_students, "summary": summary}

    except Exception as e:
        db.rollback()
        raise e

    finally:
        if close_db:
            db.close()


def get_student_by_access_code_db(access_code, school_id=None):
    """Fetch student ORM object by access code (case-insensitive) and optional school."""
    clean_code = access_code.strip().upper()
    db = get_session()
    try:
        query = db.query(Student).filter(func.upper(Student.access_code) == clean_code)
        if school_id:
            query = query.filter_by(school_id=school_id)
        return query.first()
    finally:
        db.close()


def get_student_by_code(db: Session, access_code: str, school_id=None):
    """
    Fetch a student record by their unique access code.
    Returns None if not found.
    """
    try:
        query = db.query(Student).filter_by(access_code=access_code)
        if school_id:
            query = query.filter_by(school_id=school_id)
        return query.first()
    except Exception as e:
        print(f"❌ Error fetching student by code: {e}")
        return None


def update_student_submission_db(access_code, school_id=None):
    """Mark student as submitted = True for a specific school."""
    db = get_session()
    try:
        code = normalize_code(access_code)
        query = db.query(Student).filter(Student.access_code == code)
        if school_id:
            query = query.filter_by(school_id=school_id)
        student = query.first()
        if student:
            student.submitted = True
            db.commit()
    finally:
        db.close()


def reset_student_retake_db(access_code, school_id=None):
    """Reset student so they can retake (submitted = False) for a specific school."""
    db = get_session()
    try:
        code = normalize_code(access_code)
        query = db.query(Student).filter(Student.access_code == code)
        if school_id:
            query = query.filter_by(school_id=school_id)
        student = query.first()
        if student:
            student.submitted = False
            db.commit()
    finally:
        db.close()

def get_users(school_id=None):
    """
    Return all students as a dict keyed by access_code.
    - If school_id is provided → returns only that school’s students.
    - Otherwise → returns all students (for super_admin).
    """
    db = get_session()
    try:
        query = db.query(Student)
        if school_id is not None:
            query = query.filter_by(school_id=school_id)

        students = query.all()

        return {
            s.access_code.strip().upper(): {
                "id": s.id,
                "name": s.name,
                "class_name": s.class_name,
                "unique_id": s.unique_id,
                "access_code": s.access_code.strip().upper(),
                "submitted": bool(s.submitted),
                "school_id": s.school_id,
                "can_retake": bool(s.can_retake),
            }
            for s in students
        }

    finally:
        db.close()


def add_question_db(class_name: str, subject: str, text: str, options: List[str], correct: str, school_id=None):
    """Add a single question to the DB with optional school_id."""
    db = get_session()
    try:
        db.add(Question(
            class_name=class_name.strip().upper(),
            subject=subject.strip().capitalize(),
            question_text=text.strip(),
            options=json.dumps([opt.strip() for opt in options]),
            answer=correct.strip(),
            school_id=school_id  # <-- multi-tenant
        ))
        db.commit()
    finally:
        db.close()


def get_questions_db(class_name: str, subject: str = None, school_id=None) -> List[Dict[str, Any]]:
    """Fetch questions for a class (optionally filtered by subject and school)."""
    db = get_session()
    try:
        query = db.query(Question).filter(Question.class_name.ilike(class_name.strip()))
        if subject:
            query = query.filter(Question.subject.ilike(subject.strip()))
        if school_id:
            query = query.filter_by(school_id=school_id)
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
                "archived": q.archived
            })
        return result
    finally:
        db.close()

@st.cache_data(ttl=60)
def handle_uploaded_questions(class_name, subject, valid_questions, school_id=None):
    """Upload and replace questions for a class/subject with proper subject_id and automatic school_id."""
    from sqlalchemy import and_
    db = get_session()
    try:
        # Automatically detect school_id from session if not provided
        if not school_id:
            school_id = get_current_school_id()

        if not school_id:
            return {"success": False, "error": "School ID not found in session or argument."}

        class_name_lower = class_name.strip().lower()
        subject_lower = subject.strip().lower()

        # STEP 0: Fetch the corresponding Subject row within this school
        subject_obj = db.query(Subject).filter(
            func.lower(Subject.name) == subject_lower,
            func.lower(Subject.class_name) == class_name_lower,
            Subject.school_id == school_id
        ).first()

        if not subject_obj:
            return {
                "success": False,
                "error": f"Subject '{subject}' for class '{class_name}' not found in DB for this school (ID={school_id})."
            }

        # STEP 1: Delete old questions for this class, subject, and school
        filters = [
            Question.class_name == class_name_lower,
            Question.subject == subject_lower,
            Question.school_id == school_id
        ]
        deleted_count = db.query(Question).filter(and_(*filters)).delete(synchronize_session=False)
        db.commit()

        # STEP 2: Insert new questions
        new_records = []
        for q in valid_questions:
            question_text = q.get("question", "").strip()
            options = q.get("options", [])
            answer = q.get("answer", "").strip()

            clean_options = [opt.strip() for opt in options if isinstance(opt, str) and opt.strip()]
            if len(clean_options) < 2:
                print(f"⚠️ Skipping question '{question_text}' — not enough options.")
                continue

            new_records.append(
                Question(
                    class_name=class_name_lower,
                    subject=subject_lower,
                    subject_id=subject_obj.id,  # link to Subject
                    question_text=question_text,
                    options=json.dumps(clean_options),
                    answer=answer,
                    school_id=school_id
                )
            )

        db.add_all(new_records)
        db.commit()

        inserted_count = len(new_records)
        print(f"✅ Upload successful: Deleted {deleted_count}, Inserted {inserted_count}")

        return {"success": True, "inserted": inserted_count, "deleted": deleted_count}

    except Exception as e:
        print("❌ Upload error:", e)
        db.rollback()
        return {"success": False, "error": str(e)}

    finally:
        db.close()

@st.cache_data(ttl=60)
def load_questions_db(class_name: str, subject: str, school_id=None, limit: int = 30) -> list[dict]:
    """Robust question loader that handles case, whitespace, and mixed formatting in DB."""
    db = get_session()
    try:
        # Auto-detect school_id if missing
        if not school_id:
            school_id = get_current_school_id()

        if not class_name or not subject:
            print("⚠️ Missing class_name or subject in load_questions_db:", class_name, subject)
            return []

        # Normalize inputs
        class_key = class_name.lower().replace(" ", "")   # removes spaces (jhs 1 → jhs1)
        subject_key = subject.lower().strip()             # english → english

        # Build robust query
        query = db.query(Question).filter(
            func.replace(func.lower(Question.class_name), ' ', '') == class_key,
            func.lower(Question.subject) == subject_key
        )

        if school_id:
            query = query.filter(Question.school_id == school_id)

        # Random selection
        questions = query.order_by(func.random()).limit(limit).all()

        result = []
        for q in questions:
            # Parse options safely
            try:
                opts = json.loads(q.options) if isinstance(q.options, str) else q.options
            except Exception:
                opts = []

            result.append({
                "id": q.id,
                "question_text": q.question_text,
                "options": opts,
                "answer": q.answer,
                "type": getattr(q, "type", "objective"),
                "subject_id": q.subject_id,
                "school_id": q.school_id
            })

        return result

    except Exception as e:
        print("❌ Error loading questions:", e)
        return []

    finally:
        db.close()

def delete_student_db(student_identifier, school_id=None):
    """
    Delete a student record using either integer ID or access_code.
    Optional school_id ensures only students from that school are deleted.
    """
    db = get_session()
    try:
        query = db.query(Student)
        if school_id:
            query = query.filter(Student.school_id == school_id)

        # Determine if input is integer ID or string access_code
        if isinstance(student_identifier, int) or str(student_identifier).isdigit():
            student = query.filter_by(id=int(student_identifier)).first()
        else:
            student = query.filter_by(access_code=str(student_identifier).strip()).first()

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


import re

def normalize_text(text: str) -> str:
    """Normalize text for safe string comparison (case + whitespace insensitive)."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.strip().lower())




def add_submission_db(student_id: int, subject: str, submissions: list, score: int, total: int, percentage: float, school_id=None):
    """
    Save per-question submissions and a TestResult summary.
    Multi-tenant aware via optional school_id.
    """
    db = get_session()
    try:
        student = db.query(Student).filter_by(id=student_id).first()
        if not student:
            raise ValueError("Invalid student ID")

        # Verify school consistency if school_id provided
        if school_id and student.school_id != school_id:
            raise ValueError("Student does not belong to this school")

        # Save each per-question submission
        for sub in submissions:
            db.add(Submission(
                student_id=student.id,
                question_id=sub["question_id"],
                selected_answer=sub["selected"],
                correct=sub["is_correct"],
                subject=subject,
                school_id=school_id or student.school_id
            ))

        # Save test result summary
        db.add(TestResult(
            student_id=student.id,
            subject=subject,
            score=score,
            total=total,
            percentage=percentage,
            school_id=school_id or student.school_id
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
def get_all_submissions_db(school_id=None):
    """
    Return all submissions in the database.
    Optional school_id filters by school.
    """
    db = get_session()
    try:
        query = db.query(Submission)
        if school_id:
            query = query.filter(Submission.school_id == school_id)
        return query.all()
    except Exception as e:
        print(f"[DB ERROR] Failed to fetch submissions: {e}")
        return []
    finally:
        db.close()

# -----------------------------
# Score Calculation
# -----------------------------
def calculate_score_db(student_name, subject, questions, answers_dict):
    """
    Compare answers_dict against correct answers and return score details.
    This function does not require school_id because it only computes scores.
    """
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
def get_submission_db(student_id, subject=None, school_id=None):
    """Fetch submissions for a student (optionally filtered by subject and school)."""
    db = get_session()
    try:
        query = db.query(Submission).filter_by(student_id=student_id)
        if subject:
            query = query.filter_by(subject=subject)
        if school_id:
            query = query.filter(Submission.school_id == school_id)
        return query.all()
    finally:
        db.close()


# -----------------------------
# Question Tracker (UI only)
# -----------------------------
def show_question_tracker(questions, current_q, answers):
    """Streamlit UI tracker: progress bar + clickable grid navigator."""
    import uuid
    import streamlit as st

    total = len(questions)
    marked = set(st.session_state.get("marked_for_review", []))

    # Stable unique test ID for session buttons
    if "test_id" not in st.session_state:
        st.session_state.test_id = str(uuid.uuid4())
    test_id = st.session_state.test_id

    student_id = st.session_state.get("student", {}).get("id", "anon")
    subject = st.session_state.get("subject", "unknown")

    # -----------------------------
    # Progress Summary + Bar
    # -----------------------------
    answered = sum(1 for ans in answers if ans not in ["", None])
    percent = int((answered / total) * 100) if total else 0

    st.markdown(
        f"<div style='background:#f9f9f9; padding:8px; border-radius:6px; "
        f"border:1px solid #ddd; margin-bottom:8px;'>"
        f"<b>📊 Progress:</b> {answered}/{total} answered — <b>{percent}%</b></div>",
        unsafe_allow_html=True,
    )
    st.progress(answered / total if total else 0)

    # -----------------------------
    # Question Navigator (Expander)
    # -----------------------------
    with st.expander("🔽 Question Navigator", expanded=False):
        for row_start in range(0, total, 10):  # 10 buttons per row
            cols = st.columns(10)
            for i in range(row_start, min(row_start + 10, total)):
                color = (
                    "#FFA500" if i in marked
                    else "#2ECC71" if answers[i] not in ["", None]
                    else "#E74C3C"
                )

                btn_key = f"jump_{subject}_{student_id}_{test_id}_{i}"
                label_html = f"""
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
                        border:{'3px solid #000' if i == current_q else 'none'};
                    ">{i+1}</div>
                """

                # Button click updates current question
                if cols[i % 10].button(f" ", key=btn_key):
                    st.session_state.current_q = i
                    st.rerun()

                cols[i % 10].markdown(label_html, unsafe_allow_html=True)

        st.markdown(
            "<p style='font-size:13px;'>🟩 Answered | 🟥 Unanswered | 🟨 Marked for review</p>",
            unsafe_allow_html=True
        )


# ==============================
# 🕒 Test Duration Helpers
# ==============================

def set_test_duration(class_name: str, subject: str, school_id: int, duration_minutes: int):
    """
    Save or update test duration in DB for a given class, subject, and school.
    Duration is stored in SECONDS.
    """
    if not (class_name and subject and school_id):
        print("⚠️ Missing class, subject, or school_id in set_test_duration().")
        return

    db = get_session()
    try:
        from models import TestDuration  # ensure the model is imported

        duration_seconds = duration_minutes * 60
        record = db.query(TestDuration).filter_by(
            class_name=class_name.strip(),
            subject=subject.strip(),
            school_id=school_id
        ).first()

        if record:
            record.duration = duration_seconds
        else:
            db.add(TestDuration(
                class_name=class_name.strip(),
                subject=subject.strip(),
                school_id=school_id,
                duration=duration_seconds
            ))

        db.commit()
        print(f"✅ Duration saved: {duration_minutes} min for {class_name}-{subject} (school_id={school_id})")
    except Exception as e:
        print(f"❌ set_test_duration() error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def get_test_duration(class_name: str, subject: str, school_id: int):
    """
    Returns duration IN MINUTES.
    DB stores duration in SECONDS.
    """
    if not (class_name and subject and school_id):
        return None

    db = get_session()
    try:
        from models import TestDuration
        from sqlalchemy import and_

        record = db.query(TestDuration).filter(
            and_(
                TestDuration.class_name.ilike(class_name.strip()),
                TestDuration.subject.ilike(subject.strip()),
                TestDuration.school_id == school_id
            )
        ).first()

        if record and record.duration and record.duration > 0:
            # Convert seconds → minutes
            duration_minutes = record.duration // 60

            print("⏱ LOADED DURATION:", record.duration, "sec →", duration_minutes, "mins")

            return max(1, int(duration_minutes))

        return None

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

def clear_questions_db(school_id=None):
    """
    Delete questions.
    - If `school_id` is provided → delete only that school's questions.
    - If `school_id` is None → super_admin can delete all.
    """
    db = get_session()
    try:
        query = db.query(Question)
        if school_id is not None:
            query = query.filter_by(school_id=school_id)
        deleted_count = query.delete(synchronize_session=False)
        db.commit()
        return deleted_count  # Optional: return number of deleted records
    finally:
        db.close()



def load_subjects(class_name: str | None = None, school_id: int | None = None):
    """Load subjects automatically filtered by current school."""
    db = get_session()
    try:
        if not school_id:
            school_id = get_current_school_id()

        query = db.query(Subject).filter(Subject.school_id == school_id)

        # Filter by class
        if isinstance(class_name, str) and class_name.strip():
            query = query.filter(Subject.class_name.ilike(class_name.strip()))

        # Return list of dicts: [{"id": 1, "name": "English"}, ...]
        return [{"id": s.id, "name": s.name} for s in query.all()]

    finally:
        db.close()

def save_subjects(subjects: list, class_name: str | None = None):
    """Safely save (add/update) subjects without deleting linked ones."""
    db = get_session()
    try:
        school_id = get_current_school_id()
        if not school_id:
            st.session_state["subject_msg"] = ("error", "❌ No school ID found for current admin.")
            return False

        if not class_name:
            st.session_state["subject_msg"] = ("error", "⚠️ Please select a valid class before saving subjects.")
            return False

        # Normalize input
        new_subjects = sorted(set([str(x).strip() for x in subjects if str(x).strip()]))

        # Get existing subjects for this class & school
        existing_subjects = {
            s.name.lower(): s
            for s in db.query(Subject)
            .filter(
                Subject.school_id == school_id,
                Subject.class_name.ilike(class_name.strip())
            )
            .all()
        }

        added = 0
        for s in new_subjects:
            if s.lower() not in existing_subjects:
                db.add(Subject(name=s, class_name=class_name.strip(), school_id=school_id))
                added += 1

        db.commit()

        msg = f"✅ {added} new subject(s) added for {class_name}." if added > 0 else f"ℹ️ No new subjects to add for {class_name}."
        st.session_state["subject_msg"] = ("success", msg)
        st.session_state["last_updated_class"] = class_name.strip()
        return True

    except Exception as e:
        db.rollback()
        st.session_state["subject_msg"] = ("error", f"❌ Error saving subjects: {e}")
        return False

    finally:
        db.close()


def delete_subject(subject_name: str, school_id: int | None = None, class_name: str | None = None):
    """Delete a subject safely by name, class, and school."""
    db = get_session()
    try:
        query = db.query(Subject).filter(Subject.name.ilike(subject_name.strip()))
        if school_id:
            query = query.filter(Subject.school_id == school_id)
        if class_name:
            query = query.filter(Subject.class_name.ilike(class_name.strip()))

        subject = query.first()
        if not subject:
            st.warning(f"⚠️ Subject '{subject_name}' not found for {class_name}.")
            return False

        # Check linked questions (by name + class + school)
        linked_questions = db.query(Question).filter(
            Question.subject.ilike(subject_name.strip()),
            Question.class_name.ilike(class_name.strip()),
            Question.school_id == school_id
        ).count()

        if linked_questions > 0:
            st.warning(f"⚠️ Cannot delete '{subject_name}' — {linked_questions} question(s) linked.")
            return False

        db.delete(subject)
        db.commit()
        st.success(f"✅ Subject '{subject_name}' deleted successfully for {class_name}.")
        st.rerun()
        return True

    except Exception as e:
        db.rollback()
        st.error(f"❌ Error deleting subject: {e}")
        return False
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
def clear_students_db(school_id=None):
    """
    Delete students.
    - If `school_id` is provided → delete only that school's students.
    - If `school_id` is None → delete all (super_admin only).
    """
    db = get_session()
    try:
        query = db.query(Student)  # ✅ fixed from User → Student
        if school_id is not None:
            query = query.filter_by(school_id=school_id)
        deleted_count = query.delete(synchronize_session=False)
        db.commit()
        return deleted_count
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

def clear_submissions_db(school_id=None):
    """
    Delete submissions.
    - If `school_id` is provided → delete only that school's submissions.
    - If `school_id` is None → delete all (super_admin only).
    """
    db = get_session()
    try:
        query = db.query(Submission)
        if school_id is not None:
            # Join with Student to ensure we only delete submissions belonging to that school
            query = query.join(Student).filter(Student.school_id == school_id)
        deleted_count = query.delete(synchronize_session=False)
        db.commit()
        return deleted_count
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
from datetime import datetime
from sqlalchemy.orm import Session

from datetime import datetime
from sqlalchemy.orm import Session

def archive_question(session: Session, question_id: int) -> bool:
    """Move a question from 'questions' to 'archived_questions'."""
    try:
        # ✅ SQLAlchemy 2.x way — .get() moved to session.get()
        q = session.get(Question, question_id)
        if not q:
            return False

        # ✅ Do NOT copy the same id — let ArchivedQuestion auto-increment
        archived = ArchivedQuestion(
            class_name=q.class_name,
            subject=q.subject,
            subject_id=q.subject_id,
            question_text=q.question_text,
            options=q.options,
            answer=q.answer,
            created_by=q.created_by,
            created_at=q.created_at,
            archived=True,
            archived_at=datetime.utcnow(),
            school_id=q.school_id,
        )

        session.add(archived)
        session.delete(q)
        session.commit()
        return True

    except Exception as e:
        session.rollback()
        print(f"❌ Archive error: {e}")
        return False


def restore_question(session: Session, archived_id: int) -> bool:
    """Move a question back from 'archived_questions' to 'questions'."""
    try:
        aq = session.get(ArchivedQuestion, archived_id)
        if not aq:
            return False

        restored = Question(
            class_name=aq.class_name,
            subject=aq.subject,
            subject_id=aq.subject_id,
            question_text=aq.question_text,
            options=aq.options,
            answer=aq.answer,
            created_by=aq.created_by,
            created_at=aq.created_at,
            school_id=aq.school_id,
            archived=False,
        )

        session.add(restored)
        session.delete(aq)
        session.commit()
        return True

    except Exception as e:
        session.rollback()
        print(f"❌ Restore error: {e}")
        return False


def get_archived_questions(session: Session, class_name=None, subject=None, school_id=None):
    """Fetch archived questions, with optional filters."""
    query = session.query(ArchivedQuestion)

    if class_name:
        query = query.filter(ArchivedQuestion.class_name == class_name)
    if subject:
        query = query.filter(ArchivedQuestion.subject == subject)
    if school_id:
        query = query.filter(ArchivedQuestion.school_id == school_id)

    return query.order_by(ArchivedQuestion.archived_at.desc()).all()


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
def has_submitted_test(
    access_code: str,
    subject_id: int,
    school_id: int,
    test_type: str
) -> bool:
    db = get_session()
    try:
        # Get the most recent progress record for this test
        record = (
            db.query(StudentProgress)
            .filter(
                StudentProgress.access_code == access_code,
                StudentProgress.subject_id == subject_id,
                StudentProgress.school_id == school_id,
                StudentProgress.test_type == test_type
            )
            .order_by(StudentProgress.id.desc())   # latest record
            .first()
        )

        return record.submitted if record else False

    finally:
        db.close()

def save_progress(
    access_code,
    subject_id,
    answers,
    current_q,
    start_time,
    duration,
    questions,
    school_id,
    test_type,
    student_id=None,
    submitted=False
):

    def normalize_question(q):
        if isinstance(q, (int, str)):
            return q
        return q.id

    db = get_session()
    try:
        question_list = [normalize_question(q) for q in questions]

        existing = db.query(StudentProgress).filter_by(
            access_code=access_code,
            subject_id=subject_id,   # ✅ correct
            school_id=school_id,
            test_type=test_type
        ).first()

        if existing:
            existing.answers = answers
            existing.current_q = current_q
            existing.start_time = float(start_time)
            existing.duration = int(duration)
            existing.questions = question_list
            existing.submitted = bool(submitted)
            if student_id:
                existing.student_id = student_id
        else:
            db.add(StudentProgress(
                access_code=access_code,
                subject_id=subject_id,   # ✅ changed
                school_id=school_id,
                test_type=test_type,
                answers=answers,
                current_q=current_q,
                start_time=float(start_time),
                duration=int(duration),
                questions=question_list,
                student_id=student_id,
                submitted=submitted
            ))

        db.commit()

    finally:
        db.close()


@st.cache_data(ttl=300)
def load_progress(
    access_code: str,
    subject_id: int,
    school_id: int | None = None,
    test_type: str = "objective"
) -> Optional[Dict]:

    db = get_session()
    try:
        query = db.query(StudentProgress).filter_by(
            access_code=access_code,
            subject_id=subject_id,      # ✅ correct
            test_type=test_type
        )

        if school_id is not None:
            query = query.filter(StudentProgress.school_id == school_id)

        record = query.first()
        if not record:
            return None

        return {
            "answers": record.answers or [],
            "current_q": record.current_q or 0,
            "start_time": record.start_time or datetime.now().timestamp(),
            "duration": record.duration or 1800,
            "questions": record.questions or [],
            "test_type": record.test_type,
            "submitted": record.submitted,
            "student_id": record.student_id,
        }

    finally:
        db.close()


# ==============================
# ✅ Clear Progress After Submission
# ==============================
def clear_progress(access_code: str, subject_id: int, school_id: int | None = None, test_type: str | None = None):
    db = get_session()
    try:
        query = db.query(StudentProgress).filter_by(
            access_code=access_code,
            subject_id=subject_id    # ✅ correct
        )

        if school_id:
            query = query.filter(StudentProgress.school_id == school_id)

        if test_type:
            query = query.filter(StudentProgress.test_type == test_type)

        query.delete()
        db.commit()

    finally:
        db.close()

# ------------------------------
# Generate short unique school code
# ------------------------------
def generate_unique_school_code(name, db, length=6, max_attempts=10):
    """
    Generate a unique school code. Retry up to max_attempts to avoid collisions.
    """
    base = ''.join(e for e in name.upper() if e.isalnum())[:length]

    for _ in range(max_attempts):
        suffix = ''.join(random.choices(string.digits, k=3))
        code = f"{base}{suffix}"
        if not db.query(School).filter_by(code=code).first():
            return code
    raise ValueError(f"Failed to generate a unique school code for {name} after {max_attempts} attempts.")


def add_school(name, address=None, code=None, db=None, return_dict=False):
    """
    Add a school with optional code. Returns model or dict.

    Parameters:
        name (str): School name (required)
        address (str, optional)
        code (str, optional): if not provided, generated automatically
        db (Session, optional): SQLAlchemy session
        return_dict (bool): if True, returns a dict instead of model
    """
    if not name or not name.strip():
        raise ValueError("School name cannot be empty.")

    close_db = False
    if db is None:
        db = get_session()
        close_db = True

    try:
        # Check for existing school by name
        existing = db.query(School).filter(School.name.ilike(name.strip())).first()
        if existing:
            return {
                "exists": True,
                "id": existing.id,
                "name": existing.name,
                "code": existing.code
            } if return_dict else existing

        # Generate unique code if not provided
        school_code = code or generate_unique_school_code(name, db)

        # Create and save
        school = School(name=name.strip(), code=school_code, address=address)
        db.add(school)
        db.commit()
        db.refresh(school)

        return {
            "exists": False,
            "id": school.id,
            "name": school.name,
            "code": school.code
        } if return_dict else school

    except SQLAlchemyError as e:
        db.rollback()
        raise e
    finally:
        if close_db:
            db.close()


## ------------------------------
# Get all schools (returns School objects)
# ------------------------------
def get_all_schools(db=None):
    close_db = False
    if db is None:
        db = get_session()
        close_db = True

    try:
        # Return the actual ORM objects
        return db.query(School).order_by(School.name.asc()).all()
    finally:
        if close_db:
            db.close()

# ------------------------------
# Get students by school (as dicts)
# ------------------------------
def get_students_by_school(school_id, class_level=None, active_only=True, db=None):
    """
    Return students of a school as a list of dicts, with optional filters.
    Suitable for Streamlit tables or selectboxes.
    """
    if not school_id:
        raise ValueError("School ID is required.")

    close_db = False
    if db is None:
        db = get_session()
        close_db = True

    try:
        query = db.query(Student).filter(Student.school_id == school_id)

        # Match your model field — use class_name, not class_level
        if class_level:
            query = query.filter(Student.class_name == class_level)

        # You can skip active_only unless you later add an `is_active` field
        students = query.order_by(Student.name.asc()).all()

        return [
            {
                "id": s.id,
                "name": s.name,
                "class_name": s.class_name,
                "access_code": s.access_code,
                "can_retake": getattr(s, "can_retake", True),
                "submitted": getattr(s, "submitted", False)
            }
            for s in students
        ]

    except Exception as e:
        print(f"❌ Error fetching students for school {school_id}: {e}")
        return []

    finally:
        if close_db:
            db.close()


def get_current_school_id() -> int | None:
    """
    Safely fetch the current logged-in admin's school_id from session.
    Works for both super_admin and school_admin.
    """
    return (
        st.session_state.get("school_id")
        or st.session_state.get("admin_school_id")
        or st.session_state.get("current_school_id")
    )

# =====================================================
# 🧭 ASSIGN ADMIN TO A SCHOOL
# =====================================================
def assign_admin_to_school(admin_id: int | str, school_id: int, db=None):
    """
    Assign an admin to a specific school.
    Accepts either numeric admin_id or username.
    """
    if not admin_id or not school_id:
        raise ValueError("Admin ID and School ID are required.")

    close_db = False
    if db is None:
        db = get_session()
        close_db = True

    try:
        # ✅ Handle both ID (int) and username (str)
        if isinstance(admin_id, int) or (isinstance(admin_id, str) and admin_id.isdigit()):
            admin = db.query(Admin).filter_by(id=int(admin_id)).first()
        else:
            admin = db.query(Admin).filter(Admin.username.ilike(admin_id.strip())).first()

        school = db.query(School).filter_by(id=school_id).first()

        if not admin:
            raise ValueError("Admin not found.")
        if not school:
            raise ValueError("School not found.")

        admin.school_id = school_id
        db.commit()

        return {
            "success": True,
            "message": f"Admin '{admin.username}' assigned to school '{school.name}'."
        }

    except SQLAlchemyError as e:
        db.rollback()
        raise e
    finally:
        if close_db:
            db.close()

# =====================================================
# 🧭 SCHOOL CONTEXT HANDLER (For Non–Super Admins)
# =====================================================

def get_or_select_school():
    """
    Returns a valid school_id for the current admin.
    If none is assigned, allows them to select or create one.
    """
    session = get_session()
    admin_role = st.session_state.get("admin_role")
    school_id = st.session_state.get("school_id")

    # If already assigned, return it
    if school_id:
        return school_id

    # If Super Admin, they already pick schools manually later
    if admin_role == "super_admin":
        return None

    st.warning("⚠️ No school assigned to your account yet.")
    st.markdown("### 🏫 Select or Create Your School")

    # Show existing schools
    schools = get_all_schools()
    school_options = [s.name for s in schools] if schools else []

    choice = st.selectbox(
        "Select School or Add New:",
        school_options + ["➕ Add New School"],
        key="admin_select_school"
    )

    if choice == "➕ Add New School":
        new_school_name = st.text_input("Enter New School Name:", key="new_school_name_field")
        if st.button("✅ Create School", key="create_school_btn"):
            if not new_school_name.strip():
                st.error("❌ Please enter a valid school name.")
            else:
                try:
                    new_school = add_school(new_school_name.strip())
                    st.success(f"🏫 School '{new_school.name}' created successfully!")
                    # Assign to current admin
                    assign_admin_to_school(st.session_state["admin_id"], new_school.id)
                    st.session_state["school_id"] = new_school.id
                    st.session_state["school_name"] = new_school.name
                    st.rerun()
                except Exception as e:
                    st.error(f"⚠️ Failed to create school: {e}")
    else:
        selected_school = next((s for s in schools if s.name == choice), None)
        if selected_school and st.button(f"🏫 Use {selected_school.name}", key="use_school_btn"):
            assign_admin_to_school(st.session_state["admin_id"], selected_school.id)
            st.session_state["school_id"] = selected_school.id
            st.session_state["school_name"] = selected_school.name
            st.success(f"✅ You are now managing: {selected_school.name}")
            st.rerun()

    st.stop()  # Stop page until selection is made

def delete_school(school_id, db=None):
    from sqlalchemy.exc import SQLAlchemyError, IntegrityError
    from models import School

    close_db = False
    if db is None:
        db = get_session()
        close_db = True

    try:
        print(f"🧩 DB in use: {db.bind.url}")
        print(f"🗑️ Trying to delete school ID: {school_id} (type: {type(school_id)})")

        deleted = db.query(School).filter(School.id == int(school_id)).delete(synchronize_session=False)
        db.commit()

        print(f"🧾 Deleted count: {deleted}")

        # Verify immediately
        remaining = db.query(School).filter(School.id == int(school_id)).first()
        print("🕵️‍♂️ Remaining record:", remaining)

        return True

    except Exception as e:
        db.rollback()
        print(f"💥 Error during delete: {type(e).__name__}: {e}")
        return False

    finally:
        if close_db:
            db.close()


def load_student_results(access_code: str, school_id=None):
    """
    Fetch all test results for a student using their access code.
    Joins students -> test_results by student_id.
    """
    db = get_session()
    try:
        # Step 1: Find the student by access code (case-insensitive)
        student = (
            db.query(Student)
            .filter(func.upper(Student.access_code) == access_code.strip().upper())
            .first()
        )

        if not student:
            print(f"⚠️ No student found for access code {access_code}")
            return []

        # Step 2: Fetch test results by student_id
        results_query = db.query(TestResult).filter_by(student_id=student.id)

        if school_id:
            results_query = results_query.filter_by(school_id=school_id)

        results = results_query.order_by(TestResult.taken_at.desc()).all()

        # ✅ Attach class_name manually if needed for display
        for r in results:
            r.class_name = getattr(student, "class_name", "N/A")

        return results

    except Exception as e:
        print(f"❌ Error loading results for {access_code}: {e}")
        return []
    finally:
        db.close()

def can_take_test(access_code, subject_id, school_id):
    db = get_session()
    try:
        # Load student
        from models import Student, StudentProgress

        student = db.query(Student).filter_by(
            access_code=access_code,
            school_id=school_id
        ).first()

        if not student:
            return False

        # Check all attempts for that subject
        attempts = db.query(StudentProgress).filter_by(
            access_code=access_code,
            subject_id=subject_id,
            school_id=school_id
        ).all()

        # No attempt → allow first test
        if not attempts:
            return True

        # If any attempt is not submitted → allow resume
        if any(not a.submitted for a in attempts):
            return True

        # All attempts submitted → require admin retake
        return bool(student.can_retake)

    finally:
        db.close()


def get_retake_db(access_code: str, subject_id: int, school_id: int = None) -> bool:
    """
    Check if a student has retake permission for a subject (multi-tenant aware).
    Uses subject_id instead of subject text.
    """
    db = get_session()
    try:
        student = db.query(Student).filter_by(access_code=access_code).first()
        if not student:
            return False

        # Ensure subject_id is always int (avoids dict or string errors)
        try:
            subject_id = int(subject_id)
        except:
            return False

        query = db.query(Retake).filter_by(
            student_id=student.id,
            subject_id=subject_id
        )

        # Only filter on school_id if provided
        if school_id is not None:
            query = query.filter(Retake.school_id == school_id)

        retake = query.first()
        return bool(retake and retake.can_retake)

    finally:
        db.close()

def decrement_retake(student_id: int, subject_id: int, school_id: int):
    db = get_session()
    try:
        progress = db.query(StudentProgress).filter_by(
            student_id=student_id,
            subject_id=subject_id,
            school_id=school_id
        ).first()

        if progress:
            progress.submitted = True

        # Disable retake automatically after use
        retake = db.query(Retake).filter_by(
            student_id=student_id,
            subject_id=subject_id,
            school_id=school_id
        ).first()

        if retake:
            retake.can_retake = False

        db.commit()
    except Exception as e:
        db.rollback()
        print("❌ decrement_retake error:", e)
    finally:
        db.close()



def set_retake_db(
        access_code: str,
        subject_id: int,
        can_retake: bool = True,
        school_id=None,
        auto_create_student=False,
        student_name=None,
        class_name=None
):
    """
    Create or update a student's retake permission for a subject using subject_id.
    """
    db = get_session()
    try:
        access_code = str(access_code).strip()

        # Convert IDs safely
        try:
            subject_id = int(subject_id)
        except:
            raise ValueError(f"Invalid subject_id: {subject_id}")

        school_id_int = int(school_id) if school_id is not None else None

        # Find student
        query = db.query(Student).filter(func.trim(Student.access_code) == access_code)
        if school_id_int is not None:
            query = query.filter(Student.school_id == school_id_int)

        student = query.first()

        # Auto-create student if needed
        if not student and auto_create_student:
            if not student_name or not class_name:
                raise ValueError(
                    "student_name and class_name are required when auto_create_student=True."
                )
            student = Student(
                name=student_name.strip(),
                access_code=access_code,
                class_name=class_name.strip(),
                school_id=school_id_int or 0,
            )
            db.add(student)
            db.commit()
            db.refresh(student)

        if not student:
            raise ValueError(
                f"Invalid student access code '{access_code}' for school '{school_id}'"
            )

        # --- Update / Create Retake entry ---
        retake_query = db.query(Retake).filter(
            Retake.student_id == student.id,
            Retake.subject_id == subject_id
        )

        if school_id_int is not None:
            retake_query = retake_query.filter(
                (Retake.school_id == school_id_int) | (Retake.school_id.is_(None))
            )

        retake = retake_query.one_or_none()

        if retake:
            retake.can_retake = can_retake
            # Fix missing school_id on legacy rows
            if retake.school_id is None and school_id_int is not None:
                retake.school_id = school_id_int
        else:
            retake = Retake(
                student_id=student.id,
                subject_id=subject_id,
                can_retake=can_retake,
                school_id=school_id_int
            )
            db.add(retake)

        db.commit()

        print(
            f"🟢 Retake {'enabled' if can_retake else 'disabled'} for {student.name} "
            f"({access_code}) | subject_id={subject_id}"
        )

    except Exception as e:
        db.rollback()
        print(f"❌ Error in set_retake_db: {e}")
        raise
    finally:
        db.close()
