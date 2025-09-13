import streamlit as st
import pandas as pd
import json
from helpers import (
    generate_access_code,
    require_admin_login,
    generate_access_slips,
    delete_question_file,
    change_admin_password_ui,
    reset_test,
    generate_student_id,
    add_admin,
    remove_admin,
    _load_unified_data,
    get_users, set_users,
    get_retakes, set_retakes,
    get_leaderboard, set_leaderboard,
    get_admin_config, set_admin_config,
    get_questions, set_questions,ensure_super_admin_exists,upload_replace_unified_json_ui
)
ensure_super_admin_exists()



CLASSES = ["JHS1", "JHS2", "JHS3"]
SUBJECTS = [
    "English", "Math", "Science", "History", "Geography",
    "Physics", "Chemistry", "Biology", "ICT", "Economics"
]

ROLE_TABS = {
    "super_admin": [
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
    ],
    "admin": [
        "➕ Add User",
        "📥 Bulk Add Students",
        "👥 Manage Students",
        "🔑 Change Password",
        "📤 Upload Questions",
        "🗑️ Delete Questions & Duration",
        "🏆 View Leaderboard",
        "🔄 Allow Retake",
        "🖨️ Generate Access Slips",
        "🚪 Logout"
    ],
    "teacher": [
        "👥 Manage Students",
        "📤 Upload Questions",
        "🗑️ Delete Questions & Duration",
        "🏆 View Leaderboard",
        "🚪 Logout"
    ],
    "moderator": [
        "🏆 View Leaderboard",
        "🚪 Logout"
    ]
}

def run_admin_mode():
    """Clean role-aware admin panel with refresh and unique keys."""
    if not require_admin_login():
        return

    # -----------------------------
    # Refresh Admin Panel Button
    # -----------------------------
    st.divider()
    st.subheader("⚡ Refresh Admin Panel")
    if st.button("🔄 Refresh Admin UI", key="refresh_admin_ui"):
        for k in list(st.session_state.keys()):
            if "admin_" in k or "remove_admin" in k or "selected_tab" in k:
                st.session_state.pop(k, None)
        # Reset sidebar to Change Password
        st.session_state["selected_tab"] = "🔑 Change Password"
        st.success("✅ Admin panel refreshed. Sidebar reset to Change Password.")
        st.rerun()

    # -----------------------------
    # Load admins & detect role
    # -----------------------------
    data = _load_unified_data()
    admins = data.get("admins", {})
    current_user = st.session_state.get("admin_username", "")
    current_role = admins.get(current_user, {}).get("role", "admin")

    available_tabs = ROLE_TABS.get(current_role, ROLE_TABS["admin"])
    st.sidebar.title(f"⚙️ Admin Panel ({current_user} – {current_role})")

    # Sidebar remembers last selected tab
    selected_tab = st.session_state.get("selected_tab", available_tabs[0])
    selected_tab = st.sidebar.radio("Choose Action", available_tabs, index=available_tabs.index(selected_tab))
    st.session_state["selected_tab"] = selected_tab

    st.title("🛠️ Admin Dashboard")

    # ==============================
    # ➕ Add User
    # ==============================
    if selected_tab == "➕ Add User":
        st.subheader("Add a Student")
        name = st.text_input("Student Name", key="admin_add_name")
        class_name = st.selectbox("Class", CLASSES, key="admin_add_class")
        if st.button("Add Student", key="admin_add_btn"):
            if not name.strip():
                st.error("❌ Enter student name.")
            else:
                users = get_users()
                code = generate_access_code(name, set(users.keys()))
                student_id = generate_student_id(users)
                users[code] = {
                    "student_id": student_id,
                    "access_code": code,
                    "name": name,
                    "class": class_name,
                    "can_retake": True,
                    "submitted": False
                }
                set_users(users)
                st.success(f"✅ {name} added | ID: {student_id} | Code: {code}")

    # ==============================
    # 🛡️ Manage Admins (Super Admin)
    if selected_tab == "🛡️ Manage Admins" and current_role == "super_admin":
        st.header("🛡️ Manage Admins")
        upload_replace_unified_json_ui()  # Upload/replace unified_data.json

        if admins:
            st.dataframe(pd.DataFrame.from_dict(admins, orient="index"), use_container_width=True)
        else:
            st.info("No admins found. Create one below.")

        st.divider()
        st.write("### ➕ Add Admin")
        new_user = st.text_input("👤 Username", key="admin_add_user")
        new_pass = st.text_input("🔑 Password", type="password", key="admin_add_pass")
        new_role = st.selectbox("🎭 Role", ["admin", "teacher", "moderator", "super_admin"], key="admin_add_role")
        if st.button("Add Admin", key="admin_add_btn2"):
            if not new_user.strip() or not new_pass.strip():
                st.error("❌ Username & password required.")
            else:
                ok, msg = add_admin(new_user.strip(), new_pass.strip(), new_role, actor=current_user)
                st.success(msg) if ok else st.error(msg)
                if ok: st.rerun()

        st.divider()
        st.write("### 🗑️ Remove Admin")
        removable = [a for a in admins.keys() if a != current_user]
        if removable:
            admin_to_remove = st.selectbox("Select Admin to Remove", options=removable, key="admin_remove_select")
            if st.button("Remove Admin", key="admin_remove_btn"):
                ok, msg = remove_admin(admin_to_remove, actor=current_user)
                st.success(msg) if ok else st.error(msg)
                if ok: st.rerun()
        else:
            st.info("No admins available to remove.")

    # ==============================
    # 📥 Bulk Add Students
    # ==============================
    elif selected_tab == "📥 Bulk Add Students":
        st.subheader("Bulk Upload Students (CSV)")
        uploaded = st.file_uploader("Upload CSV with 'name' & 'class'", type=["csv"], key="bulk_upload_csv")
        if uploaded:
            try:
                df = pd.read_csv(uploaded)
                if not {"name", "class"}.issubset(df.columns):
                    st.error("CSV must have 'name' and 'class'")
                else:
                    users_dict = get_users()
                    existing_codes = set(users_dict.keys())
                    new_list = []
                    for _, row in df.iterrows():
                        name, cls = str(row["name"]).strip(), str(row["class"]).strip()
                        code = generate_access_code(name, existing_codes)
                        existing_codes.add(code)
                        student_id = generate_student_id(users_dict)
                        users_dict[code] = {
                            "student_id": student_id,
                            "access_code": code,
                            "name": name,
                            "class": cls,
                            "can_retake": True,
                            "submitted": False
                        }
                        new_list.append({"Student ID": student_id, "Access Code": code, "Name": name, "Class": cls})
                    set_users(users_dict)
                    st.success(f"✅ {len(new_list)} students added.")
                    st.table(pd.DataFrame(new_list))
            except Exception as e:
                st.error(f"Error reading CSV: {e}")

    # ==============================
    # 👥 Manage Students
    # ==============================
    elif selected_tab == "👥 Manage Students":
        users = get_users()
        if not users:
            st.info("No students found.")
        else:
            df = pd.DataFrame(users.values())
            st.dataframe(df, use_container_width=True)
            st.download_button("⬇️ Download CSV", df.to_csv(index=False).encode("utf-8"),
                               "students.csv", "text/csv", key="download_students")


    # ==============================
    # 🔑 Change Password
    # ==============================
    elif selected_tab == "🔑 Change Password":
        change_admin_password_ui()

    # ==============================
    # 📤 Upload Questions
    # ==============================
    elif selected_tab == "📤 Upload Questions":
        cls = st.selectbox("Class", CLASSES, key="upload_class")
        sub = st.selectbox("Subject", SUBJECTS, key="upload_subject")
        uploaded = st.file_uploader("Upload Questions JSON", type="json", key="upload_questions")
        if uploaded:
            try:
                data = json.load(uploaded)
                questions = data.get("questions", []) if isinstance(data, dict) else data
                valid = [q for q in questions if all(k in q for k in ("question", "options", "answer"))]
                if not valid:
                    st.error("No valid questions found.")
                else:
                    path = set_questions(cls, sub, valid)
                    st.success(f"✅ {len(valid)} questions uploaded for {cls}-{sub}")
                    st.caption(f"Saved: {path}")
            except Exception as e:
                st.error(f"Upload failed: {e}")

    # ==============================
    # 🗑️ Delete Questions & Duration
    # ==============================
    elif selected_tab == "🗑️ Delete Questions & Duration":
        cls = st.selectbox("Class", CLASSES, key="delete_class")
        sub = st.selectbox("Subject", SUBJECTS, key="delete_subject")
        if st.button("Delete Questions", key="delete_questions_btn"):
            delete_question_file(cls, sub)
            st.success("Questions deleted.")
        config = get_admin_config()
        duration = st.slider("Test Duration (minutes)", 5, 120, config.get("duration", 30), key="test_duration_slider")
        if st.button("Save Duration", key="save_duration_btn"):
            set_admin_config({"duration": duration})
            st.success("✅ Duration updated.")

    # ==============================
    # 🏆 View Leaderboard
    # ==============================
    elif selected_tab == "🏆 View Leaderboard":
        lb = get_leaderboard()
        if lb:
            st.dataframe(pd.DataFrame(lb), use_container_width=True)
        else:
            st.info("No submissions yet.")

    # ==============================
    # 🔄 Allow Retake
    # ==============================
    elif selected_tab == "🔄 Allow Retake":
        code = st.text_input("Student Access Code", key="retake_access_code")
        if code:
            users, retakes = get_users(), get_retakes()
            student = users.get(code.strip())
            if not student:
                st.error("Invalid code.")
            else:
                st.info(f"Student: {student['name']} | Class: {student['class']}")
                current = retakes.get(code, {})
                updates = {s: st.checkbox(s, value=current.get(s.lower(), False), key=f"retake_{s}") for s in SUBJECTS}
                if st.button("Save Retake", key="save_retake_btn"):
                    retakes[code] = {s.lower(): v for s, v in updates.items() if v}
                    set_retakes(retakes)
                    lb = [e for e in get_leaderboard() if e.get("access_code") != code]
                    set_leaderboard(lb)
                    st.success("✅ Retake updated.")

    # ==============================
    # 🖨️ Generate Access Slips
    # ==============================
    elif selected_tab == "🖨️ Generate Access Slips":
        if st.button("Generate ZIP", key="generate_zip_btn"):
            users = get_users()
            buffer = generate_access_slips(users)
            st.download_button("⬇️ Download ZIP", buffer, "AccessSlips.zip", key="download_slips")

    # ==============================
    # ♻️ Reset Tests (Super Admin Only)
    # ==============================
    elif selected_tab == "♻️ Reset Tests" and current_role == "super_admin":
        if st.button("Reset All Tests", key="reset_tests_btn"):
            reset_test()
            st.success("✅ Tests reset.")

    # ==============================
    # 🚪 Logout
    # ==============================
    elif selected_tab == "🚪 Logout":
        st.session_state["admin_logged_in"] = False
        st.success("Logged out.")
        st.rerun()
