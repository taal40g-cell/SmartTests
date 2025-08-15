import json
from datetime import datetime
import streamlit as st
import csv
import bcrypt
import pandas as pd
from config import ADMIN_USERNAME, ADMIN_PASSWORD
import qrcode
from io import BytesIO
import io
import zipfile
from fpdf import FPDF


def require_admin_login():
    if "admin_logged_in" not in st.session_state:
        st.session_state["admin_logged_in"] = False

    if not st.session_state["admin_logged_in"]:
        st.subheader("Admin Login")
        username = st.text_input("Username", key="admin_username")
        password = st.text_input("Password", type="password", key="admin_password")

        if st.button("Login"):

            if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                st.session_state["admin_logged_in"] = True
                st.success("Login successful")
            else:
                st.error("Incorrect username or password")
        return False

    return True

# ----------------------------- Session Initialization -----------------------------


# ----------------------------- Background -----------------------------

def show_progress_chart():
    answers = st.session_state.get("answers", {})
    marked = st.session_state.get("marked_review", {})

    total = len(answers)
    answered = sum(1 for a in answers.values() if a)
    marked_review = sum(1 for k, v in marked.items() if v)
    unanswered = total - answered

    fig = go.Figure(data=[go.Pie(
        labels=["Answered", "Marked for Review", "Unanswered"],
        values=[answered, marked_review, unanswered],
        hole=0.4
    )])
    fig.update_traces(textinfo="label+value", pull=[0.05, 0.05, 0])
    st.plotly_chart(fig, use_container_width=True)
# ----------------------------- User Management -----------------------------
# Dictionary version (used for fast access in Student test mode)

# List version (used for access slips, loops, etc.)
def load_users():

    users = []
    if os.path.exists("users.csv"):
        with open("users.csv", "r", newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            users = list(reader)
    return users

def load_users_list():
    import csv
    users_list = []
    with open("users.csv", newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            users_list.append({
                "access_code": row.get("access_code", "").strip(),
                "name": row.get("name", "").strip(),
                "class": row.get("class", "").strip(),
                "can_retake": row.get("can_retake", "").strip().lower() == "true"
            })
    return users_list


def save_users(users):
    with open("users.csv", "w", encoding="utf-8") as f:
        f.write("access_code,name,class,can_retake\n")
        for user in users:
            f.write(f"{user['access_code']},{user['name']},{user['class']},{user['can_retake']}\n")

def generate_access_code(name):
    base = name.replace(" ", "").lower()
    code = base[:4] + str(datetime.now().microsecond)[-4:]
    return code


def allow_retake_toggle(access_code, value):
    users = load_users()
    if access_code in users:
        users[access_code]["can_retake"] = value
        save_users(users)


# ----------------------------- Question Management -----------------------------

def get_question_file_name(class_name, subject_name):
    class_name = class_name.replace(" ", "").lower()
    subject_name = subject_name.replace(" ", "").lower()
    return f"questions_{class_name}_{subject_name}.json"


def save_questions(class_name, subject_name, questions):
    file_name = get_question_file_name(class_name, subject_name)
    with open(file_name, "w") as f:
        json.dump(questions, f)

    #st.write("?? Trying to load:", file_name)
    if not os.path.exists(file_name):
        st.error(f"? File not found: {file_name}")
        return []
    with open(file_name, "r") as f:
        questions = json.load(f)
      # st.write(f"? Loaded {len(questions)} questions")
        return questions


def delete_question_file(class_name, subject_name):
    file_name = get_question_file_name(class_name, subject_name)
    if os.path.exists(file_name):
        os.remove(file_name)


# ----------------------------- Score & Result -----------------------------

def calculate_score(questions, answers):
    score = 0
    detailed = []
    for i, q in enumerate(questions):
        # Access the user's answer by index with fallback
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


def save_student_result(access_code, result_entry, folder="results"):
    os.makedirs(folder, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{access_code}_{timestamp}.json"
    file_path = os.path.join(folder, filename)
    with open(file_path, "w") as f:
        json.dump(result_entry, f, indent=4)

def load_results_detail(access_code, folder="results"):
    file_path = os.path.join(folder, f"{access_code}.json")
    if not os.path.exists(file_path):
        return {}
    with open(file_path, "r") as f:
        return json.load(f)
from fpdf import FPDF
import os

def save_result_pdf(access_code, result_entry, folder="result_pdfs"):
    print(f"Saving PDF for {access_code}")

    os.makedirs(folder, exist_ok=True)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(0, 10, f"?? Result Summary for: {result_entry.get('name', '')}", ln=True)
    pdf.cell(0, 10, f"Class: {result_entry.get('class', '')}", ln=True)
    pdf.cell(0, 10, f"Subject: {result_entry.get('subject', '')}", ln=True)
    pdf.cell(0, 10, f"Score: {result_entry.get('score', '')} / {result_entry.get('total', '')}", ln=True)
    pdf.cell(0, 10, f"Percentage: {result_entry.get('percentage', '')}%", ln=True)
    pdf.ln(10)

    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Answer Breakdown:", ln=True)
    pdf.set_font("Arial", "", 11)

    for i, detail in enumerate(result_entry.get("details", []), start=1):
        pdf.multi_cell(0, 10, f"{i}. {detail['question']}\n"
                              f"Your Answer: {detail['your_answer']}\n"
                              f"Correct Answer: {detail['correct_answer']}\n"
                              f"{'? Correct' if detail['is_correct'] else '? Incorrect'}", border=1)
        pdf.ln(2)

    file_path = os.path.join(folder, f"{access_code}.pdf")
    pdf.output(file_path)

# ----------------------------- Admin Config -----------------------------

def save_admin_config(config):
    with open("admin_config.json", "w") as f:
        json.dump(config, f)


def load_admin_config():
    if os.path.exists("admin_config.json"):
        with open("admin_config.json", "r") as f:
            return json.load(f)
    return {}


# ----------------------------- Leaderboard -----------------------------

def load_leaderboard(file_path="leaderboard.json"):
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    return []


def save_leaderboard(data, file_path="leaderboard.json"):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)

def save_student_result(access_code, result_entry):
    results = {}
    if os.path.exists("results.json"):
        with open("results.json", "r") as file:
            results = json.load(file)

    results[access_code] = result_entry

    with open("results.json", "w") as file:
        json.dump(results, file, indent=4)

def generate_access_slips(users, folder="access_slips"):
    # Ensure folder exists
    if not os.path.exists(folder):
        os.makedirs(folder)

    # Create PDFs
    for user in users:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=14)
        pdf.cell(0, 10, txt="Access Slip", ln=True, align='C')
        pdf.ln(10)

        pdf.set_font("Arial", size=12)
        pdf.set_text_color(0, 0, 160)
        pdf.cell(0, 10, f"Name: {user.get('name', '')}", ln=True)
        pdf.cell(0, 10, f"Class: {user.get('class', '')}", ln=True)
        pdf.cell(0, 10, f"Access Code: {user.get('access_code', '')}", ln=True)
        pdf.cell(0, 10, f"Retake Allowed: {'Yes' if user.get('can_retake', True) else 'No'}", ln=True)

        file_name = f"{folder}/{user['access_code']}.pdf"
        pdf.output(file_name)

    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file in os.listdir(folder):
            zipf.write(os.path.join(folder, file), file)
    zip_buffer.seek(0)

    return zip_buffer

def zip_slips_folder(folder="access_slips"):
    zip_filename = "AccessSlips.zip"
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder)
                zipf.write(file_path, arcname)
    return zip_filename


# ----------------------------- UI Helpers -----------------------------

def add_user_ui():
    st.subheader(" Add New Student")
    name = st.text_input("Student Name")
    class_name = st.text_input("Class")
    can_retake = st.checkbox("Allow Retake", value=True)

    if st.button("Generate Access Code"):
        access_code = generate_access_code(name)
        new_user = {
            "access_code": access_code,
            "name": name,
            "class": class_name,
            "can_retake": can_retake
        }
        users = load_users()
        users.append(new_user)
        # Save to CSV
        with open("users.csv", "a", newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["access_code", "name", "class", "can_retake"])
            if f.tell() == 0:  # File is empty, write header
                writer.writeheader()
            writer.writerow(new_user)

        st.success(f"? User '{name}' added with code: {access_code}")


USERS_FILE = "users.csv"

def change_admin_password_ui():
    st.subheader("?? Change Admin Password")

    if not os.path.exists(USERS_FILE):
        st.error("? No users file found.")
        return

    users_df = pd.read_csv(USERS_FILE)

    username = st.text_input("Admin Username")
    old_password = st.text_input("Current Password", type="password")
    new_password = st.text_input("New Password", type="password")
    confirm_password = st.text_input("Confirm New Password", type="password")

    if st.button("Update Password"):
        if new_password != confirm_password:
            st.warning("?? New passwords do not match.")
            return

        user_row = users_df[(users_df["username"] == username) & (users_df["role"] == "admin")]

        if user_row.empty:
            st.error("? Admin user not found.")
            return

        stored_hash = user_row.iloc[0]["password"].encode('utf-8')
        if not bcrypt.checkpw(old_password.encode('utf-8'), stored_hash):
            st.error("? Incorrect current password.")
            return

        new_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        users_df.loc[users_df["username"] == username, "password"] = new_hash.decode('utf-8')
        users_df.to_csv(USERS_FILE, index=False)
        st.success("? Password updated successfully.")



RETAKE_FILE = "retake_tracker.json"

def load_retake_tracker():
    if os.path.exists(RETAKE_FILE):
        with open(RETAKE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_retake_tracker(data):
    with open(RETAKE_FILE, "w") as f:
        json.dump(data, f, indent=4)

def has_taken_subject(access_code, subject):
    tracker = load_retake_tracker()
    return subject in tracker.get(access_code, [])

def mark_subject_taken(access_code, subject):
    tracker = load_retake_tracker()
    tracker.setdefault(access_code, []).append(subject)
    save_retake_tracker(tracker)


import plotly.graph_objects as go
def show_question_status_chart(questions, answers, marked_review, class_name, subject_name):
    status_dict = {"Unanswered": 0, "Answered": 0, "Marked for Review": 0}
    for i, _ in enumerate(questions):
        if i in marked_review:
            status_dict["Marked for Review"] += 1
        elif i in answers:
            status_dict["Answered"] += 1
        else:
            status_dict["Unanswered"] += 1

    labels = list(status_dict.keys())
    values = list(status_dict.values())

    fig = go.Figure(
        data=[go.Pie(labels=labels, values=values, hole=0.4)],
    )
    fig.update_layout(
        title_text="Question Status Overview",
        showlegend=True,
        margin=dict(t=30, b=0, l=0, r=0),
    )

    # Ensure the key is always unique
    key_suffix = f"{class_name}_{subject_name}"
    st.plotly_chart(fig, use_container_width=True, key=f"question_status_chart_{key_suffix}")

def show_question_tracker():
    total = len(st.session_state.questions)
    answers = st.session_state.answers
    marked = st.session_state.get("marked_for_review", set())
    show_all = st.session_state.get("show_all_tracker", False)

    # ?? Floating top tracker style
    st.markdown("""
        <style>
        .floating-tracker {
            position: -webkit-sticky;
            position: sticky;
            top: 0;
            z-index: 999;
            background-color: #f0f2f6;
            padding: 10px 8px;
            border-bottom: 1px solid #ddd;
            border-radius: 8px;
        }
        .q-btn {
            text-align: center;
            font-size: 11px;
            margin-top: -6px;
            color: white;
            border-radius: 4px;
            padding: 4px 0;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="floating-tracker">', unsafe_allow_html=True)
    st.markdown("###  Progress Tracker")

    # ?? Toggle checkbox for full view
    st.session_state.show_all_tracker = st.checkbox(
        " Show all", value=show_all, key="toggle_tracker"
    )

    def render_tracker_range(start, end):
        cols = st.columns(10)
        for i in range(start, end):
            color = "red"
            if i in marked:
                color = "orange"
            elif answers[i]:
                color = "green"

            label = f"Q{i+1}"
            if cols[i % 10].button(label, key=f"jump_q_{i}", use_container_width=True):
                st.session_state.current_q = i
            cols[i % 10].markdown(
                f"<div class='q-btn' style='background-color:{color};'>{label}</div>",
                unsafe_allow_html=True
            )

    # ?? Show compact by default, expandable
    if st.session_state.show_all_tracker or total <= 10:
        render_tracker_range(0, total)
    else:
        render_tracker_range(0, 10)
        with st.expander(f" Show remaining {total - 10} questions"):
            render_tracker_range(10, total)

    st.markdown('</div>', unsafe_allow_html=True)

    # ?? Legend
    st.markdown("""
        <div style='margin-top:10px; font-size: 13px;'>
            <span style="color:green;"> Answered</span> |
            <span style="color:red;"> Not Answered</span> |
            <span style="color:orange;"> Marked for Review</span>
        </div>
    """, unsafe_allow_html=True)


def toggle_mark_for_review(q_index):
    """
    Toggles whether the current question is marked for review.
    """
    marked = st.session_state.get("marked_for_review", set())
    is_marked = q_index in marked

    toggle = st.checkbox(" Mark this question for review", value=is_marked)

    if toggle:
        marked.add(q_index)
    else:
        marked.discard(q_index)

    st.session_state.marked_for_review = marked


def load_questions(class_name, subject_name):
    """Load questions for the given class and subject."""
    safe_class = class_name.lower().replace(" ", "")
    safe_subject = subject_name.lower().replace(" ", "")
    filename = f"questions_{safe_class}_{safe_subject}.json"
    filepath = os.path.join("questions", filename)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def view_student_performance(student):
    """Show the performance history of a student."""
    try:
        df = pd.read_csv("performance.csv")
    except FileNotFoundError:
        st.warning("No performance data found.")
        return

    student_data = df[df['access_code'] == student['access_code']]

    if student_data.empty:
        st.info("No performance records found for this student.")
    else:
        st.dataframe(student_data)

def generate_qr_code(data):
    """
    Generate a QR code image for the given data string.
    Returns a BytesIO object with PNG image data.
    """
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def load_results(access_code):
    path = f"results/{access_code}.json"
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return None

def results_page():
    access_code = st.query_params.get("access_code", [None])[0]

    if not access_code:
        st.error("No access code provided in URL.")
        return

    results = load_results(access_code)
    if not results:
        st.error("No results found for this access code.")
        return

    st.title(f"Results for {results.get('name', 'Unknown Student')}")
    st.write(f"Class: {results.get('class', '')}")
    st.write(f"Subject: {results.get('subject', '')}")
    st.write(f"Score: {results.get('score', 0)} / {results.get('total', 0)}")
    st.write(f"Percentage: {results.get('percentage', 0):.2f}%")

    st.markdown("### Detailed Answers")
    for i, detail in enumerate(results.get("details", []), start=1):
        st.write(f"**Q{i}:** {detail['question']}")
        st.write(f"- Your answer: {detail['your_answer']}")
        st.write(f"- Correct answer: {detail['correct_answer']}")
        st.write(f"- Result: {'✅ Correct' if detail['is_correct'] else '❌ Incorrect'}")
        st.write("---")


def load_users_dict():
    import csv
    users_dict = {}
    try:
        with open("users.csv", newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                access_code = row.get("access_code", "").strip()
                if access_code:
                    users_dict[access_code] = {
                        "name": row.get("name", "").strip(),
                        "class": row.get("class", "").strip(),
                        "can_retake": row.get("can_retake", "").strip().lower() == "true"
                    }
    except FileNotFoundError:
        pass
    return users_dict

def show_header():
    st.markdown("<h2 style='text-align: center;'>?? SmartTest Student Portal</h2>", unsafe_allow_html=True)
    st.write("Welcome to your personalized test center.")

def layout_top_controls(class_name, subject_name, duration):
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"?? Class: **{class_name}**")
        st.info(f"?? Subject: **{subject_name}**")
    with col2:
        from datetime import datetime

        if "test_start_time" in st.session_state and "test_end_time" in st.session_state:
            now = datetime.now()
            remaining = st.session_state.test_end_time - now
            if remaining.total_seconds() > 0:
                minutes, seconds = divmod(int(remaining.total_seconds()), 60)
                st.success(f"Time Remaining: {minutes:02}:{seconds:02}")
            else:
                st.error("? Time's up!")


import streamlit as st
import base64

def set_background(image_file="assets/fl.png"):
    with open(image_file, "rb") as f:
        base64_image = base64.b64encode(f.read()).decode()

    background_style = f"""
        <style>
            .stApp {{
                background-image: url("data:image/png;base64,{base64_image}");
                background-size: cover;
            }}
        </style>
    """
    st.markdown(background_style, unsafe_allow_html=True)


def send_sms(to_number, message):
    """Mock SMS sender - no Twilio call"""
    print(f"📩 [MOCK] SMS to {to_number}: {message}")
