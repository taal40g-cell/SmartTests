# ============================================
# app.py — SmartTest Admin (Full Clean Rewrite)
# ============================================
import json
import time
import pandas as pd
import streamlit as st

# === Local imports (adjust paths if your helper file lives elsewhere) ===
# Subject & utility helpers (from the helper module you created)
from ui import (
    CLASSES,
    excel_download_buffer,
    load_classes,style_admin_headers
)

# Models
from models import Leaderboard, Student,School,Subject,ArchivedQuestion,SubjectiveQuestion

# DB helpers
from db_helpers import (
    get_session,
    Question,
    get_all_admins,
    set_admin,
    verify_admin,
    add_student_db,
    get_student_by_access_code_db,
    add_question_db,
    reset_test,
    get_questions_db,
    update_student_db,
    delete_student_db,
    get_users,
    clear_students_db,
    load_subjects,
    save_subjects,
    clear_questions_db,
    clear_submissions_db,
    clear_progress,
    set_retake_db,
    get_retake_db,
    update_admin_password,
    bulk_add_students_db,
    delete_subject,
    handle_uploaded_questions,restore_question,
    ensure_super_admin_exists,archive_question,
    require_admin_login,assign_admin_to_school,delete_school,
    get_all_submissions_db,
    get_test_duration,get_current_school_id,
    set_test_duration,get_students_by_school,add_school,get_all_schools
)


def inject_tab_style():
    st.markdown("""
        <style>
        /* ======================================
           🌸 Sleek  Admin Tabs
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
            background-color: #f3f6f6 !important;     /* Soft neutral base */
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
            background-color: #7abaa1 !important;     /* Softer hover pink */
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
        "✍️ Add Subjective Questions",
        "🗑️ Delete Questions",
        "🗂️ Archive / Restore Questions",
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
        "🗂️ Archive / Restore Questions",
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
        "🗑️ Delete Questions",
        "🗂️ Archive / Restore Questions",
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

    # ==========================================
    # 🏫 Load School Context (Supports Super Admin)
    # ==========================================
    admin_role = st.session_state.get("admin_role", "")
    current_user = st.session_state.get("admin_username", "")

    school_id = None
    school_name = "No School Assigned"

    # 🔹 Super Admin can manage all schools
    if admin_role == "super_admin":

        schools = get_all_schools()  # could be tuples or ORM objects

        selected_school = st.selectbox(
            "Select School to Manage:",
            schools,
            format_func=lambda s: (
                s.name if hasattr(s, "name") else s[1] if isinstance(s, tuple) else str(s)
            )
        )

        if selected_school:
            # Handle tuple OR ORM object
            if isinstance(selected_school, tuple):
                school_id = selected_school[0]
                school_name = selected_school[1]
            else:
                school_id = selected_school.id
                school_name = selected_school.name

            # Save global
            st.session_state["school_id"] = school_id

    else:
        # ⭐ FIX: fallback to session_state if available
        school_id = st.session_state.get("school_id") or get_current_school_id()

        if not school_id:
            st.error("❌ No school ID found for current admin.")
            st.stop()

        db = get_session()
        try:
            school = db.query(School).filter_by(id=school_id).first()
            if school:
                school_name = school.name
        finally:
            db.close()

    # ==========================================
    # 🏫 Display School Header
    # ==========================================
    st.markdown(f"## 🏫 {school_name} — Admin Dashboard")
    st.caption(f"👤 Logged in as **{current_user} ({admin_role})**")
    st.divider()

    # ==========================================
    # 🎛️ Dashboard Navigation Tabs
    # ==========================================
    all_admins = get_all_admins(as_dict=True)
    current_role = all_admins.get(current_user, "admin")
    available_tabs = ROLE_TABS.get(current_role, ROLE_TABS["admin"])

    st.markdown(f"### ⚙️ {current_user} – {current_role}")

    # Layout grid
    cols_per_row = 4
    rows = [available_tabs[i:i + cols_per_row] for i in range(0, len(available_tabs), cols_per_row)]

    # Apply button CSS
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
        </style>
    """, unsafe_allow_html=True)

    # Track active tab
    if "selected_tab" not in st.session_state:
        st.session_state["selected_tab"] = available_tabs[0]

    # Draw tab buttons
    for row in rows:
        cols = st.columns(len(row))
        for i, tab_name in enumerate(row):
            with cols[i]:
                if st.button(tab_name, key=f"tab_{tab_name}", use_container_width=True):
                    st.session_state["selected_tab"] = tab_name
                    st.rerun()

    # Active tab
    selected_tab = st.session_state["selected_tab"]

    # Section title
    st.markdown(f"#### 🧭 Current Section: **{selected_tab}**")
    st.divider()

    # =====================================================
    # 🏫 Manage Schools (Super Admin Only)
    # =====================================================
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
                        school.get("name") if isinstance(school, dict) else "<unknown>"
                    )
                    st.success(f"✅ Added School: {sname}")

                    # Reset fields safely
                    st.session_state.update({
                        "add_school_name": "",
                        "add_school_code": ""
                    })

                    time.sleep(0.5)
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Failed to add school: {e}")

        st.markdown("---")
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

                if not st.session_state.confirm_delete:
                    if st.button("Delete Selected School", key="delete_school_btn"):
                        st.session_state.confirm_delete = True
                        st.session_state.school_to_delete = selected_school
                        st.rerun()

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

    # ======================================================
    # ➕ Add Student (Per School)
    # ======================================================
    elif selected_tab == "➕ Add User":
        st.session_state["mode"] = "admin"  # 🔒 Always lock admin mode
        st.subheader("➕ Add Student")

        # ✅ Determine school for this admin
        school_id = get_current_school_id()

        if admin_role == "super_admin":
            schools = get_all_schools()
            if schools:
                selected_school = st.selectbox(
                    "🏫 Select School",
                    schools,
                    format_func=lambda s: f"{s.name} (Code: {s.code})",
                    key="add_user_school"
                )
                school_id = selected_school.id
            else:
                st.warning("⚠️ No schools found. Please create one first.")
                st.stop()

        elif not school_id:
            st.error("❌ No school assigned to this admin. Please log in again or assign a school.")
            st.stop()

        # ✅ Student info input
        name = st.text_input("Student Name", key="add_name")
        class_name = st.selectbox("Class", CLASSES, key="add_class")

        if st.button("Add Student", key="add_student_btn"):
            st.session_state["mode"] = "admin"  # re-lock before db ops
            if not name.strip():
                st.error("❌ Please enter a valid student name.")
            elif not school_id:
                st.error("❌ Please select or assign a school first.")
            else:
                try:
                    student = add_student_db(name.strip(), class_name, school_id)
                    if hasattr(student, "name"):
                        st.success(
                            f"✅ {student.name} added successfully!\n\n"
                            f"School: {selected_school.name if admin_role == 'super_admin' else 'Current School'} | "
                            f"Class: {student.class_name} | "
                            f"Access Code: {student.access_code}"
                        )
                    else:
                        st.warning("⚠️ Student added, but details not fully returned.")
                except Exception as e:
                    st.error(f"❌ Error adding student: {e}")


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

        # Determine current role & school context (safe defaults)
        current_role = st.session_state.get("admin_role", "")
        current_school_id = get_current_school_id()

        # Super admin may pick a school to manage
        if current_role == "super_admin":
            schools = get_all_schools() or []
            if not schools:
                st.warning("⚠️ No schools exist yet. Please create one first.")
                st.stop()

            selected_school = st.selectbox(
                "🏫 Select School to View / Manage Students",
                schools,
                format_func=lambda s: f"{s.name} (ID: {s.id})",
                key="manage_students_school"
            )
            current_school_id = getattr(selected_school, "id", current_school_id)

        # final guard
        if not current_school_id:
            st.error("❌ No school selected or assigned. Please select a school.")
            st.stop()

        # -- Search / Filter UI --
        st.markdown("### 🔎 Search & Filter Students")
        search_q = st.text_input("Search by name, access code or class (leave empty to list all)",
                                 key="manage_students_search").strip()

        try:
            students = get_students_by_school(current_school_id) or []
        except Exception as e:
            st.error(f"❌ Failed to load students: {e}")
            st.stop()

        # Normalize students to DataFrame-friendly dicts
        df = pd.DataFrame(students)
        if df.empty:
            st.info("No students found for this school.")
            st.stop()

        # Apply search filter (case-insensitive)
        if search_q:
            q = search_q.lower()
            mask = (
                    df["name"].astype(str).str.lower().str.contains(q)
                    | df["access_code"].astype(str).str.lower().str.contains(q)
                    | df["class_name"].astype(str).str.lower().str.contains(q)
            )
            df_filtered = df[mask].copy()
        else:
            df_filtered = df.copy()

        # Show a compact table
        st.write(f"Showing {len(df_filtered)} / {len(df)} students")
        st.dataframe(df_filtered.reset_index(drop=True), use_container_width=True)

        # Select a student to edit
        st.markdown("### ✏️ Edit Selected Student")
        if df_filtered.empty:
            st.info("No students to edit.")
        else:
            # Use index selection for stable mapping
            selected_idx = st.selectbox(
                "Pick a student to edit",
                df_filtered.index.tolist(),
                format_func=lambda
                    i: f"{df_filtered.loc[i, 'name']} — {df_filtered.loc[i, 'access_code']} ({df_filtered.loc[i, 'class_name']})",
                key="manage_student_select_idx"
            )

            student_row = df_filtered.loc[selected_idx]
            selected_id = int(student_row["id"])

            st.write(f"Editing **{student_row['name']}** (Access: `{student_row['access_code']}`)")

            # Editable fields
            new_name = st.text_input("Update Name", value=str(student_row.get("name", "")).strip(), key="upd_name")
            # Class selector with safe index
            class_raw = str(student_row.get("class_name", "") or "").strip()
            normalized_classes = [c.strip() for c in CLASSES]
            try:
                class_index = normalized_classes.index(class_raw) if class_raw in normalized_classes else 0
            except Exception:
                class_index = 0
            new_class = st.selectbox("Update Class", normalized_classes, index=class_index, key="upd_class")

            # Subject (optional) — fall back to SUBJECTS list if available
            try:
                subjects = load_subjects()
            except Exception:
                subjects = SUBJECTS if "SUBJECTS" in globals() else []
            subject_raw = str(student_row.get("subject", "") or "").strip()
            if subjects:
                try:
                    subj_index = subjects.index(subject_raw) if subject_raw in subjects else 0
                except Exception:
                    subj_index = 0
                new_subject = st.selectbox("Update Subject (optional)", subjects, index=subj_index, key="upd_subject")
            else:
                new_subject = st.text_input("Subject (optional)", value=subject_raw, key="upd_subject_free")

            # Two-column actions
            col1, col2 = st.columns([1, 1])

            with col1:
                if st.button("💾 Save Changes", key="save_student_changes"):
                    try:
                        update_student_db(selected_id, new_name.strip(), new_class, new_subject)
                        st.success("✅ Student updated successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Failed to update student: {e}")

            # Delete flow with explicit confirmation
            with col2:
                if "delete_confirm_for" not in st.session_state:
                    st.session_state.delete_confirm_for = None

                if st.session_state.delete_confirm_for != selected_id:
                    if st.button("🗑️ Delete Student", key=f"delete_student_btn_{selected_id}"):
                        # set pending delete
                        st.session_state.delete_confirm_for = selected_id
                        st.rerun()
                else:
                    st.warning("⚠️ You're about to delete this student permanently. This action cannot be undone.")
                    confirm_col1, confirm_col2 = st.columns(2)
                    with confirm_col1:
                        if st.button("✅ Confirm Delete", key=f"confirm_delete_yes_{selected_id}"):
                            try:
                                delete_student_db(selected_id)
                                st.success("✅ Student deleted.")
                                st.session_state.delete_confirm_for = None
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Could not delete student: {e}")
                                st.session_state.delete_confirm_for = None
                    with confirm_col2:
                        if st.button("❌ Cancel", key=f"confirm_delete_no_{selected_id}"):
                            st.info("Deletion cancelled.")
                            st.session_state.delete_confirm_for = None
                            st.rerun()

        # Export the currently shown list
        st.markdown("---")
        if not df_filtered.empty:
            csv = df_filtered.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download Shown Students (CSV)", csv, f"students_school_{current_school_id}.csv",
                               "text/csv")

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
        current_role = st.session_state.get("admin_role", "")
        current_school_id = st.session_state.get("admin_school_id")

        old_pw = st.text_input("Current Password", type="password", key="old_pw")
        new_pw = st.text_input("New Password", type="password", key="new_pw")
        confirm_pw = st.text_input("Confirm New Password", type="password", key="confirm_pw")

        if st.button("Update Password", key="update_password_btn"):
            if not old_pw or not new_pw or not confirm_pw:
                st.error("❌ Please fill in all fields.")
            elif new_pw != confirm_pw:
                st.error("❌ New passwords do not match.")
            else:
                admin = verify_admin(current_user, old_pw, school_id=current_school_id)
                if admin:
                    success = update_admin_password(current_user, new_pw, school_id=current_school_id)
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

    # ============================================
    # ✍️ Add Subjective Questions
    # ============================================
    elif selected_tab == "✍️ Add Subjective Questions":
        st.subheader("✍️ Add Subjective Questions")

        # --- School Selection ---
        if admin_role == "super_admin":
            schools = get_all_schools()
            if not schools:
                st.warning("⚠️ No schools exist yet. Please create one first.")
                st.stop()
            selected_school = st.selectbox(
                "🏫 Select School",
                schools,
                format_func=lambda s: f"{s.name} ({s.code})"
            )
            school_id = selected_school.id
        else:
            school_id = get_current_school_id()
            if not school_id:
                st.error("❌ No school assigned. Please log in again.")
                st.stop()

        # --- Class & Subject Selection ---
        class_name = st.selectbox("Select Class", CLASSES)
        subjects = load_subjects(school_id=school_id)  # make sure this accepts school_id
        if not subjects:
            st.info("No subjects found for this school.")
            st.stop()
        subject = st.selectbox("Select Subject", subjects)

        # --- Option to Add New Subject ---
        with st.expander("➕ Add New Subject"):
            new_subject = st.text_input("Enter new subject name")
            new_class = st.selectbox("Select Class for Subject", CLASSES, key="add_subj_class")
            if st.button("💾 Save New Subject"):
                if not new_subject.strip():
                    st.error("Please enter a subject name.")
                else:
                    try:
                        db = get_session()
                        existing = (
                            db.query(Subject)
                            .filter_by(name=new_subject.strip(), class_name=new_class, school_id=school_id)
                            .first()
                        )
                        if existing:
                            st.warning("⚠️ Subject already exists for this class.")
                        else:
                            new_sub = Subject(
                                school_id=school_id,
                                name=new_subject.strip(),
                                class_name=new_class
                            )
                            db.add(new_sub)
                            db.commit()
                            st.success(f"✅ Added new subject '{new_subject.strip()}' for {new_class}")
                            st.rerun()
                    except Exception as e:
                        db.rollback()
                        st.error(f"❌ Error adding subject: {e}")
                    finally:
                        db.close()

        # --- Single Question Input ---
        st.markdown("### ➕ Add Single Question")
        question_text = st.text_area("📝 Question Text")
        marks = st.number_input("Marks", min_value=1, max_value=50, value=10)

        if st.button("💾 Save Single Question"):
            if not question_text.strip():
                st.error("Please enter a question.")
            else:
                try:
                    db = get_session()
                    new_q = SubjectiveQuestion(
                        school_id=school_id,
                        class_name=class_name,
                        subject=subject,
                        question_text=question_text.strip(),
                        marks=marks
                    )
                    db.add(new_q)
                    db.commit()
                    st.success(f"✅ Added subjective question for {class_name} - {subject}")
                    st.rerun()
                except Exception as e:
                    db.rollback()
                    st.error(f"❌ Error: {e}")
                finally:
                    db.close()

        # --- Bulk Upload ---
        st.markdown("### 📤 Bulk Upload Questions (JSON)")
        uploaded_file = st.file_uploader("Upload JSON file", type=["json"], key="subj_upload_file")
        if uploaded_file and st.button("✅ Upload Now", key="subj_upload_btn"):
            try:
                data = json.load(uploaded_file)
                if not isinstance(data, list):
                    st.error("⚠️ JSON must be a list of question objects.")
                    st.stop()

                cleaned = []
                for idx, q in enumerate(data, start=1):
                    if not all(k in q for k in ["question", "marks"]):
                        st.error(f"⚠️ Question {idx} missing required fields.")
                        st.stop()
                    cleaned.append({
                        "question_text": q["question"].strip(),
                        "marks": int(q["marks"])
                    })

                db = get_session()
                for item in cleaned:
                    new_q = SubjectiveQuestion(
                        school_id=school_id,
                        class_name=class_name,
                        subject=subject,
                        question_text=item["question_text"],
                        marks=item["marks"]
                    )
                    db.add(new_q)
                db.commit()
                st.success(f"🎯 Uploaded {len(cleaned)} subjective questions for {class_name} - {subject}")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Upload failed: {e}")
            finally:
                db.close()

        # --- Existing Questions ---
        st.markdown("---")
        st.subheader("📚 Existing Subjective Questions")
        db = get_session()
        existing = (
            db.query(SubjectiveQuestion)
            .filter_by(school_id=school_id)
            .order_by(SubjectiveQuestion.created_at.desc())
            .all()
        )

        if existing:
            for q in existing:
                st.markdown(f"**{q.class_name} - {q.subject}**")
                st.write(q.question_text)
                st.caption(f"Marks: {q.marks} | Added on {q.created_at.strftime('%Y-%m-%d')}")
        else:
            st.info("No subjective questions yet.")
        db.close()

    # =====================================================
    # 🗑️ DELETE QUESTIONS & DURATION
    # =====================================================
    elif selected_tab == "🗑️ Delete Questions":
        st.subheader("🗑️ Delete Question Sets or Subjects")

        # Resolve school_id robustly
        school_id = (
                st.session_state.get("school_id")
                or st.session_state.get("admin_school_id")
                or st.session_state.get("current_school_id")
                or get_current_school_id()
        )

        if not school_id:
            st.warning("⚠️ No school selected. Please assign/select a school first.")
            st.stop()

        cls = st.selectbox(
            "Select Class",
            CLASSES,
            key=f"delete_class_select_{school_id}"
        )

        # ✅ Load subjects safely
        sub_list = load_subjects(cls, school_id) if callable(load_subjects) else (
            load_subjects() if "load_subjects" in globals() else []
        )

        sub = st.selectbox(
            "Select Subject",
            sub_list,
            key=f"delete_subject_select_{school_id}_{cls}"
        )

        if cls and sub:
            from sqlalchemy import func
            db = get_session()
            try:
                # Count existing (scoped to school)
                existing_count = db.query(Question).filter(
                    func.lower(Question.class_name) == cls.strip().lower(),
                    func.lower(Question.subject) == sub.strip().lower(),
                    Question.school_id == school_id
                ).count()

                if existing_count:
                    st.info(f"📚 Found {existing_count} questions for {cls} - {sub} (School ID: {school_id})")

                    confirm = st.checkbox(
                        f"⚠️ Confirm deletion of all questions for {cls} - {sub}",
                        key=f"confirm_delete_questions_{school_id}_{cls}_{sub}"
                    )

                    if st.button(
                            "🗑️ Delete ALL Questions",
                            key=f"delete_all_questions_btn_{school_id}_{cls}_{sub}"
                    ):
                        if not confirm:
                            st.error("❌ Please confirm before deleting.")
                        else:
                            try:
                                deleted_count = db.query(Question).filter(
                                    func.lower(Question.class_name) == cls.strip().lower(),
                                    func.lower(Question.subject) == sub.strip().lower(),
                                    Question.school_id == school_id
                                ).delete(synchronize_session=False)
                                db.commit()
                                st.success(f"✅ Deleted {deleted_count} questions for {cls} - {sub}")
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                db.rollback()
                                st.error(f"❌ Error deleting questions: {e}")
                else:
                    st.warning(f"No questions found for {cls} - {sub} in this school (ID: {school_id}).")
            finally:
                db.close()


    # =====================================================
    # 🗂️ ARCHIVE / RESTORE QUESTIONS
    # =====================================================
    elif selected_tab == "🗂️ Archive / Restore Questions":
        st.subheader("🗂️ Archive or Restore Questions")

        db = get_session()
        try:
            # -----------------------------
            # Identify current school
            # -----------------------------
            school_id = (
                    st.session_state.get("school_id")
                    or st.session_state.get("admin_school_id")
                    or st.session_state.get("current_school_id")
                    or get_current_school_id()
            )
            if not school_id:
                st.warning("⚠️ No school selected.")
                st.stop()

            cls = st.selectbox("Select Class", CLASSES, key=f"archive_cls_{school_id}")

            # Load subject list
            if callable(load_subjects):
                sub_list = load_subjects(school_id)
            else:
                sub_list = []

            sub = st.selectbox("Select Subject", sub_list, key=f"archive_sub_{school_id}")
            show_archived = st.checkbox("👁️ Show Archived Questions", value=False)

            if cls and sub:
                from sqlalchemy import func

                if not show_archived:
                    # Active questions
                    questions = (
                        db.query(Question)
                        .filter(
                            func.lower(Question.class_name) == cls.lower(),
                            func.lower(Question.subject) == sub.lower(),
                            Question.school_id == school_id
                        )
                        .order_by(Question.id.asc())
                        .all()
                    )
                    st.info(f"Showing ACTIVE questions for {cls} - {sub}")

                    for q in questions:
                        with st.expander(f"Q{q.id}: {q.question_text[:70]}..."):
                            st.write(f"**Answer:** {q.answer}")
                            if st.button(f"🗃️ Archive Q{q.id}", key=f"archive_{q.id}"):
                                if archive_question(db, q.id):
                                    st.success(f"✅ Archived Q{q.id}")
                                    st.rerun()

                else:
                    # Archived questions
                    archived = (
                        db.query(ArchivedQuestion)
                        .filter(
                            func.lower(ArchivedQuestion.class_name) == cls.lower(),
                            func.lower(ArchivedQuestion.subject) == sub.lower(),
                            ArchivedQuestion.school_id == school_id
                        )
                        .order_by(ArchivedQuestion.archived_at.desc())
                        .all()
                    )
                    st.info(f"Showing ARCHIVED questions for {cls} - {sub}")

                    for aq in archived:
                        with st.expander(f"🗃️ Q{aq.id}: {aq.question_text[:70]}..."):
                            st.write(f"**Answer:** {aq.answer}")
                            st.write(f"**Archived At:** {aq.archived_at}")
                            if st.button(f"♻️ Restore Q{aq.id}", key=f"restore_{aq.id}"):
                                if restore_question(db, aq.id):
                                    st.success(f"♻️ Restored Q{aq.id}")
                                    st.rerun()

            # ===================
            # Download Archived CSV
            # ===================
            all_archived = db.query(ArchivedQuestion).filter(ArchivedQuestion.school_id == school_id).all()
            if all_archived:
                df = pd.DataFrame([
                    {
                        "Class": q.class_name,
                        "Subject": q.subject,
                        "Question": q.question_text,
                        "Answer": q.answer,
                        "Archived At": q.archived_at.strftime("%Y-%m-%d %H:%M:%S") if q.archived_at else ""
                    }
                    for q in all_archived
                ])
                st.download_button(
                    "📥 Download Archived Questions (CSV)",
                    df.to_csv(index=False).encode("utf-8"),
                    f"archived_questions_school_{school_id}.csv",
                    "text/csv",
                )
        except Exception as e:
            st.error(f"❌ Error: {e}")
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
    # 🏆 View Leaderboard
    # -----------------------
    elif selected_tab == "🏆 View Leaderboard":
        st.subheader("🏆 Leaderboard")

        # Admin’s school from session
        school_id = st.session_state.get("school_id", None)
        if not school_id:
            st.error("School information not found. Please log in again.")
            st.stop()

        filter_input = st.text_input("🔍 Search by Name, Access Code, or Class (optional)", key="lb_filter")
        top_n = st.selectbox("Show Top N Students", options=[5, 10, 20, 50, 100, "All"], index=1)

        db = get_session()
        try:
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
                search = filter_input.strip()
                df = df[
                    df["Student Name"].str.contains(search, case=False)
                    | df["Access Code"].str.contains(search, case=False)
                    | df["Class"].str.contains(search, case=False)
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

        code_input = st.text_input("Student Access Code", key="retake_code").strip().upper()
        if code_input:
            student = get_student_by_access_code_db(code_input)
            if not student:
                st.error("Invalid student code. Make sure the code exists.")
                st.stop()

            st.info(f"Student: {student.name} | Class: {student.class_name}")
            st.markdown("### Manage Retake Permissions")

            # Load subjects (each subject is a dict: {"id": X, "name": Y})
            subjects = load_subjects(school_id=student.school_id)
            if not subjects:
                st.warning("No subjects found for this school.")
                st.stop()

            toggle_all = st.checkbox("Allow All Subjects", key="toggle_all_retake")

            subject_permissions = {}

            for subj in subjects:
                subject_id = subj["id"]
                subject_name = subj["name"]

                # Load current DB permission (now expecting int)
                allow_in_db = get_retake_db(code_input, subject_id, school_id=student.school_id)

                # Convert DB value strictly to boolean
                current_allow = bool(allow_in_db)

                # Override if admin checked "Allow All"
                if toggle_all:
                    current_allow = True

                # Render checkbox using subject name
                subject_permissions[subject_id] = st.checkbox(
                    label=subject_name,
                    value=current_allow,
                    key=f"allow_retake_{subject_id}"
                )

            # SAVE BUTTON
            if st.button("💾 Save Changes", key="save_retake_btn"):
                for subj in subjects:
                    subject_id = subj["id"]

                    # Get checkbox value by subject_id
                    allow = subject_permissions.get(subject_id, False)

                    # Save retake permission
                    set_retake_db(
                        code_input,
                        subject_id,
                        can_retake=allow,
                        school_id=student.school_id
                    )

                    # If retake is enabled → clear old progress
                    if allow:
                        clear_progress(
                            access_code=code_input,
                            subject_id=subject_id,
                            school_id=student.school_id
                        )

                st.success(f"✅ Retake permissions updated for {student.name}.")


    # -----------------------
    # 🖨️ Generate Access Slips
    # -----------------------
    elif selected_tab == "🖨️ Generate Slips":
        st.subheader("🖨️ Generate Student Access Slips")
        # ✅ Role and school logic
        current_role = st.session_state.get("admin_role", "")
        current_school_id = st.session_state.get("admin_school_id", None)

        # Fetch users by role
        if current_role == "super_admin":
            users = get_users()
        else:
            users = get_users(school_id=current_school_id)

        # Debugging (optional — uncomment if needed)
        # st.write("DEBUG role:", current_role)
        # st.write("DEBUG school_id:", current_school_id)
        # st.write("DEBUG users count:", len(users))

        if not users:
            st.info("No students found for this school.")
        else:
            df = pd.DataFrame(users.values())

            # Clean up columns for clarity
            display_cols = ["name", "class_name", "access_code"]
            df_display = df[display_cols].rename(columns={
                "name": "Student Name",
                "class_name": "Class",
                "access_code": "Access Code"
            })

            # Show table
            st.dataframe(df_display, use_container_width=True)

            # 🧾 Generate downloadable CSV
            csv_data = df_display.to_csv(index=False).encode("utf-8")

            st.download_button(
                label="⬇️ Download Access Slips (CSV)",
                data=csv_data,
                file_name=f"access_slips_{current_school_id or 'all'}.csv",
                mime="text/csv"
            )

            st.success(f"✅ Generated {len(df_display)} access slips successfully!")
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
