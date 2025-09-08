import streamlit as st
import pandas as pd
import json

# =====================================================================
# Local Imports
# =====================================================================
from helpers import (
    generate_access_code,
    require_admin_login,
    generate_access_slips,
    delete_question_file,
    change_admin_password_ui,
    reset_test,

    add_admin,
    remove_admin,
    _load_unified_data,

    # Unified JSON API
    get_users, set_users,
    get_retakes, set_retakes,
    get_leaderboard, set_leaderboard,
    get_admin_config, set_admin_config,
    get_questions, set_questions
)

# =====================================================================
# Constants
# =====================================================================
CLASSES = ["JHS1", "JHS2", "JHS3"]
SUBJECTS = [
    "English", "Math", "Science", "History", "Geography",
    "Physics", "Chemistry", "Biology", "ICT", "Economics"
]

# =====================================================================
# Admin Mode
# =====================================================================
def run_admin_mode():
    """Main Admin Panel UI (Multi-Admin Enabled)."""
    if not require_admin_login():
        return

    st.sidebar.title("⚙️ Admin Panel")
    selected_tab = st.sidebar.radio("Choose Action", [
        "➕ Add User",
        "📥 Bulk Add Students",
        "👥 Manage Students",
        "🛡️ Manage Admins",
        "🔑 Change Password",
        "📤 Upload Questions",
        "🗑️ Delete Questions & Duration",
        "🏆 View Leaderboard",
        "🔄 Allow Retake",
        "🖨️ Generate Access Slips",
        "♻️ Reset Tests",
        "🚪 Logout"
    ])

    st.title("🛠️ Admin Dashboard")

    # -----------------------------
    # Add User
    # -----------------------------
    if selected_tab == "➕ Add User":
        st.subheader("Add a Student")
        name = st.text_input("Student Name")
        class_name = st.selectbox("Class", CLASSES)
        if st.button("Add Student"):
            users_dict = get_users()
            access_code = generate_access_code(name, set(users_dict.keys()))
            users_dict[access_code] = {
                "access_code": access_code,
                "name": name,
                "class": class_name,
                "can_retake": True,
                "submitted": False,
            }
            set_users(users_dict)
            st.success(f"✅ {name} added | Access Code: {access_code}")

    # -----------------------------
    # Bulk Add Students
    # -----------------------------
    elif selected_tab == "📥 Bulk Add Students":
        st.subheader("Bulk Upload Students (CSV)")
        uploaded_file = st.file_uploader("Upload CSV with 'name' & 'class'", type=["csv"])
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
                if not {"name", "class"}.issubset(df.columns):
                    st.error("❌ CSV must have 'name' and 'class' columns.")
                else:
                    users_dict, new_students = get_users(), []
                    existing_codes = set(users_dict.keys())

                    for _, row in df.iterrows():
                        name, class_name = str(row["name"]).strip(), str(row["class"]).strip()
                        code = generate_access_code(name, existing_codes)
                        existing_codes.add(code)
                        users_dict[code] = {
                            "access_code": code,
                            "name": name,
                            "class": class_name,
                            "can_retake": True,
                            "submitted": False,
                        }
                        new_students.append({"Access Code": code, "Name": name, "Class": class_name})

                    set_users(users_dict)
                    st.success(f"✅ {len(new_students)} students added.")
                    st.table(pd.DataFrame(new_students))
            except Exception as e:
                st.error(f"Error reading CSV: {e}")

    # -----------------------------
    # Manage Students
    # -----------------------------
    elif selected_tab == "👥 Manage Students":
        users = get_users()
        if not users:
            st.info("No students found.")
        else:
            df = pd.DataFrame(users.values())
            st.dataframe(df, use_container_width=True)
            st.download_button("⬇️ Download CSV", df.to_csv(index=False).encode("utf-8"),
                               "students.csv", "text/csv")

    # -----------------------------
    # Manage Admins
    # -----------------------------
    elif selected_tab == "🛡️ Manage Admins":
        st.subheader("Admin Accounts")

        # Add
        st.markdown("#### ➕ Add Admin")
        new_user = st.text_input("Username")
        new_pass = st.text_input("Password", type="password")
        role = st.selectbox("Role", ["admin", "moderator"])
        if st.button("Add Admin"):
            ok, msg = add_admin(new_user, new_pass, role, st.session_state.admin_username)
            st.success(msg) if ok else st.error(msg)

        # Remove
        st.markdown("#### ➖ Remove Admin")
        data = _load_unified_data()
        admins = list(data.get("admins", {}).keys())
        to_remove = st.selectbox("Select Admin", admins) if admins else None
        if to_remove and st.button("Remove Admin"):
            ok, msg = remove_admin(to_remove, st.session_state.admin_username)
            st.success(msg) if ok else st.error(msg)

        # Logs
        st.markdown("#### 📜 Logs")
        logs = data.get("admin_logs", [])
        st.dataframe(pd.DataFrame(logs)) if logs else st.info("No logs yet.")

    # -----------------------------
    # Change Password
    # -----------------------------
    elif selected_tab == "🔑 Change Password":
        change_admin_password_ui()

    # -----------------------------
    # Upload Questions
    # -----------------------------
    elif selected_tab == "📤 Upload Questions":
        cls, sub = st.selectbox("Class", CLASSES), st.selectbox("Subject", SUBJECTS)
        uploaded = st.file_uploader("Upload Questions JSON", type="json")
        if uploaded:
            try:
                data = json.load(uploaded)
                questions = data.get("questions", []) if isinstance(data, dict) else data
                valid = [q for q in questions if all(k in q for k in ("question", "options", "answer"))]
                if not valid:
                    st.error("❌ No valid questions found.")
                else:
                    path = set_questions(cls, sub, valid)
                    st.success(f"✅ {len(valid)} questions uploaded for {cls}-{sub}")
                    st.caption(f"Saved: {path}")
            except Exception as e:
                st.error(f"Upload failed: {e}")

    # -----------------------------
    # Delete Questions & Duration
    # -----------------------------
    elif selected_tab == "🗑️ Delete Questions & Duration":
        cls, sub = st.selectbox("Class", CLASSES), st.selectbox("Subject", SUBJECTS)
        if st.button("Delete Questions"):
            delete_question_file(cls, sub)
            st.success("Questions deleted.")

        config = get_admin_config()
        duration = st.slider("Test Duration (minutes)", 5, 120, config.get("duration", 30))
        if st.button("Save Duration"):
            set_admin_config({"duration": duration})
            st.success("✅ Duration updated.")

    # -----------------------------
    # View Leaderboard
    # -----------------------------
    elif selected_tab == "🏆 View Leaderboard":
        lb = get_leaderboard()
        st.dataframe(pd.DataFrame(lb)) if lb else st.info("No submissions yet.")

    # -----------------------------
    # Allow Retake
    # -----------------------------
    elif selected_tab == "🔄 Allow Retake":
        code = st.text_input("Student Access Code")
        if code:
            users, retakes = get_users(), get_retakes()
            student = users.get(code.strip())
            if not student:
                st.error("❌ Invalid code.")
            else:
                st.info(f"Student: {student['name']} | Class: {student['class']}")
                current = retakes.get(code, {})
                updates = {s: st.checkbox(s, value=current.get(s.lower(), False)) for s in SUBJECTS}
                if st.button("Save Retake"):
                    retakes[code] = {s.lower(): v for s, v in updates.items() if v}
                    set_retakes(retakes)
                    lb = [e for e in get_leaderboard() if e.get("access_code") != code]
                    set_leaderboard(lb)
                    st.success("✅ Retake updated.")

    # -----------------------------
    # Generate Access Slips
    # -----------------------------
    elif selected_tab == "🖨️ Generate Access Slips":
        if st.button("Generate ZIP"):
            users = get_users()
            buffer = generate_access_slips(users)
            st.download_button("⬇️ Download ZIP", buffer, "AccessSlips.zip")

    # -----------------------------
    # Reset Tests
    # -----------------------------
    elif selected_tab == "♻️ Reset Tests":
        if st.button("Reset All Tests"):
            reset_test()
            st.success("✅ Tests reset.")

    # -----------------------------
    # Logout
    # -----------------------------
    elif selected_tab == "🚪 Logout":
        st.session_state["admin_logged_in"] = False
        st.success("Logged out.")
        st.rerun()
