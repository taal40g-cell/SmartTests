import os
import json
import random
import string
import io
import zipfile
import streamlit as st
from fpdf import FPDF
import hashlib
from datetime import datetime
from models import Question
from sqlalchemy import select, delete
from database import SessionLocal
from models import Retake, Submission, Leaderboard
from models import Config


def init_db():
    """Create all tables in the database."""
    from models import Base
    from database import engine
    Base.metadata.create_all(bind=engine)




# =====================================================================
# UNIFIED DATA STORAGE
# =====================================================================

UNIFIED_FILE = "unified_data.json"


def _load_unified_data():
    if not os.path.exists(UNIFIED_FILE):
        return {
            "users": {},
            "retakes": {},
            "submissions": [],
            "leaderboard": [],
            "admin_config": {"duration": 30},  # legacy single-admin
            "questions": {},
            "admins": {},  # new multi-admin
            "admin_logs": []
        }
    with open(UNIFIED_FILE, "r") as f:
        return json.load(f)

def _save_unified_data(data):
    with open(UNIFIED_FILE, "w") as f:
        json.dump(data, f, indent=4)

def _hash_password(password: str) -> str:
    """Return a SHA256 hash of the password."""
    return hashlib.sha256(password.encode()).hexdigest()


def ensure_super_admin_exists():
    """
    Ensures that a super_admin account exists.
    If missing, creates one with default password '1234'.
    If exists, does nothing (keeps current password).
    """
    data = _load_unified_data()

    if "admins" not in data:
        data["admins"] = {}

    if "super_admin" not in data["admins"]:
        default_pass = "1234"
        hashed_pass = hashlib.sha256(default_pass.encode()).hexdigest()

        data["admins"]["super_admin"] = {
            "password": hashed_pass,
            "role": "super_admin"
        }
        _save_unified_data(data)
        print("✅ Created default super_admin with password '1234'")
    else:
        # Optional: make sure role is always super_admin
        data["admins"]["super_admin"]["role"] = "super_admin"
        _save_unified_data(data)



# =====================================================================
# CALL AT STARTUP
# =====================================================================
ensure_super_admin_exists()

# =====================================================================
# RETAKES
# =====================================================================
def get_retakes():
    """Return all retakes as a nested dict {access_code: {subject: allowed}}."""
    db = SessionLocal()
    try:
        rows = db.execute(select(Retake)).scalars().all()
        retakes = {}
        for r in rows:
            if r.access_code not in retakes:
                retakes[r.access_code] = {}
            retakes[r.access_code][r.subject] = r.allowed
        return retakes
    finally:
        db.close()


def set_retakes(retakes_dict):
    """Replace all retakes with the provided dict."""
    db = SessionLocal()
    try:
        db.execute(delete(Retake))  # wipe table first
        for access_code, subjects in retakes_dict.items():
            for subject, allowed in subjects.items():
                db.add(Retake(access_code=access_code, subject=subject, allowed=allowed))
        db.commit()
    finally:
        db.close()


def grant_retake(access_code: str, subject: str):
    """Allow a single student to retake a given subject test."""
    db = SessionLocal()
    try:
        subject = subject.strip().lower()
        existing = db.execute(
            select(Retake).where(Retake.access_code == access_code, Retake.subject == subject)
        ).scalar_one_or_none()
        if existing:
            existing.allowed = True
        else:
            db.add(Retake(access_code=access_code, subject=subject, allowed=True))
        db.commit()
        return True
    finally:
        db.close()



# =====================================================================
# LEADERBOARD
# =====================================================================
def get_leaderboard():
    """Return leaderboard as list of dicts (sorted by highest score first)."""
    db = SessionLocal()
    try:
        rows = db.execute(select(Leaderboard)).scalars().all()
        return [
            {
                "name": lb.name,
                "access_code": lb.access_code,
                "subject": lb.subject,
                "score": lb.score,
                "timestamp": lb.timestamp.isoformat(),
            }
            for lb in rows
        ]
    finally:
        db.close()


def set_leaderboard(lb_list):
    """Replace leaderboard completely (usually we just append)."""
    db = SessionLocal()
    try:
        db.execute(delete(Leaderboard))
        for entry in lb_list:
            db.add(
                Leaderboard(
                    name=entry["name"],
                    access_code=entry["access_code"],
                    subject=entry["subject"],
                    score=entry["score"],
                )
            )
        db.commit()
    finally:
        db.close()

# =====================================================================
# LEGACY SINGLE-ADMIN SYSTEM
# =====================================================================
# Only supports one admin. Will be removed later.
# Uses `admin_config` dictionary in unified_data.json

def get_admin_config():
    """Fetch admin config and settings (like test duration) from DB."""
    db = SessionLocal()
    try:
        rows = db.execute(select(Config)).scalars().all()
        config = {}
        for row in rows:
            try:
                config[row.key] = json.loads(row.value)
            except (json.JSONDecodeError, TypeError):
                config[row.key] = row.value  # fallback to raw string

        # Defaults
        config.setdefault("admin_username", "admin")
        config.setdefault("admin_password", "admin123")
        return config
    finally:
        db.close()


def set_admin_config(new_config: dict):
    """Insert/update admin config settings in DB."""
    db = SessionLocal()
    try:
        for key, value in new_config.items():
            serialized = json.dumps(value)
            existing = db.get(Config, key)
            if existing:
                existing.value = serialized
            else:
                db.add(Config(key=key, value=serialized))
        db.commit()
    except Exception as e:
        st.error(f"Failed to save admin config: {e}")
    finally:
        db.close()




def upload_replace_unified_json_ui():
    """UI for super admin to upload and replace unified_data.json."""
    st.subheader("📤 Replace Unified Data File")

    uploaded_file = st.file_uploader("Upload a new unified_data.json", type=["json"], key="upload_unified_json")
    if uploaded_file:
        try:
            new_data = json.load(uploaded_file)

            # Validate structure (optional, but safer)
            if not isinstance(new_data, dict) or "admins" not in new_data:
                st.error("❌ Invalid JSON file. Missing 'admins' key.")
                return

            # Backup old file first
            if os.path.exists(UNIFIED_FILE):
                os.rename(UNIFIED_FILE, UNIFIED_FILE + ".bak")
                st.info("💾 Backup created: unified_data.json.bak")

            # Save new file
            with open(UNIFIED_FILE, "w") as f:
                json.dump(new_data, f, indent=4)

            st.success("✅ unified_data.json replaced successfully. Refresh page to see changes.")
            st.balloons()
        except json.JSONDecodeError:
            st.error("❌ Failed to decode JSON. Please upload a valid JSON file.")


def change_admin_password(username, new_password):
    data = _load_unified_data()
    if "admins" not in data:
        st.error("⚠️ No admin data found.")
        return False
    if username not in data["admins"]:
        st.error(f"⚠️ Admin '{username}' not found.")
        return False

    data["admins"][username]["password"] = _hash_password(new_password)
    _save_unified_data(data)
    st.success(f"✅ Password for {username} updated successfully.")
    return True


def admin_management_ui():
    """UI for managing admins - visible only to super_admins."""
    data = _load_unified_data()
    admins = data.get("admins", {})

    if st.session_state.get("admin_role") != "super_admin":
        st.warning("⚠️ Only Super Admins can access this section.")
        return

    st.subheader("👑 Super Admin Panel - Manage Admins")

    # --- Show all admins ---
    st.write("### Current Admins")
    st.table([{"Username": u, "Role": a["role"]} for u, a in admins.items()])

    st.divider()

    # --- Add Admin Section ---
    st.write("### ➕ Add New Admin / Moderator")
    new_user = st.text_input("New Username", key="new_admin_user")
    new_pass = st.text_input("New Password", type="password", key="new_admin_pass")
    new_role = st.selectbox("Role", ["admin", "moderator", "super_admin"], key="new_admin_role")

    if st.button("Create Admin"):
        if new_user and new_pass:
            ok, msg = add_admin(new_user, new_pass, new_role, st.session_state.admin_username)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
        else:
            st.warning("⚠️ Username and password cannot be empty")

    st.divider()

    # --- Reset Password Section ---
    st.write("### 🔑 Reset Admin Password")
    reset_user = st.selectbox("Select Admin to Reset", list(admins.keys()), key="reset_user_select")
    new_pw = st.text_input("New Password", type="password", key="reset_user_pw")
    if st.button("Reset Password"):
        if reset_user:
            data["admins"][reset_user]["password"] = _hash_password(new_pw)
            _save_unified_data(data)
            log_admin_action(st.session_state.admin_username, f"Reset password for {reset_user}")
            st.success(f"✅ Password for {reset_user} reset successfully!")
            st.rerun()

    st.divider()

    # --- Remove Admin Section ---
    st.write("### ❌ Remove Admin")
    remove_user = st.selectbox("Select Admin to Remove", list(admins.keys()), key="remove_admin_select")
    if st.button("Remove Admin"):
        if remove_user:
            if remove_user == st.session_state.admin_username:
                st.error("❌ You cannot remove yourself while logged in!")
            else:
                ok, msg = remove_admin(remove_user, st.session_state.admin_username)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)


def change_admin_password_ui():
    st.subheader("🔑 Change Admin Password")
    data = _load_unified_data()
    admins = data.get("admins", {})
    current_user = st.session_state.get("admin_username", "")

    if current_user not in admins:
        st.error("⚠️ Not logged in as a valid admin.")
        return

    # Normal password change flow
    current_password = st.text_input("Current Password", type="password")
    new_password = st.text_input("New Password", type="password")
    confirm_password = st.text_input("Confirm New Password", type="password")

    if st.button("Update Password"):
        if not _verify_password(current_password, admins[current_user]["password"]):
            st.error("❌ Current password is incorrect")
        elif new_password != confirm_password:
            st.error("❌ Passwords do not match")
        else:
            admins[current_user]["password"] = _hash_password(new_password)
            data["admins"] = admins
            _save_unified_data(data)
            st.success("✅ Password updated successfully")

    # 🔒 Extra protection for super_admin reset (hidden by default)
    if current_user == "super_admin":
        with st.expander("🛡 Emergency Super Admin Password Reset", expanded=False):
            st.info("⚠️ This will reset the super_admin password without checking the old one.")
            reset_pass = st.text_input("Enter NEW password for super_admin", type="password", key="reset_pass")
            confirm_reset = st.text_input("Confirm NEW password", type="password", key="confirm_reset")

            if st.button("🔑 Force Reset Password"):
                if not reset_pass:
                    st.error("Password cannot be empty.")
                elif reset_pass != confirm_reset:
                    st.error("Passwords do not match.")
                else:
                    admins["super_admin"]["password"] = _hash_password(reset_pass)
                    data["admins"] = admins
                    _save_unified_data(data)
                    st.success("✅ Super Admin password force-reset successfully.")

# =====================================================================
# NEW MULTI-ADMIN SYSTEM
# =====================================================================
# Supports multiple admins with hashed passwords and logs
# Uses `admins` and `admin_logs` in unified_data.json



def _verify_password(password: str, hashed_password: str) -> bool:
    """Compare a raw password with the stored hashed password."""
    return _hash_password(password) == hashed_password


def add_admin(username: str, password: str, role: str = "admin", actor: str = "system"):
    data = _load_unified_data()
    if username in data.get("admins", {}):
        return False, "❌ Admin already exists"
    data.setdefault("admins", {})[username] = {"password": _hash_password(password), "role": role}
    data.setdefault("admin_logs", []).append({
        "admin": actor,
        "action": f"Created admin {username} with role {role}",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    _save_unified_data(data)
    return True, f"✅ Admin {username} created"


def remove_admin(username: str, actor: str):
    data = _load_unified_data()
    if username not in data.get("admins", {}):
        return False, "❌ Admin not found"
    del data["admins"][username]
    data.setdefault("admin_logs", []).append({
        "admin": actor,
        "action": f"Removed admin {username}",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    _save_unified_data(data)
    return True, f"✅ Admin {username} removed"


def authenticate_admin(username: str, password: str):
    data = _load_unified_data()
    admin = data.get("admins", {}).get(username)
    if not admin:
        return False, "❌ Invalid username"
    if admin["password"] != _hash_password(password):
        return False, "❌ Invalid password"
    return True, admin["role"]



def log_admin_action(admin: str, action: str):
    data = _load_unified_data()
    data.setdefault("admin_logs", []).append({
        "admin": admin,
        "action": action,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    _save_unified_data(data)
# =====================================================================
# QUESTIONS (DB-ONLY VERSION)
# =====================================================================


def delete_question_file(class_name, subject_name):
    """Delete question set for a given class+subject from DB."""
    db = SessionLocal()
    try:
        q = (
            db.query(Question)
            .filter(
                Question.class_name == class_name.strip().upper(),
                Question.subject_name == subject_name.strip().upper()
            )
            .first()
        )
        if q:
            db.delete(q)
            db.commit()
            st.success(f"✅ Questions for {class_name}-{subject_name} deleted from DB.")
        else:
            st.warning(f"No questions found for {class_name}-{subject_name}")
    except Exception as e:
        st.error(f"Error deleting questions: {e}")
    finally:
        db.close()
# =====================================================================
# UTILITIES (access codes, slips)
# =====================================================================
def generate_access_code(name, existing_codes):
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if code not in existing_codes:
            return code

def generate_access_slips(users):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        for user in users.values():
            content = (
                f"Access Code: {user['access_code']}\n"
                f"Name: {user['name']}\n"
                f"Class: {user['class']}"
            )
            zf.writestr(f"{user['access_code']}.txt", content)
    zip_buffer.seek(0)
    return zip_buffer

def generate_student_id(users_dict: dict) -> str:
    existing_ids = [u.get("student_id") for u in users_dict.values() if "student_id" in u]
    numbers = []
    for sid in existing_ids:
        try:
            numbers.append(int(sid.replace("STU", "")))
        except (ValueError, AttributeError):
            continue
    next_number = max(numbers) + 1 if numbers else 1
    return f"STU{next_number:04d}"


# =====================================================================
# USERS API
# =====================================================================


# =====================================================================
# TEST LOGIC & RESET
# =====================================================================
def reset_test(access_code: str = None):
    data = _load_unified_data()
    if access_code:
        data["submissions"] = [s for s in data.get("submissions", []) if s.get("access_code") != access_code]
        data["leaderboard"] = [s for s in data.get("leaderboard", []) if s.get("access_code") != access_code]
        users = data.get("users", {})
        if access_code in users:
            users[access_code]["submitted"] = False
        data["users"] = users
    else:
        data["submissions"] = []
        data["leaderboard"] = []
        users = data.get("users", {})
        for u in users.values():
            u["submitted"] = False
        data["users"] = users
    _save_unified_data(data)

def can_take_test(access_code: str, subject: str):
    users = get_users()
    if not users or access_code not in users:
        return False, "Invalid access code"

    subj_key = subject.strip().lower()
    submissions = get_submissions()
    submitted_subjects = {s["subject"].strip().lower() for s in submissions if s.get("access_code", "") == access_code}

    retakes = get_retakes()
    allowed_subjects = retakes.get(access_code, {})

    if subj_key in submitted_subjects and not allowed_subjects.get(subj_key, False):
        return False, f"Already submitted {subject}. Retake not allowed.❌"
    if allowed_subjects.get(subj_key, False):
        allowed_subjects[subj_key] = False
        retakes[access_code] = allowed_subjects
        set_retakes(retakes)
    return True, " Allowed to take test"

def save_submission(access_code: str, subject: str, score: float, answers: dict):
    data = _load_unified_data()
    subj_key = subject.strip().lower()
    submissions = data.get("submissions", [])
    existing = [s for s in submissions if s["access_code"] == access_code and s["subject"].strip().lower() == subj_key]
    retakes = data.get("retakes", {})
    allowed_subjects = retakes.get(access_code, {})
    if existing and not allowed_subjects.get(subj_key, False):
        return False
    if allowed_subjects.get(subj_key, False):
        allowed_subjects[subj_key] = False
        retakes[access_code] = allowed_subjects
        set_retakes(retakes)
    users = data.get("users", {})
    if access_code in users:
        users[access_code]["submitted"] = True
    data["users"] = users
    data.setdefault("submissions", []).append({
        "access_code": access_code,
        "subject": subject,
        "score": score,
        "answers": answers,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    data.setdefault("leaderboard", []).append({
        "access_code": access_code,
        "subject": subject,
        "score": score
    })
    _save_unified_data(data)
    return True

# =====================================================================
# PDF GENERATION
# =====================================================================
def generate_result_pdf(student, questions, answers, score):
    """Generate a PDF of a student's test results."""
    buffer = io.BytesIO()
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Header
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "SmarTest Results", ln=True, align="C")
    pdf.ln(10)

    # Student Info
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, f"Name: {student['name']}", ln=True)
    pdf.cell(0, 10, f"Class: {student['class']}", ln=True)
    pdf.cell(0, 10, f"Access Code: {student['access_code']}", ln=True)
    pdf.cell(0, 10, f"Score: {score}%", ln=True)
    pdf.ln(10)

    # Questions & Answers
    pdf.set_font("Arial", size=11)
    for idx, q in enumerate(questions, start=1):
        student_ans = answers.get(str(idx), "Not Answered")
        pdf.multi_cell(0, 10, f"Q{idx}: {q['question']}")
        pdf.cell(0, 10, f"Your Answer: {student_ans}", ln=True)
        pdf.cell(0, 10, f"Correct Answer: {q['answer']}", ln=True)
        pdf.ln(5)

    pdf.output(buffer)
    buffer.seek(0)
    return buffer


# =====================================================================
# QUESTION TRACKER
# =====================================================================
def show_question_tracker(questions, current_index, answers):
    """Display a progress tracker with color-coded question buttons."""
    total = len(questions)
    marked = st.session_state.get("marked_for_review", set())
    show_all = st.session_state.get("show_all_tracker", False)
    st.session_state.current_q = current_index

    st.markdown(
        '<div style="position:sticky; top:0; z-index:999; background:#f0f2f6; '
        'padding:10px; border-bottom:1px solid #ccc;">',
        unsafe_allow_html=True
    )
    st.markdown("### Progress Tracker")
    st.session_state.show_all_tracker = st.checkbox("Show all", value=show_all)

    def render_range(start, end):
        cols = st.columns(10)
        for i in range(start, end):
            if i in marked:
                color = "orange"
            elif i < len(answers) and answers[i]:
                color = "green"
            else:
                color = "red"

            label = f"Q{i+1}"
            if cols[i % 10].button(label, key=f"jump_{i}", use_container_width=True):
                st.session_state.current_q = i
            cols[i % 10].markdown(
                f"<div style='background-color:{color}; color:white; padding:5px; "
                f"text-align:center; border-radius:4px;'>{label}</div>",
                unsafe_allow_html=True
            )

    if show_all or total <= 10:
        render_range(0, total)
    else:
        render_range(0, 10)
        with st.expander(f"Show remaining {total-10} questions"):
            render_range(10, total)

    st.markdown("</div>", unsafe_allow_html=True)


# =====================================================================
# SCORE CALCULATION
# =====================================================================
def calculate_score(questions, answers):
    """Calculate total score and detailed result per question."""
    score = 0
    detailed = []
    for i, q in enumerate(questions):
        user_ans = answers[i] if i < len(answers) and answers[i] else "No Answer"

        correct_ans = q["answer"]
        correct = user_ans.strip().lower() == correct_ans.strip().lower()
        if correct:
            score += 1
        detailed.append({
            "question": q["question"],
            "your_answer": user_ans,
            "correct_answer": correct_ans,
            "is_correct": correct
        })
    return score, detailed


# =====================================================================
# QUESTION UPLOAD HANDLER
# =====================================================================
def handle_uploaded_questions(file, class_name, subject_name):
    """Process JSON question upload from admin."""
    try:
        content = file.read().decode("utf-8").strip()
        try:
            questions = json.loads(content)
        except json.JSONDecodeError as e:
            st.error(f" Invalid JSON format: {e}")
            st.info("Make sure your file uses double quotes and is valid JSON.")
            return False

        if isinstance(questions, dict) and "questions" in questions:
            questions = questions["questions"]

        if not isinstance(questions, list):
            st.error(" Uploaded file must be a JSON list or contain a 'questions' key with a list.")
            return False

        valid = [
            q for q in questions
            if isinstance(q, dict) and all(k in q for k in ("question", "options", "answer"))
        ]
        if not valid:
            st.error("No valid questions found in file.")
            return False

        set_questions(class_name, subject_name, valid)
        st.success(f" Uploaded {len(valid)} questions for {class_name} - {subject_name}")
        return True

    except Exception as e:
        st.error(f" Error handling uploaded file: {e}")
        return False


def load_questions(class_name: str):
    """
    Load all questions for a given class from the database.
    Returns a list of dicts:
    [
        {"question": "...", "options": [...], "answer": "..."},
        ...
    ]
    """
    db = SessionLocal()
    try:
        rows = db.query(Question).filter(Question.class_name == class_name.strip().upper()).all()
        if not rows:
            return []

        validated = []
        for q in rows:
            try:
                options = json.loads(q.options) if isinstance(q.options, str) else q.options
                validated.append({
                    "question": q.question_text,
                    "options": options,
                    "answer": q.correct_answer
                })
            except Exception:
                # Skip invalid questions
                continue
        return validated
    finally:
        db.close()


def load_all_questions():
    """
    Loads all questions from the database and groups them by class.
    Returns a dict:
    {
        "JHS1": [list of questions],
        "JHS2": [...],
        ...
    }
    """
    db = SessionLocal()
    all_questions = {}
    try:
        rows = db.query(Question).all()
        for q in rows:
            try:
                options = json.loads(q.options) if isinstance(q.options, str) else q.options
                item = {"question": q.question_text, "options": options, "answer": q.correct_answer}

                if q.class_name not in all_questions:
                    all_questions[q.class_name] = []
                all_questions[q.class_name].append(item)
            except Exception:
                continue
    finally:
        db.close()
    return all_questions


def debug_print_admins():
    """Debug: Print all admins and their roles (without passwords)."""
    if not os.path.exists(UNIFIED_FILE):
        print("⚠️ No unified_data.json file found.")
        return

    try:
        with open(UNIFIED_FILE, "r") as f:
            data = json.load(f)

        admins = data.get("admins", {})
        print("\n🔎 DEBUG: Current Admins in unified_data.json")
        print("=============================================")
        if not admins:
            print("❌ No admins found in file.")
            return

        for name, info in admins.items():
            role = info.get("role", "unknown")
            print(f"👤 {name}  |  Role: {role}")

        print("=============================================\n")
    except json.JSONDecodeError:
        print("❌ Could not decode unified_data.json (invalid JSON).")

