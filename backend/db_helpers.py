# ==============================
# Third-Party Imports
# ==============================
import streamlit as st
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import Session
import json
import random
import string
import uuid
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional, Dict, List, Any
from sqlalchemy import func
from backend.security import hash_password, verify_password
from backend.models import AntiCheatLog,SubjectiveGrade

# ==============================
# Local Imports
# ==============================
from backend.database import get_session
from backend.models import (
    Admin,

    Retake,
    TestResult,
    ArchivedQuestion,
    TestDuration,
    StudentProgress,
    School,Subject,
    ObjectiveQuestion,
    StudentAnswer


)

# ==============================
# Admin CRUD (Multi-Tenant)
# ==============================
def set_admin(username: str, password: str, role: str = "admin", school_id: int | None = None) -> bool:
    db = get_session()
    try:
        username = username.strip()

        if role != "super_admin" and not school_id:
            raise ValueError("Non-super-admin must be assigned to a school.")

        hashed_pw = hash_password(password)

        # Match by username + school (important)
        query = db.query(Admin).filter(Admin.username.ilike(username))

        if role != "super_admin":
            query = query.filter(Admin.school_id == school_id)
        else:
            query = query.filter(Admin.school_id.is_(None))

        admin = query.first()

        if admin:
            admin.password_hash = hashed_pw
            admin.role = role
            admin.school_id = None if role == "super_admin" else school_id
        else:
            admin = Admin(
                username=username,
                password_hash=hashed_pw,
                role=role,
                school_id=None if role == "super_admin" else school_id
            )
            db.add(admin)

        db.commit()
        return True

    except Exception as e:
        db.rollback()
        print(f"[set_admin ERROR] {e}")
        return False
    finally:
        db.close()



# =====================================================
#
# =====================================================
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


# =====================================================
#
# =====================================================
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



# =====================================================
#
# =====================================================
def verify_admin(username: str, password: str, school_id: int | None = None) -> Admin | None:
    db = get_session()
    try:
        username = username.strip()

        query = db.query(Admin).filter(Admin.username.ilike(username))

        if school_id is not None:
            query = query.filter(Admin.school_id == school_id)
        else:
            query = query.filter(Admin.school_id.is_(None))

        admin = query.first()

        if admin and verify_password(password, admin.password_hash):
            return admin

        return None
    finally:
        db.close()



# =====================================================
#
# =====================================================
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




# =====================================================
#
# =====================================================
def delete_admin(admin_id: int) -> bool:
    """
    Delete an admin by ID.
    Returns True if deletion was successful, False otherwise.
    """
    db = get_session()
    try:
        admin = db.query(Admin).filter_by(id=admin_id).first()
        if not admin:
            return False  # Admin not found

        # Optional: prevent deleting super_admin
        if admin.role == "super_admin":
            raise ValueError("Super admin accounts cannot be deleted.")

        db.delete(admin)
        db.commit()
        return True
    except Exception as e:
        print(f"Error deleting admin: {e}")
        db.rollback()
        return False
    finally:
        db.close()

# =====================================================
#
# =====================================================
def is_answered(a):
    if a is None:
        return False
    if isinstance(a, str):
        a = a.strip()
        return a != "" and a != "Choose answer"
    return True



# =====================================================
#
# =====================================================
def parse_json_field(data):
    if not data:
        return []

    if isinstance(data, list):
        return data

    if isinstance(data, str):

        try:
            return json.loads(data)

        except:
            return []

    return []





def field(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)

    return getattr(obj, name, default)



# =====================================================
#
# =====================================================
def ensure_super_admin_exists(force_reset_password=False):
    db = get_session()
    try:
        admin = db.query(Admin).filter_by(username="super_admin").first()

        if not admin:
            db.add(
                Admin(
                    username="super_admin",
                    password_hash=hash_password("1234"),
                    role="super_admin"
                )
            )
            db.commit()
            print("✅ Created super_admin (password=1234)")

        else:
            # ✅ Ensure role
            if admin.role != "super_admin":
                admin.role = "super_admin"

            # 🔥 NEW: Force reset password if needed
            if force_reset_password:
                admin.password_hash = hash_password("1234")
                print("🔑 Password reset to 1234")

            db.commit()

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")

    finally:
        db.close()


# =====================================
# SAFE FALLBACK SESSION (DOES NOT CRASH)
# =====================================
class SafeNullSession:
    """A dummy session object used when the DB connection fails.
    Every method returns itself or harmless defaults so calls never crash.
    """
    def commit(self): pass
    def rollback(self): pass
    def close(self): pass
    def add(self, *a, **k): pass
    def delete(self, *a, **k): pass

    # SQLAlchemy-like chainable methods
    def query(self, *a, **k): return self
    def filter(self, *a, **k): return self
    def filter_by(self, *a, **k): return self
    def order_by(self, *a, **k): return self

    # Safe output methods
    def all(self): return []
    def first(self): return None
    def count(self): return 0


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
            db = get_session()

            try:

                sa = db.query(Admin).filter(
                    Admin.username.ilike(super_admin_user.strip())
                ).first()

                if sa:
                    password_ok = verify_password(
                        super_admin_pass,
                        sa.password_hash
                    )
                if sa and sa.role == "super_admin" and verify_password(super_admin_pass, sa.password_hash):
                    st.session_state.super_admin_authenticated = True
                    st.success("✅ Super Admin authenticated!")
                else:
                    st.error("❌ Invalid Super Admin credentials")

            finally:
                db.close()

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

            # ✅ STEP 1: Find user ONLY by username
            admin = db.query(Admin).filter(
                Admin.username.ilike(username.strip())
            ).first()

            if not admin:
                st.warning("❌ Username not found.")
                return False

            # ✅ STEP 2: Verify password
            if not verify_password(password, admin.password_hash):
                st.warning("❌ Invalid password.")
                return False

            # ✅ STEP 3: Handle Super Admin (NO school restriction)
            if admin.role == "super_admin":
                st.session_state.update({
                    "admin_logged_in": True,
                    "admin_username": admin.username,
                    "admin_role": "super_admin",
                    "admin_school_id": None,
                    "school_id": None,
                    "current_school_id": None,
                    "school_name": "Global",
                })

                st.sidebar.success(f"✅ Super Admin logged in")
                st.rerun()

            # ✅ STEP 4: Handle School Admin (WITH restriction)
            if tenant_school_id and admin.school_id != tenant_school_id:
                st.warning("❌ Unauthorized for this school.")
                return False
            st.session_state.update({
                "admin_logged_in": True,
                "admin_username": admin.username,
                "admin_role": "admin",
                "admin_school_id": admin.school_id,
                "school_id": admin.school_id,
                "current_school_id": admin.school_id,
                "school_name": admin.school.name if admin.school else "Unknown",
            })

            st.sidebar.success(f"✅ Logged in as {admin.username}")
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

    # ✅ Ensures function always returns a boolean
    return False



# -----------------------------
# Student Management
# -----------------------------
def generate_access_code(length=6, db=None, school_id=None, max_attempts=10):
    """Generate a unique access code per school (safe + bounded)."""

    if school_id is None:
        raise ValueError("school_id is required for access code generation")

    close_db = False
    if db is None:
        db = get_session()
        close_db = True

    try:
        for _ in range(max_attempts):
            code = ''.join(
                random.choices(string.ascii_uppercase + string.digits, k=length)
            )

            exists = db.query(Student).filter(
                Student.access_code == code,
                Student.school_id == school_id
            ).first()

            if not exists:
                return code

        raise Exception("Failed to generate unique access code")

    finally:
        if close_db:
            db.close()



# =====================================================
#
# =====================================================
def generate_unique_id(db=None, max_attempts=10):
    """Generate globally unique short ID (no school scope needed)."""

    close_db = False
    if db is None:
        db = get_session()
        close_db = True

    try:
        for _ in range(max_attempts):
            unique_id = str(uuid.uuid4())[:8]

            exists = db.query(Student).filter(
                Student.unique_id == unique_id
            ).first()

            if not exists:
                return unique_id

        raise Exception("Failed to generate unique student ID")

    finally:
        if close_db:
            db.close()



# =====================================================
#
# =====================================================
from sqlalchemy.exc import IntegrityError
def add_student_db(name, class_id, school_id, db=None):
    """
    Add a single student.
    - Reuses existing student (same name + class + school)
    - Generates safe access_code (per school)
    - Generates global unique_id
    - Handles race conditions with retry
    """

    close_db = False
    if db is None:
        db = get_session()
        close_db = True

    try:
        name = str(name).strip()

        if not name or not class_id:
            raise ValueError("Student name and class are required.")

        # ----------------------------------
        # 🔒 CHECK EXISTING STUDENT
        # ----------------------------------
        existing = (
            db.query(Student)
            .filter(
                func.lower(Student.name) == name.lower(),
                Student.class_id == class_id,
                Student.school_id == school_id
            )
            .first()
        )

        if existing:
            return {
                "id": existing.id,
                "unique_id": existing.unique_id,
                "name": existing.name,
                "class_id": existing.class_id,
                "access_code": existing.access_code,
                "status": "existing"
            }

        # ----------------------------------
        # 🆕 CREATE NEW (WITH RETRY)
        # ----------------------------------
        for _ in range(5):
            try:
                access_code = generate_access_code(db=db, school_id=school_id)
                unique_id = generate_unique_id(db=db)  # ✅ global

                student = Student(
                    unique_id=unique_id,
                    name=name,
                    class_id=class_id,
                    access_code=access_code,
                    can_retake=True,
                    submitted=False,
                    school_id=school_id
                )

                db.add(student)
                db.commit()
                db.refresh(student)

                return {
                    "id": student.id,
                    "unique_id": student.unique_id,
                    "name": student.name,
                    "class_id": student.class_id,
                    "access_code": student.access_code,
                    "status": "new"
                }

            except IntegrityError:
                db.rollback()  # 🔁 retry on collision

        raise Exception("Failed to create student after multiple retries.")

    except Exception as e:
        db.rollback()
        print("❌ Error adding student:", e)
        raise

    finally:
        if close_db:
            db.close()





# =====================================================
#
# =====================================================
from sqlalchemy.exc import IntegrityError
def bulk_add_students_db(students_list, school_id, db=None):
    """
    Bulk add students safely.
    - Reuses existing students
    - Handles collisions with retry
    - Prevents full batch failure
    """

    close_db = False
    if db is None:
        db = get_session()
        close_db = True

    added_students = []
    summary = {"new": 0, "reused": 0, "failed": 0}

    try:
        for entry in students_list:

            # ----------------------------
            # Validate entry
            # ----------------------------
            if not isinstance(entry, (list, tuple)) or len(entry) != 2:
                print(f"⚠️ Skipping invalid entry: {entry}")
                summary["failed"] += 1
                continue

            name, class_id = entry
            name = str(name).strip()

            if not name or not class_id:
                summary["failed"] += 1
                continue

            # ----------------------------
            # CHECK EXISTING
            # ----------------------------
            existing = (
                db.query(Student)
                .filter(
                    func.lower(Student.name) == name.lower(),
                    Student.class_id == class_id,
                    Student.school_id == school_id
                )
                .first()
            )

            if existing:
                added_students.append({
                    "id": existing.id,
                    "unique_id": existing.unique_id,
                    "name": existing.name,
                    "class_id": existing.class_id,
                    "access_code": existing.access_code,
                    "status": "reused"
                })
                summary["reused"] += 1
                continue

            # ----------------------------
            # CREATE NEW (WITH RETRY)
            # ----------------------------
            created = False

            for _ in range(5):
                try:
                    access_code = generate_access_code(db=db, school_id=school_id)
                    unique_id = generate_unique_id(db=db)

                    student = Student(
                        unique_id=unique_id,
                        name=name,
                        class_id=class_id,
                        access_code=access_code,
                        can_retake=True,
                        submitted=False,
                        school_id=school_id
                    )

                    db.add(student)
                    db.flush()  # ✅ keep for bulk performance

                    added_students.append({
                        "id": student.id,
                        "unique_id": student.unique_id,
                        "name": student.name,
                        "class_id": student.class_id,
                        "access_code": student.access_code,
                        "status": "new"
                    })

                    summary["new"] += 1
                    created = True
                    break

                except IntegrityError:
                    db.rollback()  # 🔁 retry

            if not created:
                print(f"❌ Failed to create student: {name}")
                summary["failed"] += 1

        db.commit()

        return {
            "students": added_students,
            "summary": summary
        }

    except Exception as e:
        db.rollback()
        print("❌ Bulk add failed:", e)
        raise

    finally:
        if close_db:
            db.close()



# =====================================================
#
# =====================================================
def get_student_by_access_code(access_code: str, school_id: int):
    """
    Fetch a student by access code (STRICT school-scoped).
    """

    if not access_code or not school_id:
        return None

    db = get_session()
    try:
        return db.query(Student).filter(
            Student.access_code == access_code.strip().upper(),
            Student.school_id == school_id
        ).first()
    finally:
        db.close()





# ==============================
# RAW DB FUNCTION (NO CACHE)
# ==============================
def _get_users_db(school_id=None):
    db = get_session()

    if not db:
        return {}

    try:
        query = db.query(Student)

        if school_id is not None:
            query = query.filter(Student.school_id == school_id)

        students = query.all()

        return {
            (s.access_code or "").strip().upper(): {
                "id": s.id,
                "name": s.name,
                "class_id": s.class_id,
                "unique_id": s.unique_id,
                "access_code": (s.access_code or "").strip().upper(),
                "submitted": bool(s.submitted),
                "school_id": s.school_id,
                "can_retake": bool(s.can_retake),
            }
            for s in students
        }

    except Exception as e:
        print("⚠️ get_users failed:", e)
        return {}

    finally:
        db.close()


# ==============================
# CACHED VERSION (UI SAFE)
# ==============================
@st.cache_data(ttl=60, show_spinner=False)
def get_users(school_id=None):
    return _get_users_db(school_id)



# =====================================================
#
# =====================================================
def add_question_db(
    class_id: int,
    subject_id: int,
    question_text: str,
    options: list[str],
    correct_answer: str,
    school_id: int,
):


    if not class_id:
        raise ValueError("class_id is required")

    if not subject_id:
        raise ValueError("subject_id is required")

    options = [
        o.strip() for o in options
        if isinstance(o, str) and o.strip()
    ]

    if len(options) < 2:
        raise ValueError("Objective question must have at least 2 options")

    db = get_session()

    try:
        subject_obj = (
            db.query(Subject)
            .filter(
                Subject.id == subject_id,
                Subject.class_id == class_id,
                Subject.school_id == school_id,
            )
            .first()
        )

        if not subject_obj:
            raise ValueError("Subject does not belong to this class or school")

        question = ObjectiveQuestion(
            class_id=class_id,
            subject_id=subject_id,
            question_text=question_text.strip(),
            options=options,
            answer=correct_answer.strip(),
            school_id=school_id,
            archived=False,
        )

        db.add(question)
        db.commit()

    finally:
        db.close()




# =====================================================
#
# =====================================================
def get_current_school_id() -> int:
    school_id = st.session_state.get("school_id")

    if not school_id:
        st.error("🚫 No active school selected.")
        st.stop()

    school_id = int(school_id)

    db = get_session()
    exists = db.query(School.id).filter_by(id=school_id).first()
    db.close()

    if not exists:
        st.session_state["school_id"] = None
        st.error("🚫 Selected school no longer exists.")
        st.stop()

    return school_id



# =====================================================
# 📤 HANDLE OBJECTIVE QUESTION UPLOAD
# =====================================================
def handle_uploaded_questions(
    class_id: int,
    subject_id: int,
    valid_questions: list,
    school_id: int | None = None,
):
    """
    Upload and replace objective questions safely
    with duplicate detection and optimized inserts.
    """

    import re

    if not class_id or not subject_id:

        return {
            "success": False,
            "error": "class_id and subject_id are required"
        }

    db = get_session()

    try:

        # ------------------------------------------------
        # 🏫 Detect school_id
        # ------------------------------------------------
        if school_id is None:
            school_id = get_current_school_id()

        if not school_id:

            return {
                "success": False,
                "error": "School ID not found"
            }

        # ------------------------------------------------
        # ✅ Verify subject ownership
        # ------------------------------------------------
        subject_exists = (
            db.query(Subject.id)
            .filter(
                Subject.id == subject_id,
                Subject.class_id == class_id,
                Subject.school_id == school_id,
            )
            .first()
        )

        if not subject_exists:

            return {
                "success": False,
                "error": (
                    "Subject does not belong "
                    "to this class or school"
                ),
            }

        # ------------------------------------------------
        # 🧹 CLEAN + DEDUPLICATE
        # ------------------------------------------------
        cleaned_questions = []

        seen_questions = set()

        duplicate_count = 0
        skipped_invalid = 0

        # ------------------------------------------------
        # 🔤 NORMALIZER
        # ------------------------------------------------
        def normalize_text(text: str):

            text = text.lower().strip()

            # remove punctuation
            text = re.sub(r"[^\w\s]", "", text)

            # remove extra spaces
            text = re.sub(r"\s+", " ", text)

            return text

        # ------------------------------------------------
        # PROCESS QUESTIONS
        # ------------------------------------------------
        for q in valid_questions:

            question_text = str(
                q.get("question", "")
            ).strip()

            options = q.get("options", [])

            answer = str(
                q.get("answer", "")
            ).strip()

            # ----------------------------
            # 🚫 Empty question
            # ----------------------------
            if not question_text:
                skipped_invalid += 1
                continue

            # ----------------------------
            # 🔍 Duplicate detection
            # ----------------------------
            normalized = normalize_text(
                question_text
            )

            if normalized in seen_questions:
                duplicate_count += 1
                continue

            seen_questions.add(normalized)

            # ----------------------------
            # 🧹 Clean options
            # ----------------------------
            clean_options = [

                str(opt).strip()

                for opt in options

                if str(opt).strip()
            ]

            # remove duplicates while preserving order
            clean_options = list(
                dict.fromkeys(clean_options)
            )

            # ----------------------------
            # 🚫 Need minimum options
            # ----------------------------
            if len(clean_options) < 2:
                skipped_invalid += 1
                continue

            # ----------------------------
            # 🚫 Invalid answer
            # ----------------------------
            if answer and answer not in clean_options:

                skipped_invalid += 1
                continue

            # ----------------------------
            # ✅ Append clean payload
            # ----------------------------
            cleaned_questions.append({

                "school_id": school_id,

                "class_id": class_id,

                "subject_id": subject_id,

                "question_text": question_text,

                "options": clean_options,

                "correct_answer": answer,
            })

        # ------------------------------------------------
        # 🚫 Prevent wipe
        # ------------------------------------------------
        if not cleaned_questions:

            return {
                "success": False,
                "error": "No valid questions found in upload",
            }

        # ------------------------------------------------
        # 🗑️ Delete old questions
        # ------------------------------------------------
        deleted_count = (
            db.query(ObjectiveQuestion)
            .filter(
                ObjectiveQuestion.class_id == class_id,
                ObjectiveQuestion.subject_id == subject_id,
                ObjectiveQuestion.school_id == school_id,
            )
            .delete(synchronize_session=False)
        )

        # ------------------------------------------------
        # ⚡ FAST BULK INSERT
        # ------------------------------------------------
        db.bulk_insert_mappings(
            ObjectiveQuestion,
            cleaned_questions
        )

        db.commit()

        # ------------------------------------------------
        # 🧠 CLEAR CACHE
        # ------------------------------------------------
        for fn in [
            "load_questions",
            "load_subjects",
        ]:

            try:
                globals()[fn].clear()
            except Exception:
                pass

        return {

            "success": True,

            "deleted": deleted_count,

            "inserted": len(cleaned_questions),

            "duplicates_skipped": duplicate_count,

            "invalid_skipped": skipped_invalid,
        }

    except Exception as e:

        db.rollback()

        return {
            "success": False,
            "error": str(e)
        }

    finally:
        db.close()


# =====================================================
#
# =====================================================
def delete_student_db(student_identifier, school_id=None):
    """
    Delete a student and all related records safely.
    student_identifier: int (ID) or str (access_code)
    school_id: optional, limits deletion to a specific school
    """
    db = get_session()
    try:
        print("🔍 DELETE INPUT:", student_identifier, type(student_identifier))
        print("🔍 SCHOOL FILTER:", school_id)

        # Start query for Student
        query = db.query(Student)
        if school_id:
            query = query.filter(Student.school_id == school_id)

        # Identify student by ID or access_code
        if isinstance(student_identifier, int):
            student = query.filter(Student.id == student_identifier).first()
        else:
            student = query.filter(
                Student.access_code == str(student_identifier).strip()
            ).first()

        if not student:
            print(f"⚠️ No student found for identifier: {student_identifier}")
            return False

        # 🔥 Delete the student (cascade will handle related tables)
        db.delete(student)
        db.commit()

        print(f"✅ Deleted student and all related records: {student.name} ({student.access_code})")
        return True

    except Exception as e:
        db.rollback()
        print("❌ Error deleting student:", e)
        return False

    finally:
        db.close()



# -----------------------------
# Submissions (Updated)
# -----------------------------
def add_submission_db(
    student_id: int,
    subject_id: int,
    submissions: list,
    score: int,
    total: int,
    percentage: float,
    school_id=None,
    class_id=None,
    test_type="objective"
):
    """
    Save submissions using StudentProgress + StudentAnswer + TestResult.
    """

    db = get_session()
    try:
        student = db.query(Student).filter_by(id=student_id).first()
        if not student:
            raise ValueError("Invalid student ID")

        # Resolve tenant context
        school_id = school_id or student.school_id
        class_id = class_id or student.class_id

        if not class_id:
            raise ValueError("Class ID is required")

        # -----------------------------------
        # 1️⃣ Get or Create StudentProgress
        # -----------------------------------
        progress = db.query(StudentProgress).filter_by(
            student_id=student_id,
            subject_id=subject_id,
            school_id=school_id,
            class_id=class_id,
            test_type=test_type
        ).first()

        if not progress:
            raise ValueError("StudentProgress not found. Test session missing.")

        # Mark as submitted
        progress.submitted = True
        progress.score = score
        progress.review_status = "pending" if test_type == "subjective" else "completed"

        # -----------------------------------
        # 2️⃣ Save Answers
        # -----------------------------------
        for sub in submissions:
            db.add(StudentAnswer(
                progress_id=progress.id,
                question_id=sub.get("question_id"),
                answer=sub.get("selected")
            ))

        # -----------------------------------
        # 3️⃣ Save Test Result Summary
        # -----------------------------------
        db.add(TestResult(
            student_id=student_id,
            class_id=class_id,
            subject_id=subject_id,  # ✅ CORRECT
            score=score,
            total=total,
            percentage=percentage
        ))

        db.commit()

        print(f"✅ Saved {len(submissions)}/{total} answers for {student.name} ({score} score)")

    except Exception as e:
        db.rollback()
        print(f"❌ Failed to save submissions: {e}")
        raise

    finally:
        db.close()


# -----------------------------
# Submissions (Updated)
# -----------------------------
def get_all_submissions_db(school_id=None):
    """
    Return all submitted test sessions (StudentProgress).
    Optional school_id filters by school.
    """
    db = get_session()
    try:
        query = db.query(StudentProgress).filter(
            StudentProgress.submitted == True
        )

        if school_id:
            query = query.filter(StudentProgress.school_id == school_id)

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

    correct = 0
    wrong = 0
    details = []

    for q in questions:
        qid = q.get("id")

        correct_answer = str(q.get("answer", "")).strip().lower()
        user_answer = str(answers_dict.get(qid, "")).strip().lower()

        if user_answer == correct_answer and user_answer != "":
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

    total = len(questions)

    return {
        "correct": correct,
        "wrong": wrong,
        "total": total,
        "score_percent": round((correct / total) * 100, 2) if total else 0,
        "details": details
    }




# =====================================================
#
# =====================================================
def show_question_tracker(questions, current_q, answers):
    """Streamlit UI tracker: clickable grid navigator only."""

    total = len(questions)
    marked = set(st.session_state.get("marked_for_review", []))

    # Stable unique test ID
    if "test_id" not in st.session_state:
        st.session_state.test_id = str(uuid.uuid4())
    test_id = st.session_state.test_id

    student_id = st.session_state.get("student", {}).get("id", "anon")
    subject = st.session_state.get("subject", "unknown")

    with st.expander("🔽 Question Navigator", expanded=False):

        # ✅ Build answer lookup once
        if not isinstance(answers, dict):
            answers = {}

        answer_lookup = answers

        # DEBUG
        ids = [str(q["id"]) for q in questions]

        duplicates = [
            x
            for x in ids
            if ids.count(x) > 1
        ]

        st.write("QUESTION IDS:", ids)
        st.write("DUPLICATES:", set(duplicates))

        for row_start in range(0, total, 10):
            cols = st.columns(10)

            ...
            for i in range(row_start, min(row_start + 10, total)):

                question = questions[i]
                qid = str(question["id"])

                if i == 0:
                    st.write("TRACKER SAMPLE INDEX:", i)
                    st.write("TRACKER SAMPLE QID:", qid)
                    st.write("SESSION ANSWERS SAMPLE:", st.session_state.answers.get(qid, "MISSING"))

                answer = st.session_state.answers.get(qid, "")

                if qid in marked:
                    color = "#FFA500"  # marked

                elif str(answer).strip():
                    color = "#2ECC71"  # answered

                else:
                    color = "#E74C3C"  # unanswered

                qid = str(question["id"])
                btn_key = f"jump_{student_id}_{qid}"

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

                if cols[i % 10].button(" ", key=btn_key):
                    st.session_state.current_q = i
                    st.rerun()

                cols[i % 10].markdown(label_html, unsafe_allow_html=True)

        st.markdown(
            "<p style='font-size:13px;'>🟩 Answered | 🟥 Unanswered | 🟨 Marked for review</p>",
            unsafe_allow_html=True
        )

# ==============================
# 🕒 Test Duration Helpers (ID-ONLY)
# ==============================

def set_test_duration(
    school_id: int,
    class_id: int,
    subject_id: int,
    duration_minutes: int
):
    """
    Save or update test duration for a given school, class, and subject.
    Duration is stored in SECONDS.
    """

    if not all([school_id, class_id, subject_id, duration_minutes]):
        print("⚠️ Missing required IDs in set_test_duration().")
        return

    db = get_session()

    try:
        from backend.models import TestDuration

        duration_seconds = duration_minutes * 60

        record = db.query(TestDuration).filter_by(
            school_id=school_id,
            class_id=class_id,
            subject_id=subject_id
        ).first()

        if record:
            record.duration = duration_seconds
        else:
            db.add(TestDuration(
                school_id=school_id,
                class_id=class_id,
                subject_id=subject_id,
                duration=duration_seconds
            ))

        db.commit()
        print(
            f"✅ Duration saved: {duration_minutes} min "
            f"(school={school_id}, class={class_id}, subject={subject_id})"
        )

    except Exception as e:
        db.rollback()
        print(f"❌ set_test_duration() error: {e}")
        raise

    finally:
        db.close()


# =====================================================
#
# =====================================================
def get_test_duration(class_id: int, subject_id: int, school_id: int):
    """
    Returns duration IN MINUTES.
    DB stores duration in SECONDS.
    """
    if not (class_id and subject_id and school_id):
        return None

    db = get_session()
    try:
        record = (
            db.query(TestDuration)
            .filter(
                TestDuration.class_id == class_id,
                TestDuration.subject_id == subject_id,
                TestDuration.school_id == school_id,
            )
            .first()
        )

        if record and record.duration and record.duration > 0:
            duration_minutes = record.duration // 60
            return max(1, int(duration_minutes))

        return None

    finally:
        db.close()




# =====================================================
#
# =====================================================
def clear_questions_db(school_id: int | None = None):
    """
    Delete objective questions safely.

    - school_id provided → delete only that school's questions
    - school_id None → requires explicit super_admin call
    """
    db = get_session()
    try:
        query = db.query(ObjectiveQuestion)

        if school_id is not None:
            query = query.filter(ObjectiveQuestion.school_id == school_id)
        else:
            # Hard safety guard
            raise RuntimeError("❌ Global delete blocked. Provide school_id.")

        # Load IDs first (safer for relational cleanup)
        question_ids = [q.id for q in query.all()]

        if not question_ids:
            return 0

        # Optional safety: delete submissions first if relationship exists
        # db.query(Submission).filter(Submission.question_id.in_(question_ids)).delete(synchronize_session=False)

        deleted_count = (
            db.query(ObjectiveQuestion)
            .filter(ObjectiveQuestion.id.in_(question_ids))
            .delete(synchronize_session=False)
        )

        db.commit()
        return deleted_count

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()



# =====================================================
#
# =====================================================
@st.cache_data(ttl=60)
def load_subjects(
    school_id: int | None = None,
    class_id: int | None = None
):
    db = get_session()

    try:

        query = db.query(Subject)

        if school_id is not None:
            query = query.filter(
                Subject.school_id == school_id
            )

        if class_id is not None:
            query = query.filter(
                Subject.class_id == class_id
            )

        subjects = (
            query
            .order_by(Subject.name.asc())
            .all()
        )

        # ✅ Convert ORM objects to safe serializable data
        return [
            {
                "id": s.id,
                "name": s.name,
                "class_id": s.class_id,
                "school_id": s.school_id,
            }
            for s in subjects
        ]

    finally:
        db.close()



# =====================================================
#
# =====================================================
def delete_subject(subject_id: int, class_id: int, school_id: int) -> bool:
    db = get_session()

    try:
        # 1️⃣ Hard-delete dependent test durations FIRST
        db.query(TestDuration).filter(
            TestDuration.subject_id == subject_id,
            TestDuration.class_id == class_id,
            TestDuration.school_id == school_id,
        ).delete(synchronize_session=False)

        # 2️⃣ Ensure no questions still reference this subject
        linked_questions = db.query(ObjectiveQuestion).filter(
            ObjectiveQuestion.subject_id == subject_id,
            ObjectiveQuestion.class_id == class_id,
            ObjectiveQuestion.school_id == school_id,
        ).count()

        if linked_questions > 0:
            db.rollback()
            return False

        # 3️⃣ Delete the subject by ID (NO ORM object delete)
        deleted = db.query(Subject).filter(
            Subject.id == subject_id,
            Subject.class_id == class_id,
            Subject.school_id == school_id,
        ).delete(synchronize_session=False)

        db.commit()
        return deleted > 0

    except Exception:
        db.rollback()
        raise

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



# ==============================
# 👨‍🎓
# ==============================
def update_student_db(
    student_id: int,
    new_name: str,
    new_class_id: int,
    school_id: int | None = None,
    db=None
):
    """
    PURE ID-BASED student update.
    """
    close_db = False
    if db is None:
        db = get_session()
        close_db = True

    try:
        student_id = int(student_id)
        new_class_id = int(new_class_id)

        query = db.query(Student).filter(Student.id == student_id)

        if school_id is not None:
            query = query.filter(Student.school_id == school_id)

        student = query.first()

        if not student:
            raise ValueError("Student not found.")

        student.name = new_name.strip()
        student.class_id = new_class_id

        db.commit()

    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Error updating student: {e}")

    finally:
        if close_db:
            db.close()


# ==============================
# 📝 Submission Helpers (Updated)
# ==============================
def clear_submissions_db(school_id=None):
    """
    Delete submissions (StudentProgress + StudentAnswer + TestResult).

    - If school_id is provided → delete only that school's data
    - If None → delete everything (super admin)
    """
    db = get_session()
    try:
        # -------------------------
        # Build base queries
        # -------------------------
        progress_query = db.query(StudentProgress)
        answer_query = db.query(StudentAnswer).join(StudentProgress)
        result_query = db.query(TestResult)

        if school_id is not None:
            progress_query = progress_query.filter(StudentProgress.school_id == school_id)
            answer_query = answer_query.filter(StudentProgress.school_id == school_id)
            result_query = result_query.filter(TestResult.school_id == school_id)

        # -------------------------
        # Delete in correct order
        # -------------------------
        deleted_answers = answer_query.delete(synchronize_session=False)
        deleted_progress = progress_query.delete(synchronize_session=False)
        deleted_results = result_query.delete(synchronize_session=False)

        db.commit()

        return {
            "answers_deleted": deleted_answers,
            "progress_deleted": deleted_progress,
            "results_deleted": deleted_results
        }

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




# =====================================================
#
# =====================================================
def archive_question(session: Session, question_id: int) -> bool:
    """
    PURE ID-BASED.
    Move an objective question from ObjectiveQuestion → ArchivedQuestion.
    """
    try:
        # Lookup the objective question
        q = session.get(ObjectiveQuestion, int(question_id))
        if not q:
            return False

        # Create an archived record
        archived = ArchivedQuestion(
            question_id=q.id,          # optional reference if you keep it
            class_id=q.class_id,
            subject_id=q.subject_id,
            question_text=q.question_text,
            options=q.options,
            correct_answer=q.correct_answer,
            created_by=getattr(q, "created_by", None),
            created_at=getattr(q, "created_at", None),
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





# =====================================================
#
# =====================================================
from datetime import datetime
def restore_question(session: Session, archived_id: int) -> bool:
    try:
        aq = session.get(ArchivedQuestion, archived_id)
        if not aq:
            return False

        restored = ObjectiveQuestion()

        restored.class_id = aq.class_id
        restored.subject_id = aq.subject_id
        restored.school_id = aq.school_id
        restored.question_text = aq.question_text
        restored.options = aq.options
        restored.correct_answer = aq.correct_answer
        restored.created_at = getattr(aq, "created_at", datetime.utcnow())

        # optional fields
        if hasattr(aq, "created_by"):
            restored.created_by = aq.created_by

        session.add(restored)
        session.delete(aq)
        session.commit()
        return True

    except Exception as e:
        session.rollback()
        print(f"❌ Restore error: {e}")
        return False



# =====================================================
#
# =====================================================
def load_archived_questions(db, school_id: int):
    return (
        db.query(
            ArchivedQuestion.id,
            ArchivedQuestion.class_id,
            ArchivedQuestion.subject_id,
            ArchivedQuestion.question_text,
            Class.name.label("class_name"),
            Subject.name.label("subject_name"),
        )
        .join(Class, ArchivedQuestion.class_id == Class.id)
        .join(Subject, ArchivedQuestion.subject_id == Subject.id)
        .filter(ArchivedQuestion.school_id == school_id)
        .order_by(ArchivedQuestion.archived_at.desc())
        .all()
    )


# =====================================================
#
# =====================================================
def get_archived_questions(
    session: Session,
    school_id: Optional[int] = None,
    class_id: Optional[int] = None,
    subject_id: Optional[int] = None,
) -> list[ArchivedQuestion]:
    """
    Fetch archived questions using ID filters.
    """

    query = session.query(ArchivedQuestion)

    if school_id is not None:
        query = query.filter(
            ArchivedQuestion.school_id == school_id
        )

    if class_id is not None:
        query = query.filter(
            ArchivedQuestion.class_id == class_id
        )

    if subject_id is not None:
        query = query.filter(
            ArchivedQuestion.subject_id == subject_id
        )

    results = query.order_by(
        ArchivedQuestion.archived_at.desc()
    ).all()

    return list(results)


# =====================================================
#
# =====================================================
def reset_test(student_id: int):

    db = get_session()

    try:

        student = db.query(Student).filter_by(
            id=student_id
        ).first()

        if not student:
            return False

        # -------------------------
        # Delete grades
        # -------------------------
        db.query(SubjectiveGrade).filter(
            SubjectiveGrade.student_id == student_id
        ).delete(synchronize_session=False)

        # -------------------------
        # Delete results
        # -------------------------
        db.query(TestResult).filter(
            TestResult.student_id == student_id
        ).delete(synchronize_session=False)

        # -------------------------
        # Delete answers
        # -------------------------
        progress_ids = [
            p.id
            for p in db.query(StudentProgress.id)
            .filter(StudentProgress.student_id == student_id)
            .all()
        ]

        if progress_ids:

            db.query(StudentAnswer).filter(
                StudentAnswer.progress_id.in_(progress_ids)
            ).delete(synchronize_session=False)

        # -------------------------
        # Delete progress
        # -------------------------
        db.query(StudentProgress).filter(
            StudentProgress.student_id == student_id
        ).delete(synchronize_session=False)

        # -------------------------
        # Reset retake
        # -------------------------
        student.can_retake = True

        db.commit()

        return True

    except Exception as e:

        db.rollback()
        print("RESET ERROR:", e)

        return False

    finally:

        db.close()




def save_progress(
        access_code,
        subject_id,
        class_id,
        answers,
        current_q,
        start_time,
        duration,
        questions,
        school_id,
        test_type,
        student_id=None,
        submitted=False,
        locked=False
):

    import json
    from datetime import datetime
    import inspect

    db = get_session()

    # =========================
    # DEBUG (safe)
    # =========================
    caller = inspect.stack()[1]
    print(f"[SAVE_PROGRESS] called from {caller.filename}:{caller.lineno}")
    print("current_q:", current_q)
    print("answers type:", type(answers))
    print("questions type:", type(questions))

    try:

        # =========================
        # NORMALIZE QUESTIONS ONLY
        # =========================
        if isinstance(questions, str):
            try:
                questions = json.loads(questions)
            except:
                questions = []

        if not isinstance(questions, list):
            questions = []

        question_list = []
        for q in questions:
            if isinstance(q, dict):
                question_list.append(q.get("id"))
            else:
                question_list.append(q)

        # =========================
        # NORMALIZE ANSWERS ONLY
        # =========================
        if isinstance(answers, str):
            try:
                answers = json.loads(answers)
            except:
                answers = {}

        if not isinstance(answers, dict):
            answers = {}

        # =========================
        # TIME SAFE
        # =========================
        if isinstance(start_time, datetime):
            safe_start_time = start_time.timestamp()
        elif isinstance(start_time, (int, float)):
            safe_start_time = float(start_time)
        else:
            safe_start_time = datetime.now().timestamp()

        safe_duration = int(duration) if duration else 0

        # =========================
        # FIND EXISTING PROGRESS
        # =========================
        existing = db.query(StudentProgress).filter_by(
            student_id=student_id,
            access_code=access_code,
            subject_id=subject_id,
            class_id=class_id,
            school_id=school_id,
            test_type=test_type
        ).one_or_none()

        # =========================
        # UPDATE
        # =========================
        if existing:

            print("✅ Updating existing progress")

            existing.answers = json.dumps(answers)
            existing.questions = json.dumps(question_list)
            existing.current_q = current_q
            existing.start_time = safe_start_time
            existing.duration = safe_duration

            if submitted:
                existing.submitted = True

            if locked:
                existing.locked = True

            if submitted and test_type == "objective":
                existing.review_status = "Auto Graded"
                existing.reviewed_at = datetime.utcnow()

        # =========================
        # CREATE NEW
        # =========================
        else:

            print("🆕 Creating new progress")

            new_record = StudentProgress(
                access_code=access_code,
                student_id=student_id,
                subject_id=subject_id,
                class_id=class_id,
                school_id=school_id,
                test_type=test_type,
                answers=json.dumps(answers),
                current_q=current_q,
                start_time=safe_start_time,
                duration=safe_duration,
                questions=json.dumps(question_list),
                submitted=bool(submitted),
                locked=bool(locked)
            )

            if submitted and test_type == "objective":
                new_record.review_status = "Auto Graded"
                new_record.reviewed_at = datetime.utcnow()

            db.add(new_record)

        db.commit()
        print("✅ SAVE SUCCESS")

    except Exception as e:
        db.rollback()
        print("❌ SAVE ERROR:", e)

    finally:
        db.close()


    # =====================================================
    #
    # =====================================================
@st.cache_data(ttl=10, show_spinner=False)
def load_progress(
    access_code: str,
    subject_id: int,
    school_id: int | None,
    test_type: str,
    class_id: int | None = None,
    student_id: int | None = None
):

    db = get_session()

    try:

        # -----------------------------------
        # ⚡ Select ONLY needed columns
        # -----------------------------------
        record = (
            db.query(
                StudentProgress.answers.label("answers"),
                StudentProgress.questions.label("questions"),
                StudentProgress.current_q.label("current_q"),
                StudentProgress.start_time.label("start_time"),
                StudentProgress.duration.label("duration"),
                StudentProgress.test_type.label("test_type"),
                StudentProgress.submitted.label("submitted"),
                StudentProgress.student_id.label("student_id"),
            )
            .filter(
                StudentProgress.student_id == student_id,
                StudentProgress.access_code == access_code,
                StudentProgress.subject_id == subject_id,
                StudentProgress.school_id == school_id,
                StudentProgress.test_type == test_type,
            )

            .filter(
                StudentProgress.class_id == class_id
                if class_id is not None
                else True
            )
            .first()
        )

        if not record:
            return None

        record = dict(record._mapping)

        # -----------------------------------
        # ✅ SAFE JSON PARSING
        # -----------------------------------
        raw_answers = record.get("answers")

        # -------------------------
        # ANSWERS (SAFE LOAD)
        # -------------------------
        if raw_answers is None or raw_answers == "":
            answers = {}

        elif isinstance(raw_answers, list):
            # old format already decoded
            answers = {
                str(a.get("question_id")): a
                for a in raw_answers
                if isinstance(a, dict) and a.get("question_id") is not None
            }


        elif isinstance(raw_answers, dict):
            answers = raw_answers

        else:
            try:
                answers = json.loads(raw_answers)

                # handle JSON list after decode
                if isinstance(answers, list):
                    answers = {
                        str(a.get("question_id")): a
                        for a in answers
                        if isinstance(a, dict)
                    }

            except Exception as e:
                st.write("❌ answers load error:", e)
                answers = {}

        # -------------------------
        # QUESTIONS (SAFE LOAD)
        # -------------------------
        raw_questions = record.get("questions")

        if not raw_questions:
            questions = []

        elif isinstance(raw_questions, list):
            questions = raw_questions

        else:
            try:
                questions = json.loads(raw_questions)
            except Exception:
                questions = []
        # -----------------------------------
        # ✅ RETURN CLEAN SERIALIZABLE DATA
        # -----------------------------------
        return {
            "answers": answers,
            "questions": questions,
            "current_q": record.get("current_q", 0) or 0,
            "start_time": record.get("start_time"),
            "duration": record.get("duration"),
            "test_type": record.get("test_type"),
            "submitted": bool(record.get("submitted")),
            "student_id": record.get("student_id"),
        }
    finally:
        db.close()




# ==============================
# ✅ Clear Progress After Submission
# ==============================
def clear_progress(
    access_code: str,
    subject_id: int,
    school_id: int | None = None,
    test_type: str | None = None
):
    db = get_session()
    try:
        query = db.query(StudentProgress).filter_by(
            access_code=access_code,
            subject_id=subject_id
        )

        if school_id is not None:
            query = query.filter(StudentProgress.school_id == school_id)

        # 🔥 ALWAYS filter by test_type
        if test_type is not None:
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




# =====================================================
#
# =====================================================
def create_default_classes_for_school(school_id):
    db = get_session()
    try:
        default_classes = ["JHS1", "JHS2", "JHS3"]

        for name in default_classes:
            normalized = name.strip().lower()

            exists = db.query(Class).filter_by(
                school_id=school_id,
                normalized_name=normalized
            ).first()

            if not exists:
                db.add(Class(
                    name=name,
                    normalized_name=normalized,
                    school_id=school_id
                ))

        db.commit()

    except Exception as e:
        db.rollback()
        print(f"❌ Failed to create default classes: {e}")
    finally:
        db.close()



# =====================================================
#
# =====================================================
def add_school(name, address=None, code=None, db=None, return_dict=False):
    """
    Add a school safely with uniqueness enforcement.
    System schools are NOT created here.
    """

    if not name or not name.strip():
        raise ValueError("School name cannot be empty.")

    close_db = False
    if db is None:
        db = get_session()
        close_db = True

    try:
        name_clean = name.strip()

        # ==============================
        # 🚫 Prevent duplicate school names
        # ==============================
        existing = db.query(School).filter(
            School.name.ilike(name_clean)
        ).first()

        if existing:
            result = {
                "exists": True,
                "id": existing.id,
                "name": existing.name,
                "code": existing.code
            }
            return result if return_dict else existing

        # ==============================
        # 🏫 Generate code safely
        # ==============================
        school_code = (code or "").strip() or generate_unique_school_code(name_clean, db)

        # ==============================
        # 🏗️ Create school (ALWAYS non-system)
        # ==============================
        school = School(
            name=name_clean,
            code=school_code,
            address=address,
            is_system=False   # 🔒 HARD RULE
        )

        db.add(school)
        db.commit()
        db.refresh(school)

        # 🔥 AUTO-SETUP (THIS FIXES YOUR WHOLE FLOW)
        create_default_classes_for_school(school.id)

        result = {
            "exists": False,
            "id": school.id,
            "name": school.name,
            "code": school.code
        }
        return result if return_dict else school

    except SQLAlchemyError as e:
        db.rollback()
        raise e

    finally:
        if close_db:
            db.close()




# =====================================================
#
# =====================================================
def get_all_schools(db=None):
    close_db = False

    if db is None:
        db = get_session()
        close_db = True

    try:
        return (
            db.query(School)
            .filter(School.is_system == False)  # ✅ now valid again
            .order_by(School.name.asc())
            .all()
        )
    finally:
        if close_db:
            db.close()



# =====================================================
#
# =====================================================
from backend.models import Student, Class
def get_students_by_school(
    school_id: int,
    class_id: int | None = None,
    db=None
):
    """
    PURE ID-BASED.
    Returns students with IDs only.
    UI resolves names separately.
    """
    if not school_id:
        raise ValueError("school_id is required")

    close_db = False
    if db is None:
        db = get_session()
        close_db = True

    try:
        query = db.query(
            Student.id,
            Student.name,
            Student.access_code,
            Student.can_retake,
            Student.submitted,
            Student.class_id,
        ).filter(Student.school_id == school_id)

        if class_id is not None:
            query = query.filter(Student.class_id == class_id)

        results = query.order_by(Student.name.asc()).all()

        return [
            {
                "id": r.id,
                "name": r.name,
                "class_id": r.class_id,
                "access_code": r.access_code,
                "can_retake": r.can_retake,
                "submitted": r.submitted,
            }
            for r in results
        ]

    except Exception as e:
        print(f"❌ Error fetching students for school {school_id}: {e}")
        return []

    finally:
        if close_db:
            db.close()

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



# =====================================================
# delete_school
# =====================================================
def delete_school(school_id, db=None):
    from sqlalchemy.exc import SQLAlchemyError

    close_db = False
    if db is None:
        db = get_session()
        close_db = True

    try:
        school_id = int(school_id)

        print(f"🧩 DB in use: {db.bind.url}")
        print(f"🗑️ Deleting school ID: {school_id}")

        school = db.query(School).filter(School.id == school_id).first()

        if not school:
            print("⚠️ School not found")
            return False

        db.delete(school)   # ✅ ORM delete
        db.commit()

        print("✅ School deleted successfully")
        return True

    except Exception as e:
        db.rollback()
        print(f"💥 Error during delete: {type(e).__name__}: {e}")
        return False

    finally:
        if close_db:
            db.close()





# =====================================================
# set retake
# =====================================================
def can_take_test(student_id, subject_id, school_id, test_type):
    """
    Return True if the student has a retake allowed.
    """
    from backend.models import Retake
    db = get_session()

    try:
        retake = (
            db.query(Retake)
            .filter_by(
                student_id=student_id,
                subject_id=subject_id,
                school_id=school_id,
                test_type=test_type,
                can_retake=True
            )
            .first()
        )
        return retake is not None

    finally:
        db.close()




# =====================================================
# set retake
# =====================================================
def decrement_retake(
    student_id: int,
    subject_id: int,
    school_id: int,
    test_type: str   # ✅ ADD THIS
):
    db = get_session()
    try:
        # Mark this test attempt as submitted
        progress = db.query(StudentProgress).filter_by(
            student_id=student_id,
            subject_id=subject_id,
            school_id=school_id,
            test_type=test_type  # ✅ ADD THIS
        ).first()

        if progress:
            progress.submitted = True

        # Disable ONLY the matching test_type retake
        retake = db.query(Retake).filter_by(
            student_id=student_id,
            subject_id=subject_id,
            school_id=school_id,
            test_type=test_type   # ✅ CRITICAL
        ).first()

        if retake:
            retake.can_retake = False

        db.commit()

    except Exception as e:
        db.rollback()
        print("❌ decrement_retake error:", e)

    finally:
        db.close()




# =====================================================
#
# =====================================================
ROLE_PERMISSIONS = {

    "super_admin": [

        "all"
    ],

    "admin": [

        "manage_students",

        "upload_questions",

        "manage_subjects",

        "delete_questions",          # ✅ ADD

        "review_subjective",         # ✅ ADD

        "view_results"               # ✅ ADD
    ],

    "teacher": [

        "upload_questions",

        "review_subjective"          # ✅ OPTIONAL
    ],
}


# =====================================================
#
# =====================================================
def has_permission(role, action):
    perms = ROLE_PERMISSIONS.get(role, [])

    if "all" in perms:
        return True

    return action in perms



# =====================================================
#
# =====================================================
def require_permission(action):
    role = st.session_state.get("admin_role") or st.session_state.get("role")

    if not role:
        st.warning("🚫 Not authenticated.")
        st.stop()

    if not has_permission(role, action):
        st.warning("🚫 You are not allowed to access this feature.")
        st.stop()




# =====================================================
#
# =====================================================
def log_violation(
    progress_id,
    student_id,
    subject_id,
    question_id,
    school_id,
    test_type,
    event_type
):
    db = get_session()

    try:

        violation = AntiCheatLog(
            progress_id=progress_id,
            student_id=student_id,
            subject_id=subject_id,
            question_id=question_id,
            school_id=school_id,
            test_type=test_type,
            event_type=event_type
        )

        db.add(violation)

        db.commit()

    except Exception as e:

        db.rollback()

        raise e

    finally:

        db.close()




# =====================================================
#
# =====================================================
def normalize_objective(raw):
    details = []

    for i, item in enumerate(raw, start=1):

        if isinstance(item, dict):

            details.append({

                "question_text":
                    item.get("question_text")
                    or item.get("question")
                    or item.get("text")
                    or f"Question {i}",

                "selected":
                    item.get("selected")
                    or item.get("answer")
                    or "—",

                "correct":
                    item.get("correct")
                    or item.get("correct_answer")
                    or "—",

                "is_correct":
                    item.get("is_correct", False)
            })

        else:

            details.append({

                "question_text":
                    f"Question {i}",

                "selected":
                    str(item),

                "correct": "—",

                "is_correct": False
            })

    return details

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



# =====================================================
#
# =====================================================
def normalize_subjective(raw):
    details = []

    for i, item in enumerate(raw, start=1):

        if isinstance(item, dict):

            details.append({

                "question":
                    item.get("question")
                    or item.get("question_text")
                    or f"Question {i}",

                "answer":
                    item.get("answer")
                    or item.get("selected")
                    or "No Answer",

                "teacher_score":
                    item.get("score")
                    or item.get("teacher_score")
                    or "-"
            })

        else:

            details.append({

                "question":
                    f"Question {i}",

                "answer":
                    str(item),

                "teacher_score": "-"
            })

    return details


