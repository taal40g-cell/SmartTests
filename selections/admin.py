# ============================================
# app.py — SmartTest Admin (Full Clean Rewrite)
# ============================================

import json
import time
from datetime import datetime
import pandas as pd
import streamlit as st

# === Local imports (adjust paths if your helper file lives elsewhere) ===
# Subject & utility helpers (from the helper module you created)
from ui import (
    CLASSES,
    df_download_button,
    excel_download_buffer,
    is_archived,
    load_classes,style_admin_headers
)

# Models
from models import Leaderboard, Student,School,Subject

# DB helpers
from db_helpers import (
    get_session,
    Question,
    add_admin,
    get_all_admins,
    set_admin,
    verify_admin,
    add_student_db,
    save_questions_db,
    get_student_by_access_code_db,
    add_question_db,
    reset_test,
    get_questions_db,
    update_student_db,
    delete_student_db,
    get_submission_db,
    get_users,
    clear_students_db,
    load_subjects,
    save_subjects,
    clear_questions_db,
    clear_submissions_db,
    set_retake_db,
    preview_questions_db,
    count_questions_db,
    get_retake_db,
    update_admin_password,
    bulk_add_students_db,
    reset_student_retake_db,
    hash_password,delete_subject,
    handle_uploaded_questions,
    ensure_super_admin_exists,
    require_admin_login,assign_admin_to_school,delete_school,
    get_all_submissions_db,generate_unique_school_code,
    get_test_duration,get_current_school_id,get_or_select_school,
    set_test_duration,get_students_by_school,add_school,get_all_schools
)


def inject_tab_style():
    st.markdown("""
        <style>
        /* ======================================
           🌸 Sleek Rounded Pink Admin Tabs
        ====================================== */

        /* Tab container alignment */
        div[data-testid="stHorizontalBlock"] {
            justify-content: center !important;
            flex-wrap: wrap !important;
            gap: 8px !important;
            padding-top: 8px !important;
            padding-bottom: 10px !important;
        }

        /* Main tab button styling */
        div[data-testid="stHorizontalBlock"] button {
            background-color: #ff7e5a !important;     /* Soft neutral base */
            color: #0065a2 !important;
            border: none !important;
            border-radius: 50px !important;           /* ✅ Rounded pill look */
            padding: 8px 18px !important;
            min-width: 150px !important;              /* ✅ Uniform width */
            height: 40px !important;
            font-weight: 500 !important;
            font-size: 14px !important;
            transition: all 0.25s ease-in-out !important;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }

        /* Hover effect */
        div[data-testid="stHorizontalBlock"] button:hover {
            background-color: #ffb0b7 !important;     /* Softer hover pink */
            color: white !important;
            transform: translateY(-1px);
            box-shadow: 0 3px 6px rgba(0,0,0,0.15);
        }

        /* Active (selected) tab */
        div[data-testid="stHorizontalBlock"] button[data-baseweb="tab"][aria-selected="true"] {
            background-color: #ff828b !important;     /* 💗 Your color */
            color: white !important;
            font-weight: 600 !important;
            border-left: 4px solid #e46c75 !important; /* Slightly darker accent */
            box-shadow: 0 4px 8px rgba(0,0,0,0.25);
            transform: translateY(-1px);
        }

        /* Responsive fix for smaller screens */
        @media (max-width: 768px) {
            div[data-testid="stHorizontalBlock"] button {
                min-width: 120px !important;
                font-size: 13px !important;
                padding: 6px 14px !important;
            }
        }
        </style>
    """, unsafe_allow_html=True)

# ==============================
# Role tabs
# ==============================
ROLE_TABS = {
    "super_admin": [
        "🏫 Manage Schools",
        "➕ Add User",
        "📥 Students In Bulk",
        "👥 Manage Students",
        "🛡️ Manage Admins",
        "📚 Manage Subjects",
        "🔑 Change Password",
        "📤 Upload Questions",
        "🗑️ Delete Questions ",
        "🗂️ Archive Questions",
        "⏱ Set Duration",
        "🏆 View Leaderboard",
        "🔄 Allow Retake",
        "🖨️ Generate Slips",
        "♻️ Reset Tests",
        "📦 Data Export",
        "🚪 Logout"
    ],
    "admin": [
        "➕ Add User",
        "📥 Students In Bulk",
        "👥 Manage Students",
        "📚 Manage Subjects",
        "🔑 Change Password",
        "📤 Upload Questions",
        "🗑️ Delete Questions",
        "🗂️ Archive  Questions",
        "⏱ Set Duration",
        "🏆 View Leaderboard",
        "🔄 Allow Retake",
        "🖨️ Generate Slips",
        "♻️ Reset Tests",
        "🚪 Logout"
    ],
    "teacher": [
        "👥 Manage Students",
        "📚 Manage Subjects",
        "📤 Upload Questions",
        "🗑️ Delete Questions ",
        "🗂️ Archive  Questions",
        "🏆 View Leaderboard",
        "🚪 Logout"
    ],
    "moderator": [
        "🏆 View Leaderboard",
        "🚪 Logout"
    ]
}

# ==============================
# Admin UI
# ==============================
def run_admin_mode():
    if not require_admin_login():
        return
    inject_tab_style()
    style_admin_headers()
    # Load global lists for dropdowns
    CLASSES = load_classes() if 'load_classes' in globals() else ["JHS 1", "JHS 2", "JHS 3"]
    SUBJECTS = load_subjects() if 'load_subjects' in globals() else ["English", "Mathematics", "Science"]

    # ==============================
    # 🏫 Show Current School Context
    # ==============================
    current_school_id = get_current_school_id()
    school_id = current_school_id
    school_name = "Unknown School"

    if school_id:
        db = get_session()
        try:
            school = db.query(School).filter_by(id=school_id).first()
            if school:
                school_name = school.name
        finally:
            db.close()

    admin_role = st.session_state.get("admin_role", "")
    current_user = st.session_state.get("admin_username", "")

    # 💡 Display School Header
    st.markdown(f"## 🏫 {school_name} — Admin Dashboard")
    st.caption(f"👤 Logged in as **{current_user} ({admin_role})**")
    st.divider()


    # ==============================
    # 🎛️ Modern Dashboard Navigation
    # ==============================
    # ✅ Define admin role safely inside function
    admin_role = st.session_state.get("admin_role", "")
    current_user = st.session_state.get("admin_username", "")
    all_admins = get_all_admins(as_dict=True)

    current_role = all_admins.get(current_user, "admin")
    available_tabs = ROLE_TABS.get(current_role, ROLE_TABS["admin"])

    st.markdown(f"### ⚙️ Admin Panel ({current_user} – {current_role})")

    # --- Layout Settings ---
    cols_per_row = 4
    rows = [available_tabs[i:i + cols_per_row] for i in range(0, len(available_tabs), cols_per_row)]

    # --- Button Style (Global CSS once) ---
    st.markdown("""
        <style>
        div[data-testid="stButton"] > button {
            background-color: #f9f9f9;
            color: #333;
            border-radius: 10px;
            padding: 0.6em;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            border: none;
            font-weight: 500;
            font-size: 14px;
            transition: all 0.2s ease-in-out;
        }
        div[data-testid="stButton"] > button:hover {
            background-color: #007bff !important;
            color: white !important;
            transform: translateY(-2px);
        }
        .active-btn {
            background-color: #0066cc !important;
            color: white !important;
            font-weight: 600;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        </style>
    """, unsafe_allow_html=True)

    # --- Draw Buttons in Grid ---
    if "selected_tab" not in st.session_state:
        st.session_state["selected_tab"] = available_tabs[0]

    for row in rows:
        cols = st.columns(len(row))
        for i, tab_name in enumerate(row):
            active = st.session_state["selected_tab"] == tab_name
            btn_container = cols[i]
            with btn_container:
                if st.button(tab_name, key=f"tab_{tab_name}", use_container_width=True):
                    st.session_state["selected_tab"] = tab_name
                    st.rerun()
                # Apply active button styling using HTML marker
                if active:
                    st.markdown(
                        f"<style>div[data-testid='stButton'][key='tab_{tab_name}'] button{{background-color:#0066cc;color:white;font-weight:600;}}</style>",
                        unsafe_allow_html=True,
                    )

    # --- Get Selected Tab ---
    selected_tab = st.session_state["selected_tab"]

    # --- Show Current Section Title ---
    st.markdown(f"#### 🧭 Current Section: **{selected_tab}**")
    st.divider()
    st.title("🛠️ SmartTest — Admin Dashboard")

    # =====================================================
    # 🧭 ADMIN DASHBOARD — With Multi-School Management
    # =====================================================
    # -----------------------
    # 🏫 Manage Schools (Super Admin) + Delete Confirmation
    # -----------------------
    if selected_tab == "🏫 Manage Schools" and st.session_state.get("admin_role") == "super_admin":
        st.subheader("🏫 Manage Schools")

        # Load and normalize schools
        raw_schools = get_all_schools() or []

        def normalize_school(s):
            if isinstance(s, dict):
                return {"id": s.get("id"), "name": s.get("name"), "code": s.get("code", "")}
            return {"id": getattr(s, "id", None), "name": getattr(s, "name", None), "code": getattr(s, "code", "")}

        schools = [normalize_school(s) for s in raw_schools if s]
        schools = [s for s in schools if s["id"] is not None]

        if schools:
            df_schools = pd.DataFrame(schools).rename(columns={"id": "ID", "name": "Name", "code": "Code"})
            st.dataframe(df_schools, use_container_width=True)
        else:
            st.info("No schools found yet.")

        st.markdown("---")

        # -----------------------------
        # ➕ Add New School Section
        # -----------------------------
        st.markdown("### ➕ Add New School")
        new_school_name = st.text_input("School Name", key="add_school_name")
        new_school_code = st.text_input("School Code (optional)", key="add_school_code")

        if st.button("Add School", key="add_school_btn"):
            if not new_school_name.strip():
                st.error("Please enter a valid school name.")
            else:
                try:
                    school = add_school(new_school_name.strip(), code=(new_school_code or "").strip())
                    sname = getattr(school, "name", None) or (
                        school.get("name") if isinstance(school, dict) else "<unknown>")
                    st.success(f"✅ Added School: {sname}")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to add school: {e}")

        st.markdown("---")

        # -----------------------------
        # 🗑️ Delete School (with Search + Confirm)
        # -----------------------------
        st.markdown("### 🗑️ Delete School")
        if not schools:
            st.info("No schools available to delete.")
        else:
            search_q = st.text_input("Search School (name, code, or ID)", key="search_school").strip().lower()

            if search_q:
                filtered = [
                    s for s in schools
                    if (s["name"] and search_q in s["name"].lower())
                       or (s["code"] and search_q in s["code"].lower())
                       or (search_q.isdigit() and int(search_q) == int(s["id"]))
                ]
            else:
                filtered = schools

            if filtered:
                selected_school = st.selectbox(
                    "Select School to Delete",
                    filtered,
                    format_func=lambda s: f"{s['name']} (Code: {s['code']}) — ID:{s['id']}",
                    key="delete_school_select"
                )

                if "confirm_delete" not in st.session_state:
                    st.session_state.confirm_delete = False

                # Step 1: Show confirmation button
                if not st.session_state.confirm_delete:
                    if st.button("Delete Selected School", key="delete_school_btn"):
                        st.session_state.confirm_delete = True
                        st.session_state.school_to_delete = selected_school
                        st.rerun()

                # Step 2: Confirmation modal-like section
                elif st.session_state.confirm_delete:
                    school_info = st.session_state.school_to_delete
                    st.warning(
                        f"⚠️ Are you sure you want to permanently delete **{school_info['name']}** "
                        f"(ID: {school_info['id']})? This action **cannot be undone.**"
                    )

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Yes, Delete", key="confirm_delete_yes"):
                            try:
                                ok = delete_school(school_info["id"])
                                if ok:
                                    st.success(f"✅ '{school_info['name']}' deleted successfully.")
                                    st.session_state.confirm_delete = False
                                    time.sleep(0.8)
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to delete school.")
                            except Exception as e:
                                st.error(f"❌ Error deleting school: {e}")
                                st.session_state.confirm_delete = False
                    with col2:
                        if st.button("❌ Cancel", key="confirm_delete_cancel"):
                            st.session_state.confirm_delete = False
                            st.info("Deletion canceled.")
                            st.rerun()
            else:
                st.warning("No schools match your search.")


    # -----------------------
    # 📥 Bulk Add Students
    # -----------------------
    elif selected_tab == "📥 Students In Bulk":
        st.subheader("📥 Bulk Upload Students (CSV)")

        school_id = get_current_school_id()

        # ✅ Allow super_admin to pick a school
        if admin_role == "super_admin":
            schools = get_all_schools()

            if schools:
                selected_school = st.selectbox(
                    "🏫 Select School",
                    schools,
                    format_func=lambda s: f"{s.name} (Code: {s.code})",
                    key="bulk_school_select"
                )
                school_id = selected_school.id
            else:
                st.warning("⚠️ No schools exist yet. Please create one first.")
                st.stop()

        elif not school_id:
            st.error("❌ No school assigned to this admin. Please log in again or assign a school.")
            st.stop()

        # ✅ Choose class before uploading
        classes = ["JHS 1", "JHS 2", "JHS 3"]
        selected_class = st.selectbox("🏫 Select Class", classes, key="bulk_class_select")

        # ✅ Upload CSV File
        st.info("Upload CSV with column 'name' only. All students will be added to the selected class.")
        uploaded = st.file_uploader("Choose CSV File", type=["csv"], key="bulk_students")

        if uploaded:
            try:
                df = pd.read_csv(uploaded)

                # Validate column name
                if "name" not in df.columns:
                    st.error("❌ CSV must contain a 'name' column.")
                    st.stop()

                # Prepare student data — add class column automatically
                students_list = [(str(r["name"]).strip(), selected_class) for _, r in df.iterrows()]

                # ✅ Bulk insert
                result = bulk_add_students_db(students_list, school_id)

                # ✅ Display summary
                summary = result.get("summary", {})
                st.success(f"✅ {summary.get('new', 0)} new students added successfully to {selected_class}!")

                if summary.get("reused"):
                    st.info(f"♻️ {summary['reused']} existing students reused.")

                # ✅ Display list of added students
                for s in result.get("students", []):
                    icon = "✅" if s.get("status") == "new" else "♻️"
                    st.markdown(
                        f"{icon} **{s.get('name')}** | Class: {s.get('class_name')} | "
                        f"Access Code: `{s.get('access_code')}`"
                    )

                # ✅ Downloadable CSV of new students
                added_students = [s for s in result.get("students", []) if s.get("status") == "new"]
                if added_students:
                    df_added = pd.DataFrame(added_students)
                    csv_data = df_added.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "📥 Download Added Students CSV",
                        csv_data,
                        "bulk_added_students.csv",
                        "text/csv"
                    )

            except Exception as e:
                st.error(f"⚠️ Error processing CSV: {e}")

    # -----------------------
    # 👥 Manage Students
    # -----------------------
    elif selected_tab == "👥 Manage Students":
        st.subheader("👥 Manage Students")

        school_id = get_current_school_id()
        # Super admin can filter by school
        if current_role == "super_admin":
            schools = get_all_schools()
            if schools:
                selected_school = st.selectbox(
                    "🏫 Select School to View Students",
                    schools,
                    format_func=lambda s: f"{s.name} (ID: {s.id})",
                    key="manage_students_school"
                )
                current_school_id = selected_school.id
            else:
                st.warning("⚠️ No schools exist. Please create one first.")
                st.stop()

        if not current_school_id:
            st.error("❌ No school assigned.")
            st.stop()

        # Load students for that school
        users = get_students_by_school(current_school_id)
        if not users:
            st.info("No students found for this school.")
        else:
            df = pd.DataFrame(users)
            st.dataframe(df, use_container_width=True)

            selected_id = st.selectbox("Select Student ID", df["id"], key="manage_student_select")
            student = df[df["id"] == selected_id].iloc[0]

            st.write(f"✏️ Editing **{student['name']}** (Class: {student['class_name']})")
            new_name = st.text_input("Update Name", value=student["name"], key="upd_name")

            # ✅ Handle class name differences safely (spaces/case mismatches)
            class_name = str(student["class_name"]).strip()
            if class_name not in CLASSES:
                normalized_classes = [c.replace(" ", "").lower() for c in CLASSES]
                normalized_student = class_name.replace(" ", "").lower()
                index_class = normalized_classes.index(
                    normalized_student) if normalized_student in normalized_classes else 0
            else:
                index_class = CLASSES.index(class_name)

            new_class = st.selectbox("Update Class", CLASSES, index=index_class, key="upd_class")

            # ✅ Handle subject name differences safely (optional subject update)
            subject_name = str(student.get("subject", "")).strip()
            if subject_name not in SUBJECTS:
                normalized_subjects = [s.replace(" ", "").lower() for s in SUBJECTS]
                normalized_student_sub = subject_name.replace(" ", "").lower()
                index_subject = normalized_subjects.index(
                    normalized_student_sub) if normalized_student_sub in normalized_subjects else 0
            else:
                index_subject = SUBJECTS.index(subject_name)

            new_subject = st.selectbox("Update Subject", SUBJECTS, index=index_subject, key="upd_subject")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Save Changes", key="save_student_changes"):
                    update_student_db(selected_id, new_name.strip(), new_class, new_subject)
                    st.success("✅ Student updated successfully!")
                    st.rerun()
            with col2:
                if st.button("🗑️ Delete Student", key="delete_student_btn"):
                    delete_student_db(selected_id)
                    st.warning("⚠️ Student deleted.")
                    st.rerun()

            df_download_button(df, "⬇️ Download Students CSV", "students_backup.csv")

    # -----------------------
    # 🛡️ Manage Admins (super_admin only)
    # -----------------------
    elif selected_tab == "🛡️ Manage Admins" and current_role == "super_admin":
        st.header("🛡️ Manage Admins")

        # ✅ Step 1: Choose School First
        schools = get_all_schools()
        if not schools:
            st.warning("⚠️ No schools found. Please create a school first.")
            st.stop()

        selected_school = st.selectbox(
            "🏫 Select School",
            schools,
            format_func=lambda s: f"{s.name} (ID: {s.id})",
            key="manage_admin_school"
        )
        selected_school_id = selected_school.id

        # ✅ Step 2: Show Existing Admins for That School
        st.subheader(f"📋 Admins for {selected_school.name}")

        admins = get_all_admins()
        # filter by school_id if exists, else show all
        school_admins = [
            a for a in admins if getattr(a, "school_id", None) == selected_school_id
        ]

        if school_admins:
            df_admins = pd.DataFrame(
                [
                    {
                        "Username": a.username,
                        "Role": a.role,
                        "School": getattr(a, "school_name", selected_school.name)
                    }
                    for a in school_admins
                ]
            )
            st.dataframe(df_admins, use_container_width=True)
        else:
            st.info(f"ℹ️ No admins linked to {selected_school.name} yet.")

        # ✅ Step 3: Add / Update Admin
        st.subheader("➕ Add / Update Admin")
        new_user = st.text_input("👤 Username", key="admin_new_user")
        new_pass = st.text_input("🔑 Password", type="password", key="admin_new_pass")
        confirm_pass = st.text_input("🔑 Confirm Password", type="password", key="admin_confirm_pass")
        new_role = st.selectbox(
            "🎭 Role", ["admin", "teacher", "moderator", "super_admin"], key="admin_new_role"
        )

        if st.button("Add / Update Admin", key="add_update_admin_btn"):
            if not new_user.strip() or not new_pass:
                st.error("❌ Username & password required.")
            elif new_pass != confirm_pass:
                st.error("❌ Passwords do not match.")
            else:
                try:
                    ok = set_admin(new_user.strip(), new_pass.strip(), new_role)
                    if ok:
                        # ✅ Link admin to the selected school
                        assign_admin_to_school(new_user.strip(), selected_school_id)
                        st.success(
                            f"✅ Admin '{new_user}' added/updated and linked to {selected_school.name}."
                        )
                        st.rerun()
                    else:
                        st.error("❌ Failed to add or update admin.")
                except Exception as e:
                    st.error(f"⚠️ Error: {e}")

    elif selected_tab == "📚 Manage Subjects":
        st.subheader("📚 Manage Subjects")

        # Choose class
        selected_class = st.selectbox("Select Class", CLASSES, key="subject_class_select")

        # Load from DB each time
        db = get_session()
        school_id = get_current_school_id()
        subjects = (
            db.query(Subject.name)
            .filter(Subject.school_id == school_id, Subject.class_name.ilike(selected_class))
            .order_by(Subject.name.asc())
            .all()
        )
        db.close()
        subjects = [s[0] for s in subjects]

        st.write(f"### 📋 Subjects for {selected_class}")
        if subjects:
            for i, subj in enumerate(subjects):
                c1, c2 = st.columns([8, 1])
                c1.write(f"{i + 1}. {subj}")
                if c2.button("🗑️", key=f"del_subject_{i}"):
                    delete_subject(subj, school_id, selected_class)
                    st.rerun()
        else:
            st.info("No subjects found. Add new subjects below.")

        st.markdown("---")
        new_subject = st.text_input("➕ Add New Subject", key="new_subject_input")
        if st.button("Add Subject", key="add_subject_btn"):
            name = (new_subject or "").strip()
            if not name:
                st.warning("Enter a valid subject name.")
            elif name in subjects:
                st.info("Subject already exists.")
            else:
                subjects.append(name)
                save_subjects(sorted(subjects), selected_class)
                st.rerun()

        # 🔔 Persistent message (stays until next action)
        if "subject_msg" in st.session_state:
            msg_type, msg_text = st.session_state["subject_msg"]
            if msg_type == "error":
                st.error(msg_text)
            elif msg_type == "success":
                st.success(msg_text)

        st.caption("📚 Manage all subjects per class. Changes are saved to the central database.")

    # -----------------------
    # 🔑 Change Password
    # -----------------------
    elif selected_tab == "🔑 Change Password":
        st.subheader("Change Admin Password")
        current_user = st.session_state.get("admin_username")
        old_pw = st.text_input("Current Password", type="password", key="old_pw")
        new_pw = st.text_input("New Password", type="password", key="new_pw")
        confirm_pw = st.text_input("Confirm New Password", type="password", key="confirm_pw")

        if st.button("Update Password", key="update_password_btn"):
            if not old_pw or not new_pw or not confirm_pw:
                st.error("❌ Please fill in all fields.")
            elif new_pw != confirm_pw:
                st.error("❌ New passwords do not match.")
            else:
                admin = verify_admin(current_user, old_pw)
                if admin:
                    success = update_admin_password(current_user, new_pw)
                    if success:
                        st.success("✅ Password updated successfully.")
                        for i in range(3, 0, -1):
                            st.info(f"⏳ Logging out in {i}...")
                            time.sleep(1)
                        st.session_state["admin_logged_in"] = False
                        st.session_state["admin_username"] = None
                        st.session_state["admin_role"] = None
                        st.rerun()
                    else:
                        st.error("❌ Failed to update password. Try again.")
                else:
                    st.error("❌ Current password is incorrect.")

    # -----------------------
    # 📤 Upload Questions (Per School)
    # -----------------------
    elif selected_tab == "📤 Upload Questions":
        st.subheader("📤 Upload Questions to Database")
        school_id = get_current_school_id()

        # ✅ Super Admin can pick a school
        if admin_role == "super_admin":
            schools = get_all_schools()
            if schools:
                selected_school = st.selectbox(
                    "🏫 Select School",
                    schools,
                    format_func=lambda s: f"{s.name} (Code: {s.code})",
                    key="upload_school_select"
                )
                school_id = selected_school.id
            else:
                st.warning("⚠️ No schools exist yet. Please create one first.")
                st.stop()

        elif not school_id:
            st.error("❌ No school assigned. Please log in again or assign a school.")
            st.stop()

        # ✅ Display school context
        st.info(f"🏫 Active School ID: {school_id}")

        cls = st.selectbox("Select Class", CLASSES, key="upload_class")
        subjects = load_subjects()
        sub = st.selectbox("Select Subject", subjects, key="upload_subject")

        uploaded_file = st.file_uploader("📁 Upload Questions (JSON)", type=["json"], key="upload_file")

        if uploaded_file and st.button("✅ Upload Now", key="confirm_upload_btn"):
            try:
                # Parse JSON file
                data = json.load(uploaded_file)
                if not isinstance(data, list):
                    st.error("⚠️ Invalid format — must be a list of question objects.")
                    st.stop()

                # Clean & validate
                cleaned = []
                for idx, q in enumerate(data, start=1):
                    if not all(k in q for k in ["question", "options", "answer"]):
                        st.error(f"⚠️ Question {idx} missing required fields.")
                        st.stop()

                    cleaned.append({
                        "question": q["question"].strip(),
                        "options": [opt.strip() for opt in q["options"]],
                        "answer": q["answer"].strip()
                    })

                # ✅ Save questions to DB (scoped to school)
                result = handle_uploaded_questions(cls, sub, cleaned, school_id=school_id)

                if result.get("success"):
                    st.success(f"🎯 Uploaded {result['inserted']} new questions for {cls} - {sub}.")
                    st.cache_data.clear()
                    st.info(f"🏫 School ID: {school_id} — questions updated successfully.")
                    st.rerun()
                else:
                    st.error(f"❌ Upload failed: {result.get('error', 'Unknown error')}")

            except Exception as e:
                st.error(f"❌ Upload failed: {e}")

    elif selected_tab == "🗑️ Delete Questions & Duration":
        st.subheader("🗑️ Delete Question Sets or Subjects")

        cls = st.selectbox("Select Class", CLASSES, key="delete_class")

        school_id = (
                st.session_state.get("school_id")
                or st.session_state.get("admin_school_id")
                or st.session_state.get("current_school_id")
        )

        sub_list = load_subjects(school_id) if callable(load_subjects) else []
        sub = st.selectbox("Select Subject", sub_list, key="delete_subject")

        if not school_id:
            st.warning("⚠️ No school selected. Please assign a school before deleting.")
            st.stop()

        # -------------------------------
        # Delete all questions for subject
        # -------------------------------
        if cls and sub:
            from sqlalchemy import func
            db = get_session()
            try:
                existing = db.query(Question).filter(
                    func.lower(Question.class_name) == cls.strip().lower(),
                    func.lower(Question.subject) == sub.strip().lower(),
                    Question.school_id == school_id
                ).all()

                if existing:
                    st.info(f"📚 Found {len(existing)} questions for {cls} - {sub}")
                    confirm = st.checkbox(f"⚠️ Confirm deletion of all questions for {cls} - {sub}",
                                          key="confirm_delete_questions")

                    if st.button("🗑️ Delete ALL Questions", key="delete_all_questions_btn"):
                        if not confirm:
                            st.error("❌ Please confirm before deleting.")
                        else:
                            deleted_count = (
                                db.query(Question)
                                .filter(
                                    func.lower(Question.class_name) == cls.strip().lower(),
                                    func.lower(Question.subject) == sub.strip().lower(),
                                    Question.school_id == school_id
                                )
                                .delete(synchronize_session=False)
                            )
                            db.commit()
                            st.success(f"✅ Deleted {deleted_count} questions for {cls} - {sub}")
                            st.cache_data.clear()
                            st.rerun()
                else:
                    st.warning(f"No questions found for {cls} - {sub} in this school.")
            except Exception as e:
                db.rollback()
                st.error(f"❌ Error deleting questions: {e}")
            finally:
                db.close()

        st.markdown("---")

        # -------------------------------
        # Delete the subject itself
        # -------------------------------
        st.subheader("🗑️ Delete Subject")
        confirm_sub_del = st.checkbox(f"⚠️ Confirm deleting subject '{sub}' from {cls}", key="confirm_delete_subject")
        if st.button("🗑️ Delete Subject", key="delete_subject_btn"):
            if not confirm_sub_del:
                st.error("❌ Please confirm before deleting the subject.")
            else:
                deleted = delete_subject(sub, school_id, cls)

                if deleted:
                    st.success(f"✅ Deleted subject '{sub}' successfully.")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.warning(f"No subject named '{sub}' found or deletion failed.")

        # ==============================
    # 🗂️ Archive / Restore Questions
    # ==============================
    elif selected_tab == "🗂️ Archive / Restore Questions":
        st.subheader("🗂️ Archive or Restore Questions")
        cls = st.selectbox("Select Class", CLASSES, key="archive_cls")
        sub_list = load_subjects()
        sub = st.selectbox("Select Subject", sub_list, key="archive_sub")
        show_archived = st.checkbox("👁️ Show Archived Questions", value=False, key="archive_show")

        if cls and sub:
            questions = get_questions_db(cls, sub)
            total = len(questions)
            total_archived = sum(1 for q in questions if is_archived(q))
            total_active = total - total_archived
            st.info(f"📊 Total: {total} | ✅ Active: {total_active} | 💤 Archived: {total_archived}")
            filtered = [q for q in questions if is_archived(q) == show_archived]

            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗑️ Archive ALL Questions", key="bulk_archive_btn"):
                    db = get_session()
                    try:
                        updated = (
                            db.query(Question)
                            .filter(
                                Question.class_name == cls,
                                Question.subject == sub,
                                Question.archived.is_(False),
                            )
                            .update({"archived": True, "archived_at": datetime.now()})
                        )
                        db.commit()
                        st.success(f"🗃️ Archived {updated} questions.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Failed to archive: {e}")
                    finally:
                        db.close()

            with col2:
                if st.button("♻️ Restore ALL Archived", key="bulk_restore_btn"):
                    db = get_session()
                    try:
                        updated = (
                            db.query(Question)
                            .filter(
                                Question.class_name == cls,
                                Question.subject == sub,
                                Question.archived.is_(True),
                            )
                            .update({"archived": False, "archived_at": None})
                        )
                        db.commit()
                        st.success(f"♻️ Restored {updated} questions.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Failed to restore: {e}")
                    finally:
                        db.close()

            st.markdown("---")
            if not filtered:
                st.warning(f"No {'archived' if show_archived else 'active'} questions for {cls} - {sub}")
            else:
                for idx, q in enumerate(filtered):
                    q_id = getattr(q, "id", idx)
                    q_text = getattr(q, "question_text", "") or ""
                    q_answer = getattr(q, "correct_answer", "") or getattr(q, "answer", "")
                    q_options = getattr(q, "options", []) or []
                    q_archived = is_archived(q)
                    label = "♻️ Restore" if q_archived else "🗃️ Archive"
                    exp_title = f"Q{q_id}: {q_text[:60]}..." + (" 💤 [Archived]" if q_archived else "")
                    with st.expander(exp_title):
                        st.write(f"**Question:** {q_text}")
                        st.write(f"**Options:** {q_options}")
                        st.write(f"**Answer:** {q_answer}")
                        if st.button(label, key=f"archive_btn_{q_id}_{idx}"):
                            db = get_session()
                            try:
                                q_obj = db.query(Question).get(q_id)
                                if not q_obj:
                                    st.error(f"Question {q_id} not found.")
                                else:
                                    if q_archived:
                                        q_obj.archived = False
                                        q_obj.archived_at = None
                                        st.success(f"♻️ Question {q_id} restored.")
                                    else:
                                        q_obj.archived = True
                                        q_obj.archived_at = datetime.utcnow()
                                        st.success(f"🗃️ Question {q_id} archived.")
                                    db.commit()
                                    st.rerun()
                            finally:
                                db.close()

            # Download archived globally
            db = get_session()
            try:
                archived_all = db.query(Question).filter(Question.archived.is_(True)).order_by(
                    Question.class_name.asc(),
                    Question.subject.asc(),
                    Question.id.asc()
                ).all()
                if archived_all:
                    data_all = [
                        {
                            "ID": q.id,
                            "Class": q.class_name,
                            "Subject": q.subject,
                            "Question": q.question_text,
                            "Answer": getattr(q, "correct_answer", "") or getattr(q, "answer", ""),
                            "Options": ", ".join(q.options) if getattr(q, "options", None) else "",
                            "Archived At": q.archived_at.strftime("%Y-%m-%d %H:%M:%S") if q.archived_at else ""
                        }
                        for q in archived_all
                    ]
                    df_all = pd.DataFrame(data_all)
                    st.download_button(
                        "📥 Download ALL Archived Questions (CSV)",
                        df_all.to_csv(index=False).encode("utf-8"),
                        "all_archived_questions.csv",
                        "text/csv"
                    )
                else:
                    st.info("No archived questions found globally.")
            finally:
                db.close()

    # =======================================
    # ⏱️ Stand-alone Duration Configuration
    # =======================================
    elif selected_tab == "⏱ Set Duration":
        st.subheader("⏱ Set Test Duration Per Class & Subject")

        school_id = st.session_state.get("admin", {}).get("school_id", 1)
        class_name = st.selectbox("Select Class", CLASSES, key="dur_class")
        subject = st.selectbox("Select Subject", SUBJECTS, key="dur_subject")

        if class_name and subject:
            # Load current duration (seconds → minutes)
            current_duration_secs = get_test_duration(class_name, subject, school_id) or 0
            current_duration_mins = current_duration_secs // 60 if current_duration_secs > 0 else 0

            if current_duration_mins > 0:
                st.info(f"🕒 Current Duration: **{current_duration_mins} minutes**")
            else:
                st.info("No duration set yet — please enter one below.")

            # Input for new duration
            new_duration_mins = st.number_input(
                "Enter New Duration (minutes):",
                min_value=5,
                max_value=180,
                step=5,
                value=current_duration_mins or 30,
                key="new_duration_input"
            )
            # ------------------------------
            # Save Duration (with readable display)
            # ------------------------------
            if st.button("💾 Save Duration", key="save_duration_btn"):
                try:
                    # Save duration in DB (converted to seconds internally)
                    set_test_duration(class_name, subject, school_id, new_duration_mins)

                    # ✅ Make duration more readable
                    hours = new_duration_mins // 60
                    minutes = new_duration_mins % 60

                    if hours > 0 and minutes > 0:
                        readable_time = f"{hours} hour{'s' if hours > 1 else ''} {minutes} minute{'s' if minutes > 1 else ''}"
                    elif hours > 0:
                        readable_time = f"{hours} hour{'s' if hours > 1 else ''}"
                    else:
                        readable_time = f"{minutes} minute{'s' if minutes > 1 else ''}"

                    st.success(f"✅ Duration updated to **{readable_time}** for {class_name} - {subject}")

                except Exception as e:
                    st.error(f"❌ Failed to save duration: {e}")
            else:
                st.warning("Please select both class and subject to view or set duration.")

    # -----------------------
    # 🏆 Leaderboard (Multi-School Support)
    # -----------------------
    elif selected_tab == "🏆 View Leaderboard":
        st.subheader("🏆 Leaderboard")

        # ✅ Detect current admin’s school (from login/session)
        school_id = st.session_state.get("school_id", None)

        if not school_id:
            st.error("School information not found. Please log in again.")
            st.stop()

        filter_input = st.text_input("🔍 Search by Name, Access Code, or Class (optional)", key="lb_filter")
        top_n = st.selectbox("Show Top N Students", options=[5, 10, 20, 50, 100, "All"], index=1)

        db = get_session()
        try:
            # ✅ Filter leaderboard only for the logged-in admin’s school
            results = (
                db.query(Leaderboard, Student)
                .join(Student, Leaderboard.student_id == Student.id)
                .filter(Student.school_id == school_id)
                .order_by(Leaderboard.score.desc())
                .all()
            )

        finally:
            db.close()

        if not results:
            st.info("No leaderboard data available for this school yet.")
        else:
            df = pd.DataFrame([
                {
                    "Student Name": s.name,
                    "Access Code": s.access_code,
                    "Class": s.class_name,
                    "Subject": getattr(lb, "subject", "General"),
                    "Score": round(lb.score, 2),
                    "Submitted At": lb.submitted_at.strftime("%Y-%m-%d %H:%M:%S")
                } for lb, s in results
            ])

            if filter_input.strip():
                df = df[
                    df["Student Name"].str.contains(filter_input.strip(), case=False)
                    | df["Access Code"].str.contains(filter_input.strip(), case=False)
                    | df["Class"].str.contains(filter_input.strip(), case=False)
                    ]
                if df.empty:
                    st.warning("No matching records found.")

            subjects_present = sorted(df["Subject"].unique()) if "Subject" in df.columns else ["General"]
            tabs = st.tabs(subjects_present)
            for i, subject in enumerate(subjects_present):
                with tabs[i]:
                    df_sub = df[df["Subject"] == subject].sort_values(by="Score", ascending=False)
                    if top_n != "All":
                        df_sub = df_sub.head(int(top_n))
                    st.write(f"### 🧠 {subject} Leaderboard")
                    st.dataframe(df_sub, use_container_width=True)
                    st.download_button(
                        f"📥 Download {subject} CSV",
                        df_sub.to_csv(index=False).encode("utf-8"),
                        f"leaderboard_{subject.lower()}_{school_id}.csv",
                        "text/csv"
                    )

    # -----------------------
    # 🔄 Allow Retake
    # -----------------------
    elif selected_tab == "🔄 Allow Retake":
        st.subheader("🔄 Allow Retake Permission")
        code = st.text_input("Student Access Code", key="retake_code")
        if code:
            student = get_student_by_access_code_db(code)
            if not student:
                st.error("Invalid code.")
            else:
                st.info(f"Student: {student.name} | Class: {student.class_name}")
                st.markdown("### Manage Retake Permissions")
                toggle_all = st.checkbox("Toggle All Subjects", key="toggle_all_retake")
                subject_permissions = {}
                for subj in load_subjects():
                    current_allow = bool(get_retake_db(code, subj))
                    if toggle_all:
                        current_allow = True
                    subject_permissions[subj] = st.checkbox(subj, value=current_allow, key=f"allow_{subj}")
                if st.button("💾 Save All Changes", key="save_retake_btn"):
                    for subj, allow in subject_permissions.items():
                        set_retake_db(code, subj, allow)
                    st.success("✅ Retake permissions updated for all selected subjects.")

    # -----------------------
    # 🖨️ Generate Access Slips
    # -----------------------
    elif selected_tab == "🖨️ Generate Access Slips":
        st.subheader("🖨️ Generate Student Access Slips")
        users = get_users()
        if not users:
            st.info("No students found.")
        else:
            df = pd.DataFrame(users.values())
            st.dataframe(df, use_container_width=True)
            if st.button("📄 Generate Access Slips for All Students", key="generate_slips_btn"):
                slips_df = df[["name", "class_name", "access_code"]]
                csv_data = slips_df.to_csv(index=False).encode("utf-8")
                st.download_button("⬇️ Download Access Slips CSV", csv_data, "access_slips.csv", "text/csv")
                st.success(f"✅ Generated {len(slips_df)} access slips successfully!")

    # -----------------------
    # ♻️ Reset Tests (per student per school)
    # -----------------------
    elif selected_tab == "♻️ Reset Tests":
        st.subheader("♻️ Reset Student Test Status")

        # Super admin can choose which school to manage
        if current_role == "super_admin":
            schools = get_all_schools()
            if not schools:
                st.info("No schools found.")
            else:
                school_names = [s.name for s in schools]
                selected_school = st.selectbox("🏫 Select School", school_names, key="reset_school_select")
                school_obj = next(s for s in schools if s.name == selected_school)
                school_id = school_obj.id
        else:
            # For normal admin/teacher — only their school
            school_id = get_current_school_id()

        if not school_id:
            st.warning("⚠️ No school selected or assigned.")
        else:
            users = get_users(school_id=school_id)
            if users:
                student_codes = list(users.keys())
                student_options = [
                    f"{users[code]['name']} ({users[code]['class_name']})"
                    for code in student_codes
                ]
                selected_idx = st.selectbox(
                    "Select Student to Edit/Delete/Reset",
                    range(len(student_codes)),
                    format_func=lambda i: student_options[i],
                    key="reset_select"
                )

                selected_code = student_codes[selected_idx]
                selected_student = users[selected_code]

                st.write(f"✏️ Managing **{selected_student['name']}** (Class: {selected_student['class_name']})")

                new_name = st.text_input("Update Name", value=selected_student["name"], key="reset_new_name")
                new_class = st.selectbox(
                    "Update Class",
                    CLASSES,
                    index=CLASSES.index(selected_student["class_name"]) if selected_student[
                                                                               "class_name"] in CLASSES else 0,
                    key="reset_new_class"
                )

                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("💾 Save Changes", key="reset_save_btn"):
                        update_student_db(selected_code, new_name, new_class, school_id)
                        st.success("✅ Student updated successfully!")
                        st.rerun()
                with col2:
                    if st.button("🗑️ Delete Student", key="reset_delete_btn"):
                        delete_student_db(selected_code, school_id)
                        st.warning("⚠️ Student deleted.")
                        st.rerun()
                with col3:
                    if st.button("♻️ Reset Test Attempt", key="reset_attempt_btn"):
                        reset_test(selected_code, school_id)
                        st.info(f"🔄 Test status for {selected_student['name']} has been reset.")
                        st.rerun()
            else:
                st.info("No students found for this school.")

    # -----------------------
    # 📦 Data Export & Restore (super_admin + school_admin)
    # -----------------------
    elif selected_tab == "📦 Data Export":
        st.subheader("📦 Backup & Restore Database")

        current_role = st.session_state.get("admin_role", "")
        current_school_id = st.session_state.get("admin_school_id", None)

        if current_role not in ["super_admin", "school_admin"]:
            st.error("❌ Access denied. Only admins can use this feature.")
            st.stop()

        # -----------------------
        # 🔽 Export Current Data
        # -----------------------
        st.markdown("### 🔽 Export Current Data")

        # Fetch data based on role
        if current_role == "super_admin":
            students = get_users()
            subs = get_all_submissions_db()
        else:
            students = get_users(school_id=current_school_id)
            subs = get_all_submissions_db(school_id=current_school_id)

        # Students
        students_df = pd.DataFrame(students.values()) if students else pd.DataFrame()
        st.write(f"👥 Students: {len(students_df)} records")

        # Questions
        questions_list = []
        for cls in CLASSES:
            for sub in load_subjects():
                qs = get_questions_db(cls, sub, school_id=current_school_id if current_role == "school_admin" else None)
                if qs:
                    questions_list.extend(qs)

        questions_data = []
        for q in questions_list:
            questions_data.append({
                "id": getattr(q, "id", ""),
                "class_name": getattr(q, "class_name", ""),
                "subject": getattr(q, "subject", ""),
                "question_text": getattr(q, "question_text", "") or "",
                "options": getattr(q, "options", "") or "",
                "answer": getattr(q, "correct_answer", "") or getattr(q, "answer", ""),
                "school_id": getattr(q, "school_id", None)
            })
        questions_df = pd.DataFrame(questions_data) if questions_data else pd.DataFrame()
        st.write(f"❓ Questions: {len(questions_df)} records")

        # Submissions
        submissions_data = []
        if subs:
            for s in subs:
                submissions_data.append({
                    "Student": getattr(s, "student_name", ""),
                    "Class": getattr(s, "class_name", ""),
                    "Subject": getattr(s, "subject", ""),
                    "Score": getattr(s, "score", ""),
                    "Date": getattr(s, "timestamp", ""),
                    "school_id": getattr(s, "school_id", None)
                })
        submissions_df = pd.DataFrame(submissions_data) if submissions_data else pd.DataFrame()
        st.write(f"📝 Submissions: {len(submissions_df)} records")

        # -----------------------
        # 💾 Download Options
        # -----------------------
        col1, col2, col3 = st.columns(3)
        with col1:
            st.download_button("⬇️ Students CSV", students_df.to_csv(index=False), "students.csv")
        with col2:
            st.download_button("⬇️ Questions CSV", questions_df.to_csv(index=False), "questions.csv")
        with col3:
            st.download_button("⬇️ Submissions CSV", submissions_df.to_csv(index=False), "submissions.csv")

        excel_bytes = excel_download_buffer({
            "Students": students_df,
            "Questions": questions_df,
            "Submissions": submissions_df
        })
        st.download_button(
            "⬇️ Download All Data (Excel)",
            data=excel_bytes,
            file_name=f"smarttest_backup_{current_school_id or 'all'}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        full_backup = {
            "students": students,
            "questions": questions_data,
            "submissions": submissions_data
        }
        json_bytes = json.dumps(full_backup, indent=2).encode("utf-8")
        st.download_button(
            "⬇️ Full JSON Backup",
            json_bytes,
            f"smarttest_backup_{current_school_id or 'all'}.json",
            mime="application/json"
        )

        # -----------------------
        # 🔄 Restore From Backup
        # -----------------------
        st.markdown("---")
        st.markdown("### 🔄 Restore From Backup")

        uploaded_backup = st.file_uploader("Upload Backup JSON", type=["json"], key="restore_backup")

        if uploaded_backup:
            try:
                backup_data = json.load(uploaded_backup)
                st.info(f"Backup contains: {len(backup_data.get('students', []))} students, "
                        f"{len(backup_data.get('questions', []))} questions, "
                        f"{len(backup_data.get('submissions', []))} submissions.")

                st.warning("⚠️ Restoring will erase ALL current data for this school!")

                confirm = st.checkbox("✅ I understand and want to proceed", key="confirm_restore")

                # 🔒 Extra warning for super_admin (global restore)
                if current_role == "super_admin" and not current_school_id:
                    st.warning("⚠️ You are about to ERASE ALL SCHOOLS’ DATA permanently!")
                    global_confirm = st.checkbox("☑️ I understand this will delete ALL schools’ data",
                                                 key="confirm_global_wipe")
                else:
                    global_confirm = True

                if confirm and global_confirm and st.button("🔄 Confirm & Restore", key="confirm_restore_btn"):
                    # -----------------------
                    # Super Admin: Global Restore
                    # School Admin: Scoped Restore
                    # -----------------------
                    if current_role == "super_admin" and not current_school_id:
                        clear_students_db()
                        clear_questions_db()
                        clear_submissions_db()
                    else:
                        clear_students_db(school_id=current_school_id)
                        clear_questions_db(school_id=current_school_id)
                        clear_submissions_db(school_id=current_school_id)

                    # -----------------------
                    # 🧑‍🎓 Restore Students
                    # -----------------------
                    students_in = backup_data.get("students", {})
                    if isinstance(students_in, dict):
                        students_in = list(students_in.values())

                    for s in students_in:
                        add_student_db(
                            s.get("name", ""),
                            s.get("class_name", ""),
                            school_id=s.get("school_id") or current_school_id
                        )

                    # -----------------------
                    # ❓ Restore Questions
                    # -----------------------
                    for q in backup_data.get("questions", []):
                        try:
                            opts = q.get("options", [])
                            if isinstance(opts, str):
                                opts = json.loads(opts) if opts.startswith("[") else [x.strip() for x in opts.split(",")
                                                                                      if x.strip()]
                        except Exception:
                            opts = q.get("options", []) or []

                        add_question_db(
                            q.get("class_name", ""),
                            q.get("question_text", ""),
                            opts,
                            q.get("answer", ""),
                            school_id=q.get("school_id") or current_school_id
                        )

                    st.success("✅ Database restored successfully.")
                    st.balloons()
                    st.rerun()

            except Exception as e:
                st.error(f"❌ Failed to restore backup: {e}")

    # -----------------------
    # 🚪 Logout
    # -----------------------
    elif selected_tab == "🚪 Logout":
        st.session_state["admin_logged_in"] = False
        st.success("Logged out.")
        st.rerun()


# entrypoint
if __name__ == "__main__":
    ensure_super_admin_exists()
    run_admin_mode()
