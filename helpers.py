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

def ensure_super_admin():
    data = _load_unified_data()
    data.setdefault("admins", {})
    if "Admin" not in data["admins"]:
        data["admins"]["Admin"] = {
            "password": _hash_password("admin"),
            "role": "super_admin"
        }

        _save_unified_data(data)


# =====================================================================
# CALL AT STARTUP
# =====================================================================
ensure_super_admin()

# =====================================================================
# RETAKES
# =====================================================================
def get_retakes():
    return _load_unified_data().get("retakes", {})

def set_retakes(retakes):
    data = _load_unified_data()
    data["retakes"] = retakes
    _save_unified_data(data)

def grant_retake(access_code: str, subject: str):
    data = _load_unified_data()
    subj_key = subject.strip().lower()
    if "retakes" not in data:
        data["retakes"] = {}
    if access_code not in data["retakes"]:
        data["retakes"][access_code] = {}
    data["retakes"][access_code][subj_key] = True
    _save_unified_data(data)
    return True


# =====================================================================
# SUBMISSIONS
# =====================================================================
def get_submissions():
    return _load_unified_data().get("submissions", [])

def set_submissions(submissions):
    data = _load_unified_data()
    data["submissions"] = submissions
    _save_unified_data(data)


# =====================================================================
# LEADERBOARD
# =====================================================================
def get_leaderboard():
    return _load_unified_data().get("leaderboard", [])

def set_leaderboard(lb):
    data = _load_unified_data()
    data["leaderboard"] = lb
    _save_unified_data(data)


# =====================================================================
# LEGACY SINGLE-ADMIN SYSTEM
# =====================================================================
# Only supports one admin. Will be removed later.
# Uses `admin_config` dictionary in unified_data.json

def get_admin_config():
    return _load_unified_data().get(
        "admin_config",
        {"admin_username": "admin", "admin_password": "admin123"}
    )

def set_admin_config(config):
    data = _load_unified_data()
    data["admin_config"] = config
    _save_unified_data(data)

def require_admin_login():
    data = _load_unified_data()
    admins = data.get("admins", {})

    # Check if already logged in
    if st.session_state.get("admin_logged_in", False):
        return True

    st.subheader("🔑 Admin Login")
    username = st.text_input("Username", key="admin_username_input")
    password = st.text_input("Password", type="password", key="admin_password_input")

    col1, col2 = st.columns([3, 1])

    with col1:
        if st.button("Login"):
            normalized = username.strip().lower()
            # Create a case-insensitive lookup mapping
            admins_lower = {k.lower(): (k, v) for k, v in admins.items()}

            if normalized in admins_lower:
                original_key, admin_data = admins_lower[normalized]

                if _verify_password(password, admin_data["password"]):
                    # ✅ Store the correct original key (case preserved)
                    st.session_state.admin_username = original_key
                    st.session_state.admin_logged_in = True
                    st.session_state.admin_role = admin_data["role"]
                    st.success(f"✅ Logged in as {original_key} ({admin_data['role']})")
                    st.rerun()
                else:
                    st.error("❌ Invalid username or password")
            else:
                st.error("❌ Invalid username or password")

    # Only allow password reset for super_admin
    with col2:
        if st.button("Reset Password (Super Admin Only)"):
            st.session_state.show_reset_pw = True  # toggle UI

    if st.session_state.get("show_reset_pw", False):
        st.info("🔐 Super Admin Password Reset")
        super_admin = st.text_input("Super Admin Username", key="super_admin_user")
        super_pass = st.text_input("Super Admin Password", type="password", key="super_admin_pass")

        if st.button("Authenticate Super Admin"):
            super_admin_norm = super_admin.strip().lower()
            admins_lower = {k.lower(): (k, v) for k, v in admins.items()}

            if super_admin_norm in admins_lower:
                _, sa_data = admins_lower[super_admin_norm]
                if sa_data["role"] == "super_admin" and _verify_password(super_pass, sa_data["password"]):
                    st.session_state.super_admin_authenticated = True
                    st.success("✅ Super Admin authenticated! You can now reset any admin password.")
                else:
                    st.error("❌ Invalid super admin credentials")
            else:
                st.error("❌ Invalid super admin credentials")

        if st.session_state.get("super_admin_authenticated", False):
            reset_user = st.text_input("Username to Reset", key="reset_target_user")
            new_password = st.text_input("New Password", type="password", key="reset_new_pw")
            if st.button("Confirm Reset"):
                reset_user_norm = reset_user.strip().lower()
                admins_lower = {k.lower(): (k, v) for k, v in admins.items()}

                if reset_user_norm in admins_lower:
                    original_key, _ = admins_lower[reset_user_norm]
                    data["admins"][original_key]["password"] = _hash_password(new_password)
                    _save_unified_data(data)
                    st.success(f"✅ Password for {original_key} reset successfully!")
                    st.session_state.show_reset_pw = False
                    st.session_state.super_admin_authenticated = False
                else:
                    st.error("❌ User not found")

    return False


def ensure_super_admin_exists():
    """Ensure that super_admin with password 1234 always exists."""
    if not os.path.exists(UNIFIED_FILE):
        # If file doesn't exist, create a minimal structure
        data = {"admins": {}}
    else:
        with open(UNIFIED_FILE, "r") as f:
            data = json.load(f)

    if "admins" not in data:
        data["admins"] = {}

    if "super_admin" not in data["admins"]:
        data["admins"]["super_admin"] = {
            "password": hashlib.sha256("1234".encode()).hexdigest(),
            "role": "super_admin"
        }
        with open(UNIFIED_FILE, "w") as f:
            json.dump(data, f, indent=4)
        print("✅ Created fallback super_admin (password=1234)")

    return data


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

# =====================================================================
# NEW MULTI-ADMIN SYSTEM
# =====================================================================
# Supports multiple admins with hashed passwords and logs
# Uses `admins` and `admin_logs` in unified_data.json


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

with open("unified_data.json", "r") as f:
    data = json.load(f)

# 👇 Change "Admin" to your main admin username
username = "Admin"
new_password = "1234"  # 👈 your chosen new password
if "admins" not in data:
    data["admins"] = {}

if username not in data["admins"]:
    data["admins"][username] = {"password": _hash_password(new_password), "role": "superadmin"}
else:
    data["admins"][username]["password"] = _hash_password(new_password)

_save_unified_data(data)

with open("unified_data.json", "w") as f:
    json.dump(data, f, indent=4)


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
# QUESTIONS
# =====================================================================
QUESTIONS_DIR = "questions"

def get_questions(class_name, subject_name):
    key = f"questions_{class_name.strip().lower()}_{subject_name.strip().lower()}.json"
    file_path = os.path.join(QUESTIONS_DIR, key)
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Error loading questions: {e}")
        return []

def set_questions(class_name, subject_name, questions):
    os.makedirs(QUESTIONS_DIR, exist_ok=True)
    key = f"questions_{class_name.strip().lower()}_{subject_name.strip().lower()}"
    file_path = os.path.join(QUESTIONS_DIR, f"{key}.json")
    if isinstance(questions, dict) and "questions" in questions:
        questions_to_save = questions["questions"]
    elif isinstance(questions, list):
        questions_to_save = questions
    else:
        raise ValueError("Questions must be a list or a dict with 'questions' key")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(questions_to_save, f, indent=4)
    return file_path

def delete_question_file(class_name, subject_name):
    data = _load_unified_data()
    if ("questions" in data
        and class_name in data["questions"]
        and subject_name in data["questions"][class_name]):
        del data["questions"][class_name][subject_name]
        _save_unified_data(data)


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

def get_users():
    """Return all users from unified storage as a dict."""
    data = _load_unified_data()
    return data.get("users", {})

def set_users(users: dict):
    """Replace users in unified storage with the given dict."""
    data = _load_unified_data()
    data["users"] = users
    _save_unified_data(data)

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



def load_questions(class_name: str, subject: str):
    key = f"questions_{class_name.strip().lower()}_{subject.strip().lower()}.json"
    file_path = os.path.join(QUESTIONS_DIR, key)

    if not os.path.exists(file_path):
        st.warning(f"No questions found for key: '{key}'")
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        questions = data.get("questions", []) if isinstance(data, dict) else data
        if not isinstance(questions, list):
            st.warning(f"Invalid question format in: {file_path}")
            return []

        validated = [
            {"question": q["question"], "options": q["options"], "answer": q["answer"]}
            for q in questions
            if isinstance(q, dict) and all(k in q for k in ("question", "options", "answer"))
        ]

        if not validated:
            st.warning(f"No valid questions found in file: {file_path}")

        return validated

    except Exception as e:
        st.error(f"Error loading questions from {file_path}: {e}")
        return []


def load_all_questions():
    """
    Loads all questions from QUESTIONS_DIR and returns a dict structured as:
    {
        "jhs1_math": [list of questions],
        "jhs2_english": [list of questions],
        ...
    }
    """
    all_questions = {}

    for filename in os.listdir(QUESTIONS_DIR):
        if filename.startswith("questions_") and filename.endswith(".json"):
            key = filename.replace(".json", "").replace("questions_", "")
            file_path = os.path.join(QUESTIONS_DIR, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                questions = data.get("questions", []) if isinstance(data, dict) else data
                validated = [
                    {"question": q["question"], "options": q["options"], "answer": q["answer"]}
                    for q in questions
                    if isinstance(q, dict) and all(k in q for k in ("question", "options", "answer"))
                ]
                if validated:
                    all_questions[key] = validated
            except Exception as e:
                st.warning(f"Failed to load {filename}: {e}")

    return all_questions


def require_multi_admin_login():
    """Multi-admin login UI. Returns True if logged in."""
    if "admin_logged_in" not in st.session_state:
        st.session_state.admin_logged_in = False
        st.session_state.admin_username = None
        st.session_state.admin_role = None

    if not st.session_state.admin_logged_in:
        st.subheader("🔑 Admin Login")
        username = st.text_input("Username", key="multi_admin_username")
        password = st.text_input("Password", type="password", key="multi_admin_password")

        if st.button("Login"):
            success, result = authenticate_admin(username.strip(), password)
            if success:
                st.session_state.admin_logged_in = True
                st.session_state.admin_username = username.strip()
                st.session_state.admin_role = result  # role: admin/moderator, etc.
                st.success(f"✅ Login successful as '{username.strip()}' ({result})")
                st.rerun()
            else:
                st.error(result)
        return False
    return True
