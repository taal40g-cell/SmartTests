# ============================================
# app.py — SmartTest Admin (Full Clean Rewrite)
# ============================================
import time
import pandas as pd
import streamlit as st
from sqlalchemy.exc import IntegrityError
import re
# === Local imports (adjust paths if your helper file lives elsewhere) ===
# Subject & utility helpers (from the helper module you created)
from backend.security import hash_password, verify_password
from backend.ui import (


    load_classes,style_admin_headers
)

# Models
from backend.models import (Leaderboard,Student,School,Subject,ArchivedQuestion,Admin
,SubjectiveQuestion,ObjectiveQuestion,Class,StudentProgress,Retake)
from backend.helpers import get_objective_questions, get_subjective_questions
# DB helpers
from backend.db_helpers import (
    get_all_admins,
    set_admin,
    delete_admin,
    verify_admin,
    add_student_db,
    get_student_by_access_code,
    add_question_db,
    reset_test,
    update_student_db,
    delete_student_db,
    get_users,
    clear_students_db,
    load_subjects,
    clear_questions_db,
    clear_submissions_db,
    update_admin_password,
    bulk_add_students_db,
    delete_subject,require_permission,
    handle_uploaded_questions,restore_question,
    archive_question,get_all_schools,
    require_admin_login,delete_school,
    get_test_duration,get_current_school_id,add_submission_db,
    set_test_duration,get_students_by_school,add_school,
)

from backend.database import get_session


def format_school(s):
    if hasattr(s, "name") and hasattr(s, "code"):
        return f"{s.name} (Code: {s.code})"
    elif isinstance(s, tuple):
        return f"{s[1]} (Code: {s[2]})"
    return str(s)


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
# Role tabs (updated)
# ==============================
ROLE_TABS = {
    "super_admin": [
        "🏫 Manage Schools",
        "➕ Add Student",
        "📥 Students In Bulk",
        "👥 Manage Students",
        "🛡️ Manage Admins",
        "📚 Manage Subjects",
        "🔑 Change Password",
        "📤 Upload Questions",
        "✍️ Add Subjective Questions",
        "✍️ Review Subj Questions",   # <-- new tab
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
    "🛡️ Manage Admins",
    "➕ Add Student",
    "📥 Students In Bulk",
    "👥 Manage Students",
    "📚 Manage Subjects",
    "🔑 Change Password",
    "📤 Upload Questions",
    "✍️ Add Subjective Questions",
    "✍️ Review Subj Questions",
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
        "📤 Upload Questions",
        "✍️ Add Subjective Questions",
        "✍️ Review Subj Questions",
        "🏆 View Leaderboard",
        "🚪 Logout"
    ],
    "moderator": [
        "🏆 View Leaderboard",
        "🚪 Logout"
    ]
}


# ==============================
# Admin UI (CLEAN + STRICT)
# ==============================
def run_admin_mode():
    if not require_admin_login():
        return

    db = get_session()

    # ✅ PRE-DECLARE VARIABLES (fix warning)
    admin_role = None
    current_user = None
    selected_tab = None
    school_id = None

    try:
        inject_tab_style()
        style_admin_headers()

        admin_role = st.session_state.get("admin_role", "")
        current_user = st.session_state.get("admin_username", "")

        # ==========================================
        # 🏫 LOAD SCHOOL CONTEXT (NO UI FIRST)
        # ==========================================
        school_id = None
        school_name = "No School Selected"
        schools = []
        selected_school_obj = None

        if admin_role == "super_admin":

            if "school_id" not in st.session_state:
                st.session_state["school_id"] = None

            raw_schools = db.query(School).filter_by(is_system=False).all()

            if not raw_schools:
                st.warning("⚠️ No schools available. Please create one first.")
                st.stop()

            schools = [{"id": s.id, "name": s.name, "code": s.code} for s in raw_schools]

            # Resolve current school silently
            current_school_id = st.session_state.get("school_id")

            if not current_school_id:
                current_school_id = schools[0]["id"]
                st.session_state["school_id"] = current_school_id

            selected_school_obj = next(
                (s for s in schools if s["id"] == current_school_id),
                schools[0]
            )

            school_id = selected_school_obj["id"]
            school_name = selected_school_obj["name"]

        else:
            school_id = st.session_state.get("school_id")

            if not school_id:
                st.info("🚫 No school assigned to this admin.")
                st.stop()

            school = db.query(School).filter_by(id=school_id).first()

            if not school:
                st.info("🚫 Assigned school not found in database.")
                st.stop()

            school_name = school.name

        # ==========================================
        # 🏫 HEADER (ALWAYS TOP)
        # ==========================================
        if admin_role == "super_admin":
            code = selected_school_obj.get("code", "") if selected_school_obj else ""
            st.markdown(f"## 🏫 {school_name} ({code}) Super-Admin Dashboard")
        else:
            st.markdown(f"## 🏫 {school_name} Admin Dashboard")

        st.caption(f"👤 Logged in as **{current_user} ({admin_role})**")


        # ==========================================
        # 🎯 SCHOOL SELECTOR (AFTER HEADER)
        # ==========================================
        if admin_role == "super_admin":

            selected_school = st.selectbox(
                "🏫 Select School to Manage:",
                schools,
                index=[i for i, s in enumerate(schools) if s["id"] == school_id][0],
                format_func=lambda s: f"{s['name']} ({s['code']})"
            )

            new_school_id = selected_school["id"]

            if new_school_id != school_id:
                st.session_state["school_id"] = new_school_id
                st.session_state.pop("selected_class_id", None)
                st.session_state.pop("selected_student_id", None)
                st.rerun()



        # ==========================================
        # 📚 LOAD CLASSES
        # ==========================================
        CLASSES = db.query(Class).filter_by(school_id=school_id).all()

        # ==========================================
        # 🎛️ TABS
        # ==========================================
        all_admins = get_all_admins(as_dict=True)
        current_role = all_admins.get(current_user, "admin")
        available_tabs = ROLE_TABS.get(current_role, ROLE_TABS["admin"])

        # Track active tab
        if "selected_tab" not in st.session_state:
            st.session_state["selected_tab"] = available_tabs[0]

        cols_per_row = 4
        rows = [
            available_tabs[i:i + cols_per_row]
            for i in range(0, len(available_tabs), cols_per_row)
        ]

        # Styling
        st.markdown("""
            <style>
            div[data-testid="stButton"] > button {
                background-color: #f9f9f9;
                color: #333;
                border-radius: 10px;
                padding: 0.6em;
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

        # Render tabs
        for row in rows:
            cols = st.columns(len(row))
            for i, tab_name in enumerate(row):
                with cols[i]:
                    if st.button(tab_name, key=f"tab_{tab_name}", use_container_width=True):
                        st.session_state["selected_tab"] = tab_name
                        st.rerun()

        selected_tab = st.session_state["selected_tab"]
        st.markdown(f"#### 🧭 Current Section: **{selected_tab}**")


    # ✅ CLOSE TRY BLOCK HERE
    except Exception as e:
        st.error(f"🚫 Admin error: {e}")
        return




    # =====================================================
    # 🏫 Manage Schools (Super Admin Only)
    # =====================================================
    if selected_tab == "🏫 Manage Schools" and admin_role == "super_admin":
        st.subheader("🏫 Manage Schools")

        schools = [s for s in get_all_schools() if not s.is_system]

        if schools:
            df_schools = pd.DataFrame([
                {"ID": s.id, "Name": s.name, "Code": s.code}
                for s in schools
            ])
            st.dataframe(df_schools, use_container_width=True)
        else:
            st.info("No schools found yet.")

        # ➕ Add School
        st.markdown("### ➕ Add New School")

        with st.form("add_school_form", clear_on_submit=True):
            new_school_name = st.text_input("School Name")
            new_school_code = st.text_input("School Code (optional)")
            submitted = st.form_submit_button("Add School")

        if submitted:
            if not new_school_name.strip():
                st.error("Please enter a valid school name.")
            else:
                try:
                    school = add_school(
                        new_school_name.strip(),
                        code=(new_school_code or "").strip()
                    )
                    st.success(f"✅ Added School: {school.name} — ID {school.id}")
                    st.rerun()
                except Exception as e:
                    st.error(f"🚫 Failed to add school: {e}")

        # 🗑️ Delete School
        st.markdown("---")
        st.markdown("### 🗑️ Delete School")

        if not schools:
            st.info("No schools available to delete.")
            st.stop()

        search_q = st.text_input("Search School", key="search_school").strip().lower()

        filtered = [
            s for s in schools
            if not search_q
               or (s.name and search_q in s.name.lower())
               or (s.code and search_q in s.code.lower())
               or (search_q.isdigit() and int(search_q) == s.id)
        ]

        if filtered:
            selected_school = st.selectbox(
                "Select School to Delete",
                filtered,
                format_func=lambda s: f"{s.name} (Code: {s.code}) — ID {s.id}"
            )

            if st.button("Delete Selected School"):
                try:
                    # 🚨 SAFETY: prevent deleting currently active school
                    active_school_id = st.session_state.get("school_id")

                    if selected_school.id == active_school_id:
                        st.error("🚫 Cannot delete the currently active school.")
                        st.stop()

                    ok = delete_school(selected_school.id)

                    if ok:
                        st.success(f"✅ '{selected_school.name}' deleted.")
                        st.rerun()
                    else:
                        st.error("🚫 Failed to delete school.")

                except Exception as e:
                    st.error(f"🚫 Error deleting school: {e}")

            else:
                st.warning("No schools match your search.")




    # ======================================================
    # ➕ Add Student (Per School) — FULLY SYNCED
    # ======================================================
    elif selected_tab == "➕ Add Student":

        st.session_state["mode"] = "admin"
        st.subheader("➕ Add Student")

        # --------------------------------------------------
        # 🏫 SCHOOL (Single Source of Truth)
        # --------------------------------------------------
        school_id = st.session_state.get("school_id")

        if not school_id:
            st.warning("⚠️ No school selected.")
            st.stop()

        school_obj = db.query(School).filter_by(id=school_id).first()

        if not school_obj:
            st.error("🚫 Selected school not found in database.")
            st.stop()

        selected_school_name = school_obj.name

        # Optional: show current school context
        st.info(f"🏫 Current School: {selected_school_name}")

        # --------------------------------------------------
        # 👤 STUDENT NAME
        # --------------------------------------------------
        name = st.text_input("Student Name", key="add_name")

        # --------------------------------------------------
        # 📚 CLASS (Filtered by Selected School)
        # --------------------------------------------------
        classes_orm = db.query(Class).filter_by(school_id=school_id).all()

        if not classes_orm:
            st.warning("⚠️ No classes found for this school.")
            st.stop()

        class_lookup = {c.id: c.name for c in classes_orm}

        selected_class_id = st.selectbox(
            "Class",
            list(class_lookup.keys()),
            format_func=lambda cid: class_lookup[cid],
            key="add_class"
        )

        # --------------------------------------------------
        # 🚀 SUBMIT
        # --------------------------------------------------
        if st.button("Add Student", key="add_student_btn"):

            if not name.strip():
                st.info("🚫 Please enter a valid student name.")
                st.stop()

            try:
                student = add_student_db(
                    name=name.strip(),
                    class_id=selected_class_id,
                    school_id=school_id
                )

                st.success(
                    f"✅ {student['name']} added successfully!\n\n"
                    f"School: {selected_school_name}\n"
                    f"Class: {class_lookup[selected_class_id]}\n"
                    f"Unique ID: {student['unique_id']}\n"
                    f"Access Code: {student['access_code']}"
                )

            except Exception as e:
                st.error(f"🚫 Error adding student: {e}")



    # -----------------------
    # 📥 Bulk Add Students
    # -----------------------
    elif selected_tab == "📥 Students In Bulk":

        st.subheader("📥 Bulk Upload Students (CSV)")

        # --------------------------------------------------
        # 🏫 SCHOOL (Single Source of Truth)
        # --------------------------------------------------
        school_id = st.session_state.get("school_id")

        if not school_id:
            st.warning("⚠️ No school selected.")
            st.stop()

        school_obj = db.query(School).filter_by(id=school_id).first()

        if not school_obj:
            st.error("🚫 Selected school not found in database.")
            st.stop()


        st.info(f"🏫 Current School: {school_obj.name}")

        # --------------------------------------------------
        # 📚 CLASS (Filtered by Selected School)
        # --------------------------------------------------

        classes = db.query(Class).filter_by(school_id=school_id).all()

        if not classes:
            st.warning("⚠️ No classes found for this school.")
            st.stop()

        # Keep IDs as integers
        class_lookup = {c.id: c.name for c in classes}

        # Reset stale selection if school changed
        if "bulk_class_select" in st.session_state:
            if st.session_state.bulk_class_select not in class_lookup:
                del st.session_state.bulk_class_select


        selected_class_id = st.selectbox(
            "🏫 Select Class",
            options=list(class_lookup.keys()),
            format_func=lambda cid: class_lookup[cid],
            key="bulk_class_select"
        )

        # --------------------------------------------------
        # 📄 CSV Upload
        # --------------------------------------------------
        st.info("Upload CSV with column 'name' only. All students will be added to the selected class.")

        uploaded = st.file_uploader(
            "Choose CSV File",
            type=["csv"],
            key="bulk_students_csv"
        )

        if uploaded:
            try:
                df = pd.read_csv(uploaded)

                if "name" not in df.columns:
                    st.error("🚫 CSV must contain a 'name' column.")
                    st.stop()

                students_list = []

                for _, r in df.iterrows():
                    raw_name = r.get("name")

                    if isinstance(raw_name, str):
                        clean_name = raw_name.strip()
                        if clean_name:
                            students_list.append((clean_name, selected_class_id))

                if not students_list:
                    st.warning("⚠️ No valid student names found in file.")
                    st.stop()

                result = bulk_add_students_db(
                    students_list,
                    school_id
                )

                summary = result["summary"]

                st.success(
                    f"✅ {summary['new']} new students added to "
                    f"{class_lookup[selected_class_id]}"
                )

            except Exception as e:
                st.error(f"⚠️ Error processing CSV: {e}")


    # -----------------------
    # 👥 Manage Students
    # -----------------------
    elif selected_tab == "👥 Manage Students":

        st.subheader("👥 Manage Students")

        # --------------------------------------------------
        # 🏫 SCHOOL (Single Source of Truth)
        # --------------------------------------------------
        school_id = st.session_state.get("school_id")

        if not school_id:
            st.warning("⚠️ No school selected.")
            st.stop()

        school_obj = db.query(School).filter_by(id=school_id).first()

        if not school_obj:
            st.error("🚫 Selected school not found.")
            st.stop()

        st.info(f"🏫 Current School: {school_obj.name}")

        # --------------------------------------------------
        # 🔎 Search & Filter
        # --------------------------------------------------
        st.markdown("### 🔎 Search & Filter Students")

        search_q = st.text_input(
            "Search by name, access code or class ID (leave empty to list all)",
            key="manage_students_search"
        ).strip()

        try:
            students = get_students_by_school(school_id) or []
        except Exception as e:
            st.error(f"🚫 Failed to load students: {e}")
            st.stop()

        df = pd.DataFrame([
            {
                "id": s.get("id"),
                "name": s.get("name", ""),
                "access_code": s.get("access_code", ""),
                "class_id": s.get("class_id", 0),
                "subject": s.get("subject", "")
            }
            for s in students
        ])

        if df.empty:
            st.info("🚫 No students found for this school.")
            st.stop()

        if search_q:
            q = search_q.lower()
            mask = (
                    df["name"].astype(str).str.lower().str.contains(q)
                    | df["access_code"].astype(str).str.lower().str.contains(q)
                    | df["class_id"].astype(str).str.contains(q)
            )
            df_filtered = df[mask].copy()
        else:
            df_filtered = df.copy()

        st.write(f"Showing {len(df_filtered)} / {len(df)} students")
        st.dataframe(df_filtered.reset_index(drop=True), use_container_width=True)

        # --------------------------------------------------
        # ✏️ Edit Student
        # --------------------------------------------------
        st.markdown("### ✏️ Edit Selected Student")

        if not df_filtered.empty:

            selected_idx = st.selectbox(
                "Pick a student to edit",
                df_filtered.index.tolist(),
                format_func=lambda i: (
                    f"{df_filtered.loc[i, 'name']} — "
                    f"{df_filtered.loc[i, 'access_code']} "
                    f"(Class ID: {df_filtered.loc[i, 'class_id']})"
                ),
                key="manage_student_select_idx"
            )

            student_row = df_filtered.loc[selected_idx]
            selected_id = int(student_row["id"])

            st.write(f"Editing **{student_row['name']}** (Access: `{student_row['access_code']}`)")

            # Name
            new_name = st.text_input(
                "Update Name",
                value=str(student_row.get("name", "")).strip(),
                key="upd_name"
            )

            # --------------------------------------------------
            # 📚 Class (Synced to School)
            # --------------------------------------------------
            classes = db.query(Class).filter_by(school_id=school_id).all()

            if not classes:
                st.warning("⚠️ No classes found for this school.")
                st.stop()

            class_map = {c.id: c.name for c in classes}
            current_class_id = int(student_row.get("class_id") or 0)

            new_class_id = st.selectbox(
                "Update Class",
                options=list(class_map.keys()),
                index=list(class_map.keys()).index(current_class_id)
                if current_class_id in class_map else 0,
                format_func=lambda cid: f"ID {cid} — {class_map[cid]}",
                key="upd_class"
            )

            try:
                subjects = db.query(Subject).filter_by(school_id=school_id).all()
            except Exception:
                subjects = []

            subject_raw = str(student_row.get("subject", "") or "").strip()

            if subjects:

                # Map name → object
                subject_map = {s.name: s for s in subjects}

                # Determine default selected subject object
                default_subject_obj = subject_map.get(subject_raw)

                new_subject_obj = st.selectbox(
                    "Update Subject (optional)",
                    subjects,
                    index=subjects.index(default_subject_obj)
                    if default_subject_obj in subjects else 0,
                    format_func=lambda s: s.name,  # 👈 THIS FIXES DISPLAY
                    key="upd_subject"
                )

                new_subject = new_subject_obj.name  # Save only the name

            else:
                new_subject = st.text_input(
                    "Subject (optional)",
                    value=subject_raw,
                    key="upd_subject_free"
                )


            # --------------------------------------------------
            # Actions
            # --------------------------------------------------
            col1, col2 = st.columns(2)

            # Save
            with col1:
                if st.button("💾 Save Changes", key="save_student_changes"):
                    try:
                        update_student_db(
                            selected_id,
                            new_name.strip(),
                            new_class_id,
                            new_subject
                        )
                        st.success("✅ Student updated successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"🚫 Failed to update student: {e}")

            # Delete
            with col2:
                if "delete_confirm_for" not in st.session_state:
                    st.session_state.delete_confirm_for = None

                if st.session_state.delete_confirm_for != selected_id:
                    if st.button("🗑️ Delete Student", key=f"delete_student_btn_{selected_id}"):
                        st.session_state.delete_confirm_for = selected_id
                        st.rerun()
                else:
                    st.warning("⚠️ This action cannot be undone.")

                    confirm_col1, confirm_col2 = st.columns(2)

                    with confirm_col1:
                        if st.button("✅ Confirm Delete", key=f"confirm_delete_yes_{selected_id}"):
                            try:
                                success = delete_student_db(selected_id, school_id)
                                if success:
                                    st.success("✅ Student deleted.")
                                else:
                                    st.error("🚫 Student could not be deleted.")
                                st.session_state.delete_confirm_for = None
                                st.rerun()
                            except Exception as e:
                                st.error(f"🚫 Could not delete student: {e}")
                                st.session_state.delete_confirm_for = None

                    with confirm_col2:
                        if st.button("🚫 Cancel", key=f"confirm_delete_no_{selected_id}"):
                            st.session_state.delete_confirm_for = None
                            st.rerun()

        # --------------------------------------------------
        # Export
        # --------------------------------------------------
        st.markdown("---")

        if not df_filtered.empty:
            csv = df_filtered.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download Shown Students (CSV)",
                csv,
                f"students_school_{school_id}.csv",
                "text/csv"
            )



    # -----------------------
    # 🛡️ Manage Admins (super_admin only)
    # -----------------------
    elif selected_tab == "🛡️ Manage Admins" and current_role in ["super_admin", "admin"]:

        st.header("🛡️ Manage Admins")

        # --------------------------------------------------
        # 🏫 SCHOOL (Single Source of Truth)
        # --------------------------------------------------
        school_id = st.session_state.get("school_id")

        if not school_id:
            st.warning("⚠️ No school selected.")
            st.stop()

        school_obj = db.query(School).filter_by(id=school_id).first()

        if not school_obj:
            st.error("🚫 Selected school not found.")
            st.stop()

        st.info(f"🏫 Managing admins for: {school_obj.name}")

        # --------------------------------------------------
        # 📋 Existing Admins
        # --------------------------------------------------
        st.subheader(f"📋 Admins for {school_obj.name}")

        admins = get_all_admins()

        school_admins = [
            a for a in admins
            if getattr(a, "school_id", None) == school_id
        ]

        if school_admins:

            for a in school_admins:

                with st.container(border=True):

                    st.markdown(f"### 👤 {a.username}")
                    st.write(f"🆔 ID: {a.id}")
                    st.write(f"🎭 Role: {a.role}")

                    col1, col2, col3 = st.columns(3)

                    # -------------------------
                    # 🔑 RESET PASSWORD
                    # -------------------------
                    with col1:
                        if st.button("🔑 Reset Password", key=f"reset_{a.id}"):
                            import secrets
                            temp_password = secrets.token_hex(4)

                            a.password_hash = hash_password(temp_password)
                            db.commit()

                            st.success(f"New password: {temp_password}")


                    # -------------------------
                    # ✏️ CHANGE ROLE
                    # -------------------------
                    with col2:
                        new_role = st.selectbox(
                            "Role",
                            ["admin", "teacher", "moderator"],
                            index=["admin", "teacher", "moderator"].index(a.role)
                            if a.role in ["admin", "teacher", "moderator"] else 0,
                            key=f"role_{a.id}"
                        )

                        if st.button("💾 Update Role", key=f"role_update_{a.id}"):
                            a.role = new_role
                            db.commit()
                            st.success("Role updated")
                            st.rerun()



                    # -------------------------
                    # 🗑️ DELETE
                    # -------------------------
                    with col3:
                        if st.button("🗑️ Delete", key=f"del_{a.id}"):

                            current_username = st.session_state.get("admin_username")
                            current_role = st.session_state.get("admin_role")

                            # 🚫 Prevent self deletion
                            if a.username == current_username:
                                st.toast("🚫 You cannot delete your own account.")
                                st.stop()

                            # 🚫 Prevent deleting super admin
                            if a.role == "super_admin":
                                st.toast("🚫 Super Admin cannot be deleted.")
                                st.stop()

                            # 🚫 Admin cannot delete other admins
                            if current_role == "admin" and a.role == "admin":
                                st.toast("🚫 You cannot delete another admin.")
                                st.stop()

                            # 🚫 Prevent deleting last admin in school
                            admin_count = db.query(Admin).filter(
                                Admin.school_id == school_id,
                                Admin.role == "admin"
                            ).count()


                            if a.role == "admin" and admin_count <= 1:
                                st.toast("🚫 Cannot delete the last admin in this school.", icon="🚫")
                                st.stop()

                            # ✅ Safe to delete
                            db.delete(a)
                            db.commit()

                            st.success("✅ User deleted successfully")
                            st.rerun()


            # ----------------------------
            # 🗑️ Delete Admin
            # ----------------------------
            st.subheader("🗑️ Delete Admin")

            delete_id = st.number_input(
                "Enter Admin ID to delete",
                min_value=1,
                step=1,
                key="delete_admin_id"
            )
            if st.button("Delete Admin", key="delete_admin_btn"):

                target = db.query(Admin).filter_by(id=delete_id).first()

                if not target:
                    st.error("🚫 Admin not found.")
                    st.stop()

                if target.school_id != school_id:
                    st.error("🚫 This admin does not belong to this school.")
                    st.stop()

                current_username = st.session_state.get("admin_username")
                current_role = st.session_state.get("admin_role")

                # 🚫 Self delete
                if target.username == current_username:
                    st.error("🚫 You cannot delete your own account.")
                    st.stop()

                # 🚫 Super admin protection
                if target.role == "super_admin":
                    st.error("🚫 Super Admin cannot be deleted.")
                    st.stop()

                # 🚫 Admin restriction
                if current_role == "admin" and target.role == "admin":
                    st.toast("🚫 Cannot delete the last admin in this school.", icon="🚫")
                    st.stop()
                # 🚫 Last admin protection
                admin_count = db.query(Admin).filter(
                    Admin.school_id == school_id,
                    Admin.role == "admin"
                ).count()

                if target.role == "admin" and admin_count <= 1:
                    st.error("🚫 Cannot delete the last admin in this school.")
                    st.stop()

                # ✅ Delete
                db.delete(target)
                db.commit()

                st.success(f"✅ Admin '{target.username}' deleted successfully.")
                st.rerun()
        # --------------------------------------------------
        # ➕ Add / Update Admin
        # --------------------------------------------------
        st.subheader("➕ Add / Update Admin")

        new_user = st.text_input("👤 Username", key="admin_new_user")
        new_pass = st.text_input("🔑 Password", type="password", key="admin_new_pass")
        confirm_pass = st.text_input("🔑 Confirm Password", type="password", key="admin_confirm_pass")

        # 🎯 Role assignment based on who is logged in
        if current_role == "super_admin":
            available_roles = ["admin", "teacher", "moderator"]
        else:  # admin
            available_roles = ["teacher", "moderator"]

        new_role = st.selectbox(
            "🎭 Role",
            available_roles,
            key="admin_new_role"
        )


        if st.button("Add / Update Admin", key="add_update_admin_btn"):

            if not new_user.strip() or not new_pass:
                st.error("🚫 Username & password required.")
                st.stop()

            if new_pass != confirm_pass:
                st.error("🚫 Passwords do not match.")
                st.stop()

            try:

                # ==========================================
                # 🔐 ROLE AUTHORIZATION (FINAL SAFETY LAYER)
                # ==========================================
                if current_role == "admin":
                    allowed_roles = ["teacher", "moderator"]

                elif current_role == "super_admin":
                    allowed_roles = ["admin", "teacher", "moderator"]

                else:
                    st.error("🚫 Not authorized to create users.")
                    st.stop()

                # 🚫 Prevent invalid role assignment
                if new_role not in allowed_roles:
                    st.error(f"🚫 You are not allowed to create '{new_role}'")
                    st.stop()

                # 🚫 Hard block super_admin creation
                if new_role == "super_admin":
                    st.error("🚫 Super Admin cannot be created from this panel.")
                    st.stop()

                # ==========================================
                # 👤 CREATE / UPDATE USER
                # ==========================================
                ok = set_admin(
                    new_user.strip(),
                    new_pass.strip(),
                    new_role,
                    school_id if new_role != "super_admin" else None
                )

                if not ok:
                    st.error("❌ Admin creation failed. Username may already exist.")
                    st.stop()

                # ==========================================
                # ✅ SUCCESS MESSAGE
                # ==========================================
                st.success(
                    f"✅ User '{new_user}' added/updated successfully."
                    + (f" Linked to {school_obj.name}." if new_role != "super_admin" else "")
                )

                st.rerun()

            except Exception as e:
                st.error(f"⚠️ Admin operation failed: {e}")



# --------------------------------------------
 # Manage Subjects
# --------------------------------------------
    elif selected_tab == "📚 Manage Subjects":

        require_permission("manage_subjects")
        st.subheader("📚 Manage Subjects")

        # Choose class
        db = get_session()

        school_id = st.session_state.get("school_id")

        try:
            class_rows = (
                db.query(Class.id, Class.name)
                .filter(Class.school_id == school_id)
                .order_by(Class.name.asc())
                .all()
            )
        finally:
            db.close()


        if not class_rows:
            st.warning("No classes found for this school.")
            st.stop()

        # Map name → id
        class_map = {name: cid for cid, name in class_rows}

        # -------- SELECTBOX --------
        selected_class_name = st.selectbox(
            "Select Class",
            list(class_map.keys()),
            key="subject_class_select"
        )



        # Resolve ID safely

        if "selected_class_id" not in st.session_state:
            st.session_state.selected_class_id = class_map[selected_class_name]

        class_id = st.session_state.selected_class_id

        # 🔍 DEBUG


        # -------- LOAD SUBJECTS --------
        db = get_session()

        school_id = st.session_state.get("school_id")
        subjects = (
            db.query(Subject.id, Subject.name)
            .filter(
                Subject.school_id == school_id,
                Subject.class_id == class_id
            )
            .order_by(Subject.name.asc())
            .all()
        )

        db.close()


        if subjects:
            for i, (subject_id, subject_name) in enumerate(subjects):
                c1, c2 = st.columns([8, 1])
                c1.write(f"{i + 1}. {subject_name}")

                if c2.button("🗑️", key=f"del_subject_{subject_id}"):
                    deleted = delete_subject(
                        subject_id=subject_id,
                        class_id=class_id,  # ✅ correct
                        school_id=school_id,
                    )

                    if deleted:
                        st.success("✅ Subject deleted.")
                        st.rerun()
                    else:
                        st.warning("⚠️ Subject could not be deleted.")

        st.markdown("---")
        new_subject = st.text_input("➕ Add New Subject", key="new_subject_input")
        if st.button("Add Subject", key="add_subject_btn"):
            name = (new_subject or "").strip()
            if not name:
                st.warning("Enter a valid subject name.")
            elif any(name.lower() == s[1].lower() for s in subjects):
                st.info("Subject already exists.")
            else:
                db = get_session()
                school_id = get_current_school_id()

                try:
                    # ✅ use the resolved ID from earlier — DO NOT use selected_class.id
                    # (class_id must already exist from the lookup step)

                    new_subject = Subject(
                        name=name,
                        class_id=class_id,  # <-- ID only
                        school_id=school_id  # <-- ID only
                    )

                    db.add(new_subject)
                    db.commit()

                    st.success(f"✅ Subject '{name}' added successfully.")
                    st.rerun()



                except IntegrityError:
                    db.rollback()
                    st.warning(f"⚠️ Subject '{name}' already exists for this class.")

                except Exception as e:
                    db.rollback()
                    st.error(f"🚫 Failed to add subject: {e}")

                finally:
                    db.close()

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
                st.error("🚫 Please fill in all fields.")
            elif new_pw != confirm_pw:
                st.error("🚫 New passwords do not match.")
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
                        st.error("🚫 Failed to update password. Try again.")
                else:
                    st.error("🚫 Current password is incorrect.")




    # -----------------------
    # 📤 Upload Questions (Per School)
    # -----------------------
    elif selected_tab == "📤 Upload Questions":

        st.subheader("📤 Upload Questions to Database")

        # -------------------------
        # 🏫 GLOBAL SCHOOL (SINGLE SOURCE)
        # -------------------------
        school_id = st.session_state.get("school_id")

        if not school_id:
            st.warning("🚫 No school selected.")
            st.stop()

        school = db.query(School).filter_by(id=school_id).first()

        if not school:
            st.error("🚫 Selected school not found.")
            st.stop()

        st.info(f"🏫 Current School: {school.name} (ID: {school_id})")

        # -------------------------
        # 📚 LOAD CLASSES (SAFE SYNC)
        # -------------------------
        classes = load_classes(school_id)

        if not classes:
            st.warning("🚫 No classes found for this school.")
            st.stop()

        class_ids = [c.id for c in classes]
        class_lookup = {c.id: c for c in classes}

        # ✅ Ensure valid class selection
        if (
                "upload_class" not in st.session_state
                or st.session_state["upload_class"] not in class_ids
        ):
            st.session_state["upload_class"] = class_ids[0]

        selected_class_id = st.selectbox(
            "Select Class",
            class_ids,
            format_func=lambda cid: class_lookup[cid].name,
            key="upload_class"
        )

        class_id = selected_class_id

        # -------------------------
        # 📘 LOAD SUBJECTS (SAFE SYNC)
        # -------------------------
        subjects = load_subjects(class_id=class_id, school_id=school_id)

        if not subjects:
            st.warning("⚠️ No subjects available for this class.")
            st.info("👉 Please add subjects in Manage Subjects first.")
            st.stop()

        subject_ids = [s.id for s in subjects]
        subject_lookup = {s.id: s for s in subjects}

        # ✅ Ensure valid subject selection
        if (
                "upload_subject" not in st.session_state
                or st.session_state["upload_subject"] not in subject_ids
        ):
            st.session_state["upload_subject"] = subject_ids[0]

        selected_subject_id = st.selectbox(
            "Select Subject",
            subject_ids,
            format_func=lambda sid: subject_lookup[sid].name,
            key="upload_subject"
        )

        sub = subject_lookup[selected_subject_id]

        # -------------------------
        # 📂 FILE UPLOAD
        # -------------------------
        uploaded_file = st.file_uploader(
            "Upload JSON file (Objective Questions)",
            type=["json"],
            key="objective_file"
        )

        # -------------------------
        # 🚀 UPLOAD BUTTON
        # -------------------------
        if st.button("✅ Upload Questions", key="confirm_upload_btn"):

            if not uploaded_file:
                st.warning("Please upload a JSON file.")
                st.stop()

            try:
                import json
                data = json.load(uploaded_file)

                if not isinstance(data, list):
                    st.error("Invalid format — file must contain a list of questions.")
                    st.stop()

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

                # ----------------------
                # 🔍 CHECK DUPLICATES
                # ----------------------
                existing_questions_text = {
                    q.question_text.lower()
                    for q in get_objective_questions(
                        class_id=class_id,
                        subject_id=sub.id,
                        school_id=school_id
                    )
                }

                duplicates = [
                    q["question"]
                    for q in cleaned
                    if q["question"].lower() in existing_questions_text
                ]

                if duplicates:
                    st.warning(
                        f"⚠️ {len(duplicates)} duplicate question(s) detected. "
                        "They will be skipped."
                    )

                cleaned = [
                    q for q in cleaned
                    if q["question"].lower() not in existing_questions_text
                ]

                if not cleaned:
                    st.info("No new questions to upload.")
                    st.stop()

                # ----------------------
                 # 💾 SAVE TO DATABASE
                # ----------------------
                result = handle_uploaded_questions(
                    class_id=class_id,
                    subject_id=sub.id,
                    valid_questions=cleaned,
                    school_id=school_id
                )

                if result.get("success"):
                    st.success(
                        f"🎯 Uploaded {result['inserted']} new questions "
                        f"for {class_lookup[class_id].name} - {sub.name}."
                    )
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.warning(f"🚫 Upload failed: {result.get('error', 'Unknown error')}")

            except Exception as e:
                st.error(f"🚫 Upload error: {e}")



    # =========================================================
    # ✍️ SUBJECTIVE QUESTIONS (SYNCED + SAFE)
    # =========================================================
    elif selected_tab == "✍️ Add Subjective Questions":

        st.subheader("✍️ Add Subjective Questions")

        # =====================================================
        # 🏫 GLOBAL SCHOOL (NO SECOND SELECTOR)
        # =====================================================
        school_id = st.session_state.get("school_id")

        if not school_id:
            st.error("🚫 No school selected.")
            st.stop()

        db = get_session()
        try:
            school = db.query(School).filter_by(id=school_id).first()
        finally:
            db.close()

        if not school:
            st.error("🚫 Selected school not found.")
            st.stop()

        st.info(f"🏫 Current School: {school.name}")

        # =====================================================
        # 📚 LOAD CLASSES (SAFE SYNC)
        # =====================================================
        db = get_session()
        try:
            classes = (
                db.query(Class)
                .filter(Class.school_id == school_id)
                .order_by(Class.name.asc())
                .all()
            )
        finally:
            db.close()

        if not classes:
            st.warning("No classes found.")
            st.stop()

        class_ids = [c.id for c in classes]
        class_lookup = {c.id: c.name for c in classes}

        # ✅ Ensure valid class state
        if (
                "subjective_class" not in st.session_state
                or st.session_state["subjective_class"] not in class_ids
        ):
            st.session_state["subjective_class"] = class_ids[0]

        selected_class_id = st.selectbox(
            "Select Class",
            class_ids,
            format_func=lambda cid: class_lookup[cid],
            key="subjective_class"
        )

        class_id = selected_class_id

        # =====================================================
        # 📘 LOAD SUBJECTS (SAFE SYNC)
        # =====================================================
        db = get_session()
        try:
            subjects = (
                db.query(Subject)
                .filter(
                    Subject.school_id == school_id,
                    Subject.class_id == class_id
                )
                .order_by(Subject.name.asc())
                .all()
            )
        finally:
            db.close()

        if not subjects:
            st.warning("No subjects found.")
            st.stop()

        subject_ids = [s.id for s in subjects]
        subject_lookup = {s.id: s.name for s in subjects}

        # ✅ Ensure valid subject state
        if (
                "subjective_subject" not in st.session_state
                or st.session_state["subjective_subject"] not in subject_ids
        ):
            st.session_state["subjective_subject"] = subject_ids[0]

        selected_subject_id = st.selectbox(
            "Select Subject",
            subject_ids,
            format_func=lambda sid: subject_lookup[sid],
            key="subjective_subject"
        )

        subject_id = selected_subject_id

        st.divider()

        # =====================================================
        # ➕ ADD SINGLE QUESTION
        # =====================================================
        st.markdown("### ➕ Add Single Question")

        question_text = st.text_area(
            "Question",
            key="subjective_single_text"
        )

        marks = st.number_input(
            "Marks",
            1,
            100,
            10,
            key="subjective_single_marks"
        )

        if st.button("Save Question", key="subjective_save"):

            if not question_text.strip():
                st.error("Question required.")
                st.stop()

            db = get_session()

            try:
                db.add(
                    SubjectiveQuestion(
                        school_id=school_id,
                        class_id=class_id,
                        subject_id=subject_id,
                        question_text=question_text.strip(),
                        marks=int(marks)
                    )
                )

                db.commit()

                st.success("Question saved.")
                st.rerun()

            except Exception as e:
                db.rollback()
                st.error(f"Failed: {e}")

            finally:
                db.close()

        # =====================================================
        # ✍️ Bulk Upload Subjective Questions (CSV/Text)
        # =====================================================
        st.markdown("### 📤 Bulk Upload")

        uploaded_file = st.file_uploader(
            "Upload CSV (column 'question_text')",
            type=["csv"],
            key="subjective_csv"
        )

        bulk_text = st.text_area(
            "Or paste numbered questions",
            height=200,
            key="subjective_text"
        )

        if st.button("Upload Questions", key="subjective_upload"):

            cleaned_subjective = []

            # -------------------------
            # CSV MODE
            # -------------------------
            if uploaded_file:
                try:
                    df = pd.read_csv(uploaded_file, on_bad_lines='skip')
                    st.info(f"CSV rows read: {len(df)}")

                    if df.empty:
                        st.error("CSV is empty.")
                        st.stop()

                    if "question_text" not in df.columns:
                        first_col = df.columns[0]
                        st.warning(f"'question_text' column not found, using: '{first_col}'")
                        df.rename(columns={first_col: "question_text"}, inplace=True)

                    for idx, row in df.iterrows():
                        q_text = str(row["question_text"]).strip()

                        if not q_text:
                            continue

                        try:
                            marks_val = int(row.get("marks", 10))
                        except Exception:
                            marks_val = 10

                        cleaned_subjective.append({
                            "question": q_text,
                            "marks": marks_val
                        })

                except Exception as e:
                    st.error(f"CSV error: {e}")
                    st.stop()

            # -------------------------
            # TEXT MODE
            # -------------------------
            elif bulk_text.strip():
                import re
                parts = re.split(r"\n?\s*\d+\.\s*", bulk_text.strip())

                for p in parts:
                    q_text = p.strip()
                    if not q_text:
                        continue

                    cleaned_subjective.append({
                        "question": q_text,
                        "marks": 10
                    })

            else:
                st.warning("Provide CSV or paste questions.")
                st.stop()

            # -------------------------
            # 🔍 DUPLICATE CHECK
            # -------------------------
            existing_subj_text = {
                q.question_text.lower()
                for q in get_subjective_questions(
                    class_id=class_id,
                    subject_id=subject_id,
                    school_id=school_id
                )
            }

            duplicates = [
                q["question"]
                for q in cleaned_subjective
                if q["question"].lower() in existing_subj_text
            ]

            if duplicates:
                st.warning(f"⚠️ {len(duplicates)} duplicate(s) skipped.")
                for dq in duplicates[:10]:  # limit spam
                    st.text(f"• {dq}")

            cleaned_subjective = [
                q for q in cleaned_subjective
                if q["question"].lower() not in existing_subj_text
            ]

            # -------------------------
            # 💾 SAVE TO DB
            # -------------------------
            if cleaned_subjective:

                db = get_session()

                try:
                    count = 0

                    for q in cleaned_subjective:
                        db.add(
                            SubjectiveQuestion(
                                school_id=school_id,
                                class_id=class_id,
                                subject_id=subject_id,
                                question_text=q["question"],
                                marks=int(q.get("marks", 10))
                            )
                        )
                        count += 1

                    db.commit()

                    # ✅ SAFE DISPLAY (no stale names)
                    st.success(
                        f"🎯 Uploaded {count} new subjective question(s) "
                        f"for {class_lookup[class_id]} - {subject_lookup[subject_id]}."
                    )

                    st.rerun()

                except Exception as e:
                    db.rollback()
                    st.error(f"Upload failed: {e}")

                finally:
                    db.close()

            else:
                st.info("⚠️ No new questions to upload.")



    # =====================================================
    # ✍️ Review Subjective Questions (FIXED + STABLE)
    # =====================================================
    # =====================================================
    # ✍️ Review Subjective Questions
    # FINAL STABLE VERSION
    # =====================================================

    elif selected_tab == "✍️ Review Subj Questions":

        import json
        from datetime import datetime
        from sqlalchemy import or_, text

        st.subheader("📋 Subjective Grading Dashboard")

        school_id = st.session_state.get("school_id")

        if not school_id:
            st.error("🚫 No school selected")
            st.stop()

        status_filter = st.selectbox(
            "Show submissions",
            [
                "Pending Review",
                "Reviewed",
                "All"
            ]
        )

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

        db = get_session()

        try:

            # -------------------------
            # SAFE COLUMN CHECK
            # -------------------------

            try:

                db.execute(text("""
                ALTER TABLE student_progress
                ADD COLUMN IF NOT EXISTS review_status TEXT
                """))

                db.commit()

            except:
                db.rollback()

            # -------------------------
            # QUERY
            # -------------------------

            query = db.query(StudentProgress).filter(
                StudentProgress.school_id == school_id,
                StudentProgress.test_type == "subjective",
                StudentProgress.submitted == True
            )

            if status_filter == "Pending Review":

                query = query.filter(
                    or_(
                        StudentProgress.review_status.is_(None),
                        StudentProgress.review_status == "pending"
                    )
                )

            elif status_filter == "Reviewed":

                query = query.filter(
                    StudentProgress.review_status == "reviewed"
                )

            submissions = query.order_by(
                StudentProgress.created_at.desc()
            ).all()

            if not submissions:
                st.info("No submissions found")
                st.stop()

            # =================================================
            # RENDER EACH SUBMISSION
            # =================================================
            # ---------------------------------
            # 🔍 SEARCH + FILTER UI
            # ---------------------------------

            col1, col2 = st.columns([2, 1])

            with col1:
                student_search = st.text_input(
                    "🔍 Search Student"
                )

            with col2:
                subject_filter = st.selectbox(
                    "Subject",
                    ["All"] + sorted(
                        list({
                            getattr(
                                s.subject,
                                "name",
                                "Unknown"
                            )
                            for s in submissions
                        })
                    )
                )

            # ---------------------------------
            # APPLY FILTERS
            # ---------------------------------

            filtered_submissions = []

            for sub in submissions:

                student_name = getattr(
                    sub.student,
                    "name",
                    ""
                )

                subject_name = getattr(
                    sub.subject,
                    "name",
                    "Unknown"
                )

                matches_student = (
                        student_search.lower()
                        in student_name.lower()
                )

                matches_subject = (

                        subject_filter == "All"

                        or

                        subject_name == subject_filter
                )

                if (
                        matches_student
                        and
                        matches_subject
                ):
                    filtered_submissions.append(
                        sub
                    )

            if not filtered_submissions:
                st.warning(
                    "No matching records"
                )

                st.stop()
            for sub in submissions:

                student_name = getattr(
                    sub.student,
                    "name",
                    f"Student {sub.student_id}"
                )

                subject_name = getattr(
                    sub.subject,
                    "name",
                    "Unknown"
                )

                review_status = (
                        sub.review_status or "pending"
                )

                is_reviewed = (
                        review_status == "reviewed"
                )

                icon = (
                    "✅ Reviewed"
                    if is_reviewed
                    else "🟡 Pending"
                )

                with st.expander(
                        f"{icon} | 👤 {student_name} | 📘 {subject_name}",
                        expanded=not is_reviewed
                ):

                    answers = parse_json_field(
                        sub.answers
                    )

                    attachments = parse_json_field(
                        sub.attachments
                    )

                    st.markdown(
                        "### 📄 Student Answers"
                    )

                    scores = {}

                    if not answers:

                        st.write(
                            "_No answers submitted_"
                        )

                    else:

                        for idx, item in enumerate(
                                answers,
                                start=1
                        ):

                            question = (
                                item.get(
                                    "question",
                                    f"Question {idx}"
                                )
                                if isinstance(item, dict)
                                else f"Question {idx}"
                            )

                            answer = (
                                item.get(
                                    "answer",
                                    ""
                                )
                                if isinstance(item, dict)
                                else str(item)
                            )

                            col1, col2, col3 = st.columns(
                                [3, 5, 2]
                            )

                            with col1:

                                st.markdown(
                                    f"**Q{idx}:** {question}"
                                )

                            with col2:

                                st.markdown(
                                    answer
                                    or "_No answer_"
                                )

                            with col3:

                                slider_key = f"score_{sub.id}_{idx}"

                                existing_score = 0

                                if (
                                        is_reviewed
                                        and sub.score
                                ):
                                    total_q = len(answers)

                                    existing_score = (
                                        int(
                                            sub.score /
                                            total_q
                                        )
                                    )

                                score = st.slider(
                                    f"Score Q{idx}",
                                    0,
                                    100,
                                    value=existing_score,
                                    key=slider_key,
                                    disabled=is_reviewed
                                )

                                scores[idx] = score

                            st.markdown("---")

                    # -------------------------
                    # ATTACHMENTS
                    # -------------------------

                    if attachments:

                        st.markdown(
                            "### 📎 Attachments"
                        )

                        for file in attachments:

                            if isinstance(
                                    file,
                                    dict
                            ):

                                st.write(
                                    file.get(
                                        "name",
                                        str(file)
                                    )
                                )

                            else:

                                st.write(
                                    str(file)
                                )

                    # -------------------------
                    # REVIEWED VIEW
                    # -------------------------

                    if is_reviewed:
                        st.success(
                            f"""
    Final Score:
    {sub.score}

    Reviewed:
    {sub.reviewed_at}
    """
                        )

                    # -------------------------
                    # SUBMIT
                    # -------------------------

                    submit_clicked = st.button(
                        f"✅ Submit Review for {student_name}",
                        key=f"submit_{sub.id}",
                        disabled=is_reviewed
                    )

                    if submit_clicked:

                        total_score = sum(
                            scores.values()
                        )

                        total_questions = len(
                            answers
                        )

                        max_score = (
                                total_questions * 100
                        )

                        percent = (
                                (
                                        total_score
                                        / max_score
                                ) * 100
                        )

                        sub.score = total_score

                        sub.review_status = (
                            "reviewed"
                        )

                        sub.reviewed_at = (
                            datetime.utcnow()
                        )

                        sub.locked = True

                        from backend.models import TestResult

                        existing = db.query(
                            TestResult
                        ).filter_by(
                            student_id=sub.student_id,
                            subject_id=sub.subject_id,
                            class_id=sub.class_id,
                            school_id=sub.school_id
                        ).first()

                        if existing:

                            # 🔒 NO UPDATE
                            st.warning(
                                "Already finalized"
                            )

                        else:

                            db.add(
                                TestResult(
                                    student_id=sub.student_id,
                                    class_id=sub.class_id,
                                    subject_id=sub.subject_id,
                                    score=total_score,
                                    total=max_score,
                                    percentage=percent,
                                    school_id=sub.school_id
                                )
                            )

                        db.commit()

                        st.success(
                            "Review submitted"
                        )

                        st.rerun()

        finally:

            db.close()


    # =====================================================
    # 🗑️ Delete Questions Dashboard (SYNCED + SAFE)
    # =====================================================
    elif selected_tab == "🗑️ Delete Questions":

        require_permission("delete_questions")  # 🔐 ADD THIS

        import json

        st.subheader("🗑️ Question Deletion Dashboard")

        # -------------------------
        # 🏫 GLOBAL SCHOOL (SYNCED)
        # -------------------------
        school_id = st.session_state.get("school_id")

        if not school_id:
            st.warning("🚫 No school selected.")
            st.stop()

        db = get_session()

        try:
            # -------------------------
            # 1️⃣ Question Type
            # -------------------------
            question_type = st.selectbox(
                "Select Question Type",
                ["Objective", "Subjective"],
                key="delete_q_type"
            )

            # -------------------------
            # 2️⃣ LOAD CLASSES (SAFE)
            # -------------------------
            classes = db.query(Class).filter_by(school_id=school_id).all()

            if not classes:
                st.warning("⚠️ No classes found for this school.")
                st.stop()

            class_ids = [c.id for c in classes]
            class_lookup = {c.id: c.name for c in classes}

            if (
                    "delete_class" not in st.session_state
                    or st.session_state["delete_class"] not in class_ids
            ):
                st.session_state["delete_class"] = class_ids[0]

            selected_class_id = st.selectbox(
                "Select Class",
                class_ids,
                format_func=lambda cid: class_lookup[cid],
                key="delete_class"
            )

            class_id = selected_class_id

            # -------------------------
            # 3️⃣ LOAD SUBJECTS (SAFE)
            # -------------------------
            subjects = db.query(Subject).filter_by(
                school_id=school_id,
                class_id=class_id
            ).all()

            if not subjects:
                st.warning("⚠️ No subjects found for this class.")
                st.stop()

            subject_ids = [s.id for s in subjects]
            subject_lookup = {s.id: s.name for s in subjects}

            if (
                    "delete_subject" not in st.session_state
                    or st.session_state["delete_subject"] not in subject_ids
            ):
                st.session_state["delete_subject"] = subject_ids[0]

            selected_subject_id = st.selectbox(
                "Select Subject",
                subject_ids,
                format_func=lambda sid: subject_lookup[sid],
                key="delete_subject"
            )

            subject_id = selected_subject_id

            # -------------------------
            # 4️⃣ LOAD QUESTIONS
            # -------------------------
            if question_type == "Objective":

                questions = (
                    db.query(ObjectiveQuestion)
                    .filter_by(
                        school_id=school_id,
                        class_id=class_id,
                        subject_id=subject_id
                    )
                    .order_by(ObjectiveQuestion.id.desc())
                    .all()
                )

            else:
                questions = (
                    db.query(SubjectiveQuestion)
                    .filter_by(
                        school_id=school_id,
                        class_id=class_id,
                        subject_id=subject_id
                    )
                    .order_by(SubjectiveQuestion.id.desc())
                    .all()
                )

            st.write("Questions Found:", len(questions))

            if not questions:
                st.info("No questions found for this selection.")
                st.stop()

            st.markdown(f"### 📚 Loaded {len(questions)} Questions")

            # -------------------------
            # 5️⃣ RENDER QUESTIONS
            # -------------------------
            for q in questions:

                question_text = getattr(q, "question_text", "")

                with st.expander(f"❓ {question_text[:120]}"):

                    st.markdown(f"**Question:** {question_text}")

                    if question_type == "Objective":

                        options = getattr(q, "options", [])

                        if isinstance(options, str):
                            try:
                                options = json.loads(options)
                            except Exception:
                                options = []

                        if options:
                            st.markdown("**Options:**")
                            for opt in options:
                                st.write(f"- {opt}")

                        correct_answer = getattr(q, "correct_answer", "")
                        st.success(f"Correct Answer: {correct_answer}")

                    else:
                        marks = getattr(q, "marks", 10)
                        st.info(f"Marks: {marks}")

                    # -------------------------
                    # 🗑️ DELETE BUTTON
                    # -------------------------
                    if st.button(
                            "🗑️ Delete Question",
                            key=f"delete_{question_type}_{q.id}"
                    ):
                        db.delete(q)
                        db.commit()

                        st.success("Question deleted successfully.")
                        st.rerun()

        finally:
            db.close()




    # =====================================================
    # 🗂️ ARCHIVE / RESTORE QUESTIONS (SYNCED + SAFE)
    # =====================================================
    elif selected_tab == "🗂️ Archive / Restore Questions":

        require_permission("archive_questions")  # 🔐 ADD THIS

        st.subheader("🗂️ Archive or Restore Questions")
        # -------------------------
        # 🏫 GLOBAL SCHOOL (STRICT)
        # -------------------------
        school_id = st.session_state.get("school_id")

        if not school_id:
            st.warning("⚠️ No school selected.")
            st.stop()

        db = get_session()

        try:
            st.info(f"🏫 Current School ID: {school_id}")

            # -------------------------
            # 📚 LOAD CLASSES (SAFE)
            # -------------------------
            classes = (
                db.query(Class)
                .filter(Class.school_id == school_id)
                .order_by(Class.name.asc())
                .all()
            )

            if not classes:
                st.warning("⚠️ No classes found.")
                st.stop()

            class_ids = [c.id for c in classes]
            class_lookup = {c.id: c.name for c in classes}

            if (
                    "archive_class" not in st.session_state
                    or st.session_state["archive_class"] not in class_ids
            ):
                st.session_state["archive_class"] = class_ids[0]

            selected_class_id = st.selectbox(
                "Select Class",
                class_ids,
                format_func=lambda cid: class_lookup[cid],
                key="archive_class"
            )

            class_id = selected_class_id

            # -------------------------
            # 📘 LOAD SUBJECTS (SAFE)
            # -------------------------
            subjects = (
                db.query(Subject)
                .filter(
                    Subject.school_id == school_id,
                    Subject.class_id == class_id
                )
                .order_by(Subject.name.asc())
                .all()
            )

            if not subjects:
                st.warning("⚠️ No subjects found.")
                st.stop()

            subject_ids = [s.id for s in subjects]
            subject_lookup = {s.id: s.name for s in subjects}

            if (
                    "archive_subject" not in st.session_state
                    or st.session_state["archive_subject"] not in subject_ids
            ):
                st.session_state["archive_subject"] = subject_ids[0]

            selected_subject_id = st.selectbox(
                "Select Subject",
                subject_ids,
                format_func=lambda sid: subject_lookup[sid],
                key="archive_subject"
            )

            subject_id = selected_subject_id

            # -------------------------
            # 🔁 VIEW MODE
            # -------------------------
            show_archived = st.checkbox("👁️ Show Archived Questions", value=False)

            # -------------------------
            # 📘 ACTIVE QUESTIONS
            # -------------------------
            if not show_archived:

                questions = (
                    db.query(ObjectiveQuestion)
                    .filter(
                        ObjectiveQuestion.school_id == school_id,
                        ObjectiveQuestion.class_id == class_id,
                        ObjectiveQuestion.subject_id == subject_id
                    )
                    .order_by(ObjectiveQuestion.id.asc())
                    .all()
                )

                st.info("Showing ACTIVE questions")

                if not questions:
                    st.warning("No active questions found.")

                for q in questions:
                    with st.expander(f"Q{q.id}: {q.question_text[:70]}..."):

                        st.write(f"**Answer:** {q.correct_answer}")

                        if getattr(q, "submissions", None):
                            st.warning("⚠️ Cannot archive — has submissions.")
                        else:
                            if st.button(f"🗃️ Archive Q{q.id}", key=f"archive_q_{q.id}"):

                                if archive_question(db, q.id):
                                    st.success(f"✅ Archived Q{q.id}")
                                    st.rerun()

            # -------------------------
            # 🗂️ ARCHIVED QUESTIONS
            # -------------------------
            else:

                archived_questions = (
                    db.query(ArchivedQuestion)
                    .filter(
                        ArchivedQuestion.school_id == school_id,
                        ArchivedQuestion.class_id == class_id,
                        ArchivedQuestion.subject_id == subject_id
                    )
                    .order_by(ArchivedQuestion.archived_at.desc())
                    .all()
                )

                st.info("Showing ARCHIVED questions")

                if not archived_questions:
                    st.warning("No archived questions found.")

                for aq in archived_questions:
                    with st.expander(f"Q{aq.id}: {aq.question_text[:70]}..."):

                        st.write(f"**Answer:** {aq.correct_answer}")

                        if st.button(f"♻️ Restore Q{aq.id}", key=f"restore_q_{aq.id}"):

                            if restore_question(db, aq.id):
                                st.success(f"✅ Restored Q{aq.id}")
                                st.rerun()

        finally:
            db.close()



    # =======================================
    # ⏱️ Stand-alone Duration Configuration (SYNCED + SAFE)
    # =======================================
    elif selected_tab == "⏱ Set Duration":

        st.subheader("⏱ Set Test Duration Per Class & Subject")

        # ------------------------------
        # 🏫 GLOBAL SCHOOL (STRICT)
        # ------------------------------
        school_id = st.session_state.get("school_id")

        if not school_id:
            st.error("🚫 No school selected.")
            st.stop()

        # ------------------------------
        # 📚 LOAD CLASSES (SAFE)
        # ------------------------------
        classes = load_classes(school_id)

        if not classes:
            st.warning("⚠️ No classes found for this school.")
            st.stop()

        class_ids = [c.id for c in classes]
        class_lookup = {c.id: c.name for c in classes}

        if (
                "dur_class" not in st.session_state
                or st.session_state["dur_class"] not in class_ids
        ):
            st.session_state["dur_class"] = class_ids[0]

        selected_class_id = st.selectbox(
            "Select Class",
            class_ids,
            format_func=lambda cid: class_lookup[cid],
            key="dur_class"
        )

        class_id = selected_class_id

        # ------------------------------
        # 📘 LOAD SUBJECTS (SAFE)
        # ------------------------------
        subjects = load_subjects(
            class_id=class_id,
            school_id=school_id
        )

        if not subjects:
            st.warning("⚠️ No subjects found for this class.")
            st.stop()

        subject_ids = [s.id for s in subjects]
        subject_lookup = {s.id: s.name for s in subjects}

        if (
                "dur_subject" not in st.session_state
                or st.session_state["dur_subject"] not in subject_ids
        ):
            st.session_state["dur_subject"] = subject_ids[0]

        selected_subject_id = st.selectbox(
            "Select Subject",
            subject_ids,
            format_func=lambda sid: subject_lookup[sid],
            key="dur_subject"
        )

        subject_id = selected_subject_id

        # ------------------------------
        # ⏱ LOAD CURRENT DURATION
        # ------------------------------
        current_duration_secs = get_test_duration(
            school_id=school_id,
            class_id=class_id,
            subject_id=subject_id
        ) or 0

        current_duration_mins = current_duration_secs // 60 if current_duration_secs else 0

        if current_duration_mins > 0:
            st.info(f"🕒 Current Duration: **{current_duration_mins} minutes**")
        else:
            st.info("No duration set yet — please enter one below.")

        # ------------------------------
        # ✏️ INPUT NEW DURATION
        # ------------------------------
        new_duration_mins = st.number_input(
            "Enter New Duration (minutes):",
            min_value=5,
            max_value=180,
            step=5,
            value=current_duration_mins or 30,
            key="new_duration_input"
        )

        # ------------------------------
        # 💾 SAVE
        # ------------------------------
        if st.button("💾 Save Duration", key="save_duration_btn"):
            try:
                set_test_duration(
                    school_id=school_id,
                    class_id=class_id,
                    subject_id=subject_id,
                    duration_minutes=new_duration_mins
                )

                # readable format
                hours = new_duration_mins // 60
                minutes = new_duration_mins % 60

                if hours and minutes:
                    readable = f"{hours} hour{'s' if hours > 1 else ''} {minutes} minute{'s' if minutes > 1 else ''}"
                elif hours:
                    readable = f"{hours} hour{'s' if hours > 1 else ''}"
                else:
                    readable = f"{minutes} minute{'s' if minutes > 1 else ''}"

                st.success(
                    f"✅ Duration updated to **{readable}** for "
                    f"{class_lookup[class_id]} — {subject_lookup[subject_id]}"
                )

            except Exception as e:
                st.error(f"🚫 Failed to save duration: {e}")




    # -----------------------
    # 🏆 View Leaderboard (SYNCED + SAFE)
    # -----------------------
    elif selected_tab == "🏆 View Leaderboard":

        st.subheader("🏆 Leaderboard")

        # -------------------------
        # 🏫 SCHOOL CONTEXT
        # -------------------------
        school_id = st.session_state.get("school_id")

        if not school_id:
            st.error("🚫 No school selected.")
            st.stop()

        # -------------------------
        # 📚 CLASS FILTER (OPTIONAL)
        # -------------------------
        classes = load_classes(school_id)

        if not classes:
            st.warning("⚠️ No classes found.")
            st.stop()

        class_lookup = {c.id: c.name for c in classes}
        class_ids = [c.id for c in classes]

        selected_class = st.selectbox(
            "Filter by Class (optional)",
            ["All"] + class_ids,
            format_func=lambda cid: "All Classes" if cid == "All" else class_lookup[cid],
            key="lb_class_filter"
        )

        # -------------------------
        # 🔍 SEARCH + LIMIT
        # -------------------------
        filter_input = st.text_input(
            "🔍 Search by Name, Access Code, or Class ID",
            key="lb_filter"
        )

        top_n = st.selectbox(
            "Show Top N Students",
            options=[5, 10, 20, 50, 100, "All"],
            index=1
        )

        db = get_session()

        try:
            # -------------------------
            # 📊 QUERY (FIXED: NO Leaderboard.subject_id)
            # -------------------------
            query = (
                db.query(Leaderboard, Student, Class, Subject)
                .join(Student, Leaderboard.student_id == Student.id)
                .join(Class, Student.class_id == Class.id)
                .outerjoin(StudentProgress, StudentProgress.student_id == Student.id)
                .outerjoin(Subject, StudentProgress.subject_id == Subject.id)
                .filter(Student.school_id == school_id)
            )

            if selected_class != "All":
                query = query.filter(Student.class_id == selected_class)

            results = query.order_by(Leaderboard.score.desc()).all()

        finally:
            db.close()

        if not results:
            st.info("No leaderboard data available.")
            st.stop()

        # -------------------------
        # 🧱 BUILD DATAFRAME
        # -------------------------
        df = pd.DataFrame([
            {
                "Student Name": student.name,
                "Access Code": student.access_code,
                "Class ID": student.class_id,
                "Class Name": class_.name,
                "Subject ID": subject.id if subject else None,
                "Subject Name": subject.name if subject else "General",
                "Score": round(lb.score or 0, 2),
                "Submitted At": getattr(lb, "submitted_at", None),
            }
            for lb, student, class_, subject in results
        ])

        # format datetime safely
        if "Submitted At" in df.columns:
            df["Submitted At"] = pd.to_datetime(df["Submitted At"], errors="coerce")

        # -------------------------
        # 🔎 FILTERING
        # -------------------------
        if filter_input.strip():
            search = filter_input.strip()

            df = df[
                df["Student Name"].str.contains(search, case=False, na=False)
                | df["Access Code"].str.contains(search, case=False, na=False)
                | df["Class ID"].astype(str).str.contains(search)
                ]

            if df.empty:
                st.warning("No matching records found.")
                st.stop()

        # -------------------------
        # 📚 SUBJECT TABS
        # -------------------------
        subjects_present = (
            df[["Subject ID", "Subject Name"]]
            .drop_duplicates()
            .sort_values("Subject Name")
        )

        tabs = st.tabs(subjects_present["Subject Name"].tolist())

        for i, (_, row) in enumerate(subjects_present.iterrows()):

            subject_id = row["Subject ID"]
            subject_name = row["Subject Name"]

            with tabs[i]:

                df_sub = df[df["Subject ID"] == subject_id].copy()

                df_sub = df_sub.sort_values(by="Score", ascending=False)

                if top_n != "All":
                    df_sub = df_sub.head(int(top_n))

                st.write(f"### 🧠 {subject_name} Leaderboard")

                st.dataframe(
                    df_sub.drop(columns=["Subject ID"]),
                    use_container_width=True
                )

                st.download_button(
                    f"📥 Download {subject_name} CSV",
                    df_sub.to_csv(index=False).encode("utf-8"),
                    file_name=f"leaderboard_subject_{subject_id}_school_{school_id}.csv",
                    mime="text/csv"
                )



    # -----------------------
    # 🔄 Allow Retake (STRICT + SCHOOL-SCOPED)
    # -----------------------
    elif selected_tab == "🔄 Allow Retake":

        st.subheader("🔄 Allow Retake Permission")

        # ------------------------------------------------
        # 🏫 RESOLVE SCHOOL FIRST (CRITICAL FIX)
        # ------------------------------------------------
        admin_role = st.session_state.get("admin_role", "")

        if admin_role == "super_admin":

            schools = [s for s in (get_all_schools() or []) if s.id != 1]

            if not schools:
                st.warning("No schools found.")
                st.stop()

            school_lookup = {s.id: s.name for s in schools}

            school_id = st.selectbox(
                "🏫 Select School",
                list(school_lookup.keys()),
                format_func=lambda sid: school_lookup[sid],
                key="retake_school"
            )

        else:
            school_id = get_current_school_id()

        if not school_id:
            st.error("🚫 No school selected.")
            st.stop()

        # ------------------------------------------------
        # 🔑 ACCESS CODE INPUT
        # ------------------------------------------------
        code_input = st.text_input(
            "Student Access Code",
            key="retake_code"
        ).strip().upper()

        if not code_input:
            st.stop()

        # ✅ FIXED: PASS school_id
        student = get_student_by_access_code(code_input, school_id)

        if not student:
            st.info("🚫 Invalid student code for this school.")
            st.stop()

        db = get_session()

        try:
            # ------------------------------------------------
            # 📚 LOAD CLASS (STRICT)
            # ------------------------------------------------
            class_obj = (
                db.query(Class)
                .filter(
                    Class.id == student.class_id,
                    Class.school_id == student.school_id
                )
                .first()
            )

            class_display = class_obj.name if class_obj else f"Class ID {student.class_id}"

            st.info(f"👤 {student.name} | 📚 {class_display}")

            st.markdown("### Manage Retake Permissions")

            # ------------------------------------------------
            # 📘 LOAD SUBJECTS (SYNCED TO CLASS + SCHOOL)
            # ------------------------------------------------
            subjects = (
                db.query(Subject)
                .filter(
                    Subject.school_id == student.school_id,
                    Subject.class_id == student.class_id
                )
                .order_by(Subject.name.asc())
                .all()
            )

            if not subjects:
                st.warning("No subjects found for this student's class.")
                st.stop()

            # ==================================================
            # 🎯 OBJECTIVE SECTION
            # ==================================================
            st.markdown("## Objective")

            objective_master = st.checkbox("Allow ALL Objective", key="objective_master")

            objective_permissions = {}

            for subj in subjects:
                existing = db.query(Retake).filter_by(
                    student_id=student.id,
                    subject_id=subj.id,
                    school_id=student.school_id,
                    test_type="objective"
                ).first()

                default_value = existing.can_retake if existing else False

                allow = st.checkbox(
                    subj.name,
                    value=True if objective_master else default_value,
                    key=f"objective_{subj.id}"
                )

                objective_permissions[subj.id] = allow

            # ==================================================
            # ✍️ SUBJECTIVE SECTION
            # ==================================================
            st.markdown("---")
            st.markdown("## Subjective")

            subjective_master = st.checkbox("Allow ALL Subjective", key="subjective_master")

            subjective_permissions = {}

            for subj in subjects:
                existing = db.query(Retake).filter_by(
                    student_id=student.id,
                    subject_id=subj.id,
                    school_id=student.school_id,
                    test_type="subjective"
                ).first()

                default_value = existing.can_retake if existing else False

                allow = st.checkbox(
                    subj.name,
                    value=True if subjective_master else default_value,
                    key=f"subjective_{subj.id}"
                )

                subjective_permissions[subj.id] = allow

            # ==================================================
            # 💾 SAVE LOGIC
            # ==================================================
            if st.button("💾 Save Changes"):

                def save_permissions(permission_dict, test_type):

                    for subject_id, allow in permission_dict.items():

                        record = db.query(Retake).filter_by(
                            student_id=student.id,
                            subject_id=subject_id,
                            school_id=student.school_id,
                            test_type=test_type
                        ).first()

                        if record:
                            record.can_retake = allow
                        else:
                            db.add(
                                Retake(
                                    student_id=student.id,
                                    subject_id=subject_id,
                                    school_id=student.school_id,
                                    class_id=student.class_id,
                                    test_type=test_type,
                                    can_retake=allow
                                )
                            )

                save_permissions(objective_permissions, "objective")
                save_permissions(subjective_permissions, "subjective")

                db.commit()

                st.success("✅ Retake permissions updated successfully.")
                st.rerun()

        finally:
            db.close()


    # -----------------------
    # 🖨️ Generate Access Slips (SYNCED VERSION)
    # -----------------------
    elif selected_tab == "🖨️ Generate Slips":

        st.subheader("🖨️ Generate Student Access Slips")

        # -------------------------
        # 🏫 GLOBAL SCHOOL
        # -------------------------
        school_id = st.session_state.get("school_id")

        if not school_id:
            st.error("🚫 No school selected.")
            st.stop()

        # -------------------------

        # 👥 LOAD USERS (SCOPED)
        # -------------------------
        users = get_users(school_id=school_id)

        if not users:
            st.info("No students found for this school.")
            st.stop()

        db = get_session()

        try:
            # -------------------------
            # 📚 CLASS MAP (SCOPED)
            # -------------------------
            classes = (
                db.query(Class)
                .filter(Class.school_id == school_id)
                .order_by(Class.name.asc())
                .all()
            )

            class_map = {c.id: c.name for c in classes}

        finally:
            db.close()

        # -------------------------
        # 🧱 BUILD DATAFRAME
        # -------------------------
        df = pd.DataFrame(list(users.values()))

        df["Class"] = df["class_id"].map(
            lambda cid: class_map.get(cid, f"Class ID {cid}")
        )

        df_display = df[["name", "Class", "access_code"]].rename(columns={
            "name": "Student Name",
            "access_code": "Access Code"
        })

        st.dataframe(df_display, use_container_width=True)

        st.download_button(
            "⬇️ Download Access Slips (CSV)",
            df_display.to_csv(index=False).encode("utf-8"),
            file_name=f"access_slips_{school_id}.csv",
            mime="text/csv"
        )

        st.success(f"✅ Generated {len(df_display)} access slips successfully!")



    # -----------------------
    # ♻️ Reset Tests (ID-BASED, SAFE + ALL SUPPORT)
    # -----------------------
    elif selected_tab == "♻️ Reset Tests":

        require_permission("reset_tests")

        st.subheader("♻️ Reset Student Test Status")

        # -------------------------
        # 🏫 GLOBAL SCHOOL (STRICT)
        # -------------------------
        school_id = st.session_state.get("school_id")

        if not school_id:
            st.warning("⚠️ No school selected or assigned.")
            st.stop()

        # -------------------------
        # 👥 LOAD STUDENTS
        # -------------------------
        users = get_users(school_id=school_id)

        if not users:
            st.info("No students found for this school.")
            st.stop()

        student_codes = list(users.keys())

        # -------------------------
        # 📋 BUILD SELECT OPTIONS (SAFE)
        # -------------------------
        student_labels = ["🌍 All Students"] + [
            f"{users[code]['name']} (Class ID {users[code].get('class_id', 'N/A')})"
            for code in student_codes
        ]

        selected_label = st.selectbox(
            "Select Student to Reset",
            student_labels,
            key="reset_select"
        )

        # -------------------------
        # 🎯 RESOLVE SELECTION
        # -------------------------
        if selected_label == "🌍 All Students":
            selected_codes = student_codes
        else:
            selected_index = student_labels.index(selected_label) - 1
            selected_code = student_codes[selected_index]
            selected_codes = [selected_code]

        # -------------------------
        # ⚠️ CONFIRMATION
        # -------------------------
        st.markdown("### ⚠️ Action")

        confirm_reset = st.checkbox(
            "I understand this will reset test attempts",
            key="confirm_reset"
        )

        if len(selected_codes) == len(student_codes):
            st.warning("🔄 You are about to reset ALL students in this school!")

        # -------------------------
        # 🚀 EXECUTION
        # -------------------------
        if confirm_reset and st.button("♻️ Reset Test Attempt", key="reset_attempt_btn"):

            success_count = 0

            for code in selected_codes:
                try:
                    # IMPORTANT: ensure reset_test accepts student_id OR convert here
                    success = reset_test(code)

                    if success:
                        success_count += 1

                except Exception:
                    continue

            if len(selected_codes) == 1:
                st.success(f"🔄 Reset completed for {users[selected_codes[0]]['name']}")
            else:
                st.success(f"🔄 Reset completed for {success_count} students")

            st.rerun()




    # -----------------------
    # 📦 Data Export & Restore (ID-BASED SAFE VERSION)
    # -----------------------
    elif selected_tab == "📦 Data Export":

        st.subheader("📦 Backup & Restore Database")

        current_role = st.session_state.get("admin_role", "")

        # ====================================================
        # 🏫 SINGLE SOURCE OF TRUTH FOR SCHOOL
        # ====================================================
        current_school_id = st.session_state.get("school_id")

        if current_role not in ("super_admin", "school_admin"):
            st.error("🚫 Access denied.")
            st.stop()

        if not current_school_id:
            st.warning("🚫 No school selected.")
            st.stop()

        st.markdown("### 🔽 Export Current Data")

        db = get_session()

        try:

            # ====================================================
            # 👥 STUDENTS (SCOPED)
            # ====================================================
            students = get_users(school_id=current_school_id)

            students_df = pd.DataFrame(students.values()) if students else pd.DataFrame()
            st.write(f"👥 Students: {len(students_df)} records")

            # ====================================================
            # ❓ QUESTIONS (SCOPED)
            # ====================================================
            q_query = db.query(ObjectiveQuestion).filter(
                ObjectiveQuestion.school_id == current_school_id
            )

            questions = q_query.all()

            questions_df = pd.DataFrame([
                {
                    "question_id": q.id,
                    "class_id": q.class_id,
                    "subject_id": q.subject_id,
                    "question_text": q.question_text,
                    "options": q.options,
                    "correct_answer": q.correct_answer,
                    "school_id": q.school_id,
                }
                for q in questions
            ]) if questions else pd.DataFrame()

            st.write(f"❓ Questions: {len(questions_df)} records")

            # ====================================================
            # 📝 SUBMISSIONS (SCOPED)
            # ====================================================
            subs = (
                db.query(StudentProgress)
                .filter(StudentProgress.school_id == current_school_id)
                .all()
            )

            submissions_df = pd.DataFrame([
                {
                    "student_id": s.student_id,
                    "class_id": s.class_id,
                    "subject_id": s.subject_id,
                    "test_type": s.test_type,
                    "score": s.score,
                    "answers": ", ".join(map(str, s.answers)) if s.answers else "",
                    "review_status": s.review_status,
                    "submitted_at": s.created_at,
                    "school_id": s.school_id,
                }
                for s in subs
            ]) if subs else pd.DataFrame()

            st.write(f"📝 Submissions: {len(submissions_df)} records")

            # ====================================================
            # 📊 RESULT TABLE (SAFE)
            # ====================================================
            results_csv = None

            if subs:

                rows = []

                for s in subs:
                    student_name = getattr(s.student, "name", f"Student {s.student_id}")
                    subject_name = getattr(s.subject, "name", f"Subject {s.subject_id}")

                    rows.append({
                        "student_id": s.student_id,
                        "student_name": student_name,
                        "subject": subject_name,
                        "score": s.score or 0
                    })

                results_df = pd.DataFrame(rows)

                result_table = results_df.pivot_table(
                    index=["student_id", "student_name"],
                    columns="subject",
                    values="score",
                    aggfunc="sum",
                    fill_value=0
                ).reset_index()

                subject_cols = [
                    c for c in result_table.columns
                    if c not in ["student_id", "student_name"]
                ]

                result_table["Total"] = result_table[subject_cols].sum(axis=1)

                result_table["Rank"] = result_table["Total"].rank(
                    ascending=False,
                    method="dense"
                ).astype(int)

                result_table = result_table.sort_values("Rank")

                st.markdown("### 📊 Student Result Table")
                st.dataframe(result_table, use_container_width=True)

                results_csv = result_table.to_csv(index=False).encode("utf-8")

        finally:
            db.close()

        # ====================================================
        # ⬇️ DOWNLOADS
        # ====================================================
        if not students_df.empty:
            st.download_button(
                "⬇️ Download Students CSV",
                students_df.to_csv(index=False).encode("utf-8"),
                file_name="students_export.csv",
                mime="text/csv",
            )

        if not questions_df.empty:
            st.download_button(
                "⬇️ Download Questions CSV",
                questions_df.to_csv(index=False).encode("utf-8"),
                file_name="questions_export.csv",
                mime="text/csv",
            )

        if not submissions_df.empty:
            st.download_button(
                "⬇️ Download Submissions CSV",
                submissions_df.to_csv(index=False).encode("utf-8"),
                file_name="submissions_export.csv",
                mime="text/csv",
            )

        if results_csv:
            st.download_button(
                "⬇️ Download Result Table CSV",
                results_csv,
                file_name="student_results.csv",
                mime="text/csv",
            )

        # ====================================================
        # 📦 FULL JSON BACKUP
        # ====================================================
        full_backup = {
            "students": students_df.to_dict(orient="records") if not students_df.empty else [],
            "questions": questions_df.to_dict(orient="records") if not questions_df.empty else [],
            "submissions": submissions_df.to_dict(orient="records") if not submissions_df.empty else [],
        }

        import json

        json_bytes = json.dumps(full_backup, indent=2, default=str).encode("utf-8")

        st.download_button(
            "⬇️ Full JSON Backup",
            json_bytes,
            file_name=f"smarttest_backup_{current_school_id}.json",
            mime="application/json"
        )

        # ------------------------------------------------
        # 🔄 RESTORE BACKUP (SAFE + ID-STRICT)
        # ------------------------------------------------
        st.markdown("---")
        st.markdown("### 🔄 Restore From Backup")

        school_id = st.session_state.get("school_id")

        if not school_id:
            st.warning("⚠️ No school selected.")
            st.stop()

        uploaded_backup = st.file_uploader(
            "Upload Backup JSON",
            type=["json"],
            key="restore_backup"
        )

        if uploaded_backup:

            import json

            try:
                backup_data = json.load(uploaded_backup)

                st.info(
                    f"Backup contains "
                    f"{len(backup_data.get('students', []))} students, "
                    f"{len(backup_data.get('questions', []))} questions, "
                    f"{len(backup_data.get('submissions', []))} submissions."
                )

                confirm = st.checkbox("⚠️ I understand this will overwrite current data")

                if confirm and st.button("🔄 Confirm & Restore"):

                    # ====================================================
                    # 🧹 SAFE DELETE ORDER (PARENTS LAST)
                    # ====================================================
                    clear_submissions_db(school_id=school_id)
                    clear_questions_db(school_id=school_id)
                    clear_students_db(school_id=school_id)

                    # ====================================================
                    # 👥 RESTORE STUDENTS
                    # ====================================================
                    for s in backup_data.get("students", []):
                        add_student_db(
                            name=s["name"],
                            class_id=s["class_id"],
                            school_id=school_id,  # FORCE CURRENT SCHOOL
                        )

                    # ====================================================
                    # ❓ RESTORE QUESTIONS
                    # ====================================================
                    for q in backup_data.get("questions", []):

                        options = q.get("options", [])

                        if isinstance(options, str):
                            try:
                                options = json.loads(options)
                            except Exception:
                                options = []

                        add_question_db(
                            class_id=q["class_id"],
                            subject_id=q["subject_id"],
                            question_text=q["question_text"],  # FIXED FIELD NAME
                            options=options,
                            correct_answer=q.get("correct_answer", q.get("answer", "")),
                            school_id=school_id,
                        )

                    # ====================================================
                    # 📝 RESTORE SUBMISSIONS (OPTIONAL SAFETY)
                    # ====================================================
                    for s in backup_data.get("submissions", []):

                        try:
                            add_submission_db(
                                student_id=s["student_id"],
                                class_id=s["class_id"],
                                subject_id=s["subject_id"],
                                test_type=s.get("test_type", "objective"),
                                score=s.get("score", 0),
                                answers=s.get("answers", ""),
                                review_status=s.get("review_status", "pending"),
                                school_id=school_id,
                            )
                        except Exception:
                            continue

                    st.success("✅ Database restored successfully.")
                    st.balloons()
                    st.rerun()

            except Exception as e:
                st.error(f"🚫 Restore failed: {e}")


    # -----------------------
    # 🚪 Logout
    # -----------------------
    elif selected_tab == "🚪 Logout":
        st.session_state["admin_logged_in"] = False
        st.success("Logged out.")
        st.rerun()



# entrypoint
if __name__ == "__main__":
    run_admin_mode()