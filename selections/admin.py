# app.py (cleaned + optimized)
import streamlit as st
import pandas as pd
import time
import io
import json
from datetime import datetime
from io import StringIO
from ui import is_archived
from models import Leaderboard, Student

from db_helpers import (
    get_session,
    Question,
    add_admin,
    get_admin,
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
    get_admins,
    clear_students_db,
    clear_questions_db,
    clear_submissions_db,
    set_retake_db,
    preview_questions_db,
    count_questions_db,
    get_retake_db,
    update_admin_password,
    bulk_add_students_db,
    reset_student_retake_db,
    hash_password,
    handle_uploaded_questions,
    ensure_super_admin_exists,
    require_admin_login,
    get_all_submissions_db,
)

# ==============================
# CONFIG
# ==============================
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
        "🗂️ Archive / Restore Questions",   # ✅ Added
        "🏆 View Leaderboard",
        "🔄 Allow Retake",
        "🖨️ Generate Access Slips",
        "♻️ Reset Tests",
        "📦 Data Export",
        "🚪 Logout"
    ],
    "admin": [
        "➕ Add User",
        "📥 Bulk Add Students",
        "👥 Manage Students",
        "🔑 Change Password",
        "📤 Upload Questions",
        "🗑️ Delete Questions & Duration",
        "🗂️ Archive / Restore Questions",   # ✅ Added
        "🏆 View Leaderboard",
        "🔄 Allow Retake",
        "🖨️ Generate Access Slips",
        "🚪 Logout"
    ],
    "teacher": [
        "👥 Manage Students",
        "📤 Upload Questions",
        "🗑️ Delete Questions & Duration",
        "🗂️ Archive / Restore Questions",   # ✅ Added
        "🏆 View Leaderboard",
        "🚪 Logout"
    ],
    "moderator": [
        "🏆 View Leaderboard",
        "🚪 Logout"
    ]
}

# ==============================
# Small helpers (UI / formatting)
# ==============================
def upper_or_none(v):
    return v.strip().upper() if isinstance(v, str) and v.strip() else None


def df_download_button(df: pd.DataFrame, label: str, filename: str):
    csv_data = df.to_csv(index=False)
    st.download_button(label, csv_data, filename)


def excel_download_buffer(dfs: dict, filename="smarttest_backup.xlsx"):
    """
    Accepts dict of sheet_name -> DataFrame, returns bytes for download.
    """
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        for sheet, df in dfs.items():
            df.to_excel(writer, index=False, sheet_name=sheet)
    buffer.seek(0)
    return buffer.getvalue()


# ==============================
# Admin panel
# ==============================
def run_admin_mode():
    if not require_admin_login():
        return

    current_user = st.session_state.get("admin_username", "")
    all_admins = get_admins(as_dict=True)
    current_role = all_admins.get(current_user, "admin")
    available_tabs = ROLE_TABS.get(current_role, ROLE_TABS["admin"])

    st.sidebar.title(f"⚙️ Admin Panel ({current_user} – {current_role})")
    selected_tab = st.sidebar.radio("Choose Action", available_tabs, key="selected_tab_radio")
    st.session_state["selected_tab"] = selected_tab

    st.title("🛠️ Admin Dashboard")

    # -----------------------
    # ➕ Add single student
    # -----------------------
    if selected_tab == "➕ Add User":
        st.subheader("Add a Student")
        name = st.text_input("Student Name")
        class_name = st.selectbox("Class", CLASSES)

        if st.button("Add Student"):
            if not name.strip():
                st.error("❌ Enter student name.")
            else:
                student_info = add_student_db(name, class_name)
                st.success(
                    f"✅ {student_info['name']} added | "
                    f"Class: {student_info['class_name']} | "
                    f"Access Code: {student_info['access_code']} | "
                    f"Unique ID: {student_info['unique_id']}"
                )

    # -----------------------
    # 📥 Bulk upload students
    # -----------------------
    elif selected_tab == "📥 Bulk Add Students":
        st.subheader("📥 Bulk Upload Students (CSV)")
        uploaded = st.file_uploader("Upload CSV with columns 'name' & 'class'", type=["csv"])
        if uploaded:
            try:
                df = pd.read_csv(uploaded)
                if not {"name", "class"}.issubset(df.columns):
                    st.error("❌ CSV must have 'name' and 'class' columns")
                else:
                    students_list = [(str(r["name"]).strip(), str(r["class"]).strip()) for _, r in df.iterrows()]
                    result = bulk_add_students_db(students_list)

                    # ✅ Summary counts
                    summary = result["summary"]
                    st.success(f"✅ {summary['new']} new students added!")
                    if summary["reused"]:
                        st.info(f"♻️ {summary['reused']} existing students reused.")

                    # 🟢 Show individual results with color
                    for student in result["students"]:
                        if student["status"] == "new":
                            color = "green"
                            icon = "✅"
                        else:
                            color = "orange"
                            icon = "♻️"
                        st.markdown(
                            f"<span style='color:{color};'>{icon}</span> "
                            f"**{student['name']}** | Class: {student['class_name']} | "
                            f"Access Code: `{student['access_code']}`",
                            unsafe_allow_html=True
                        )

                    # 🖨️ Download CSV of added students only
                    added_students = [s for s in result["students"] if s["status"] == "new"]
                    if added_students:
                        result_df = pd.DataFrame(added_students)
                        csv_data = result_df.to_csv(index=False).encode("utf-8")
                        st.download_button("📥 Download Added Students CSV", csv_data, "bulk_added_students.csv",
                                           "text/csv")

            except Exception as e:
                st.error(f"⚠️ Error reading CSV: {e}")

    # -----------------------
    # 👥 Manage Students
    # -----------------------
    elif selected_tab == "👥 Manage Students":
        st.subheader("👥 Manage Students")
        users = get_users()
        if not users:
            st.info("No students found.")
        else:
            df = pd.DataFrame(users.values())
            st.dataframe(df, use_container_width=True)

            student_ids = [u["id"] for u in df.to_dict("records")]
            selected_id = st.selectbox("Select Student ID", student_ids)

            if selected_id:
                selected_student = next((u for u in users.values() if u["id"] == selected_id), None)
                if selected_student:
                    st.write(f"✏️ Editing **{selected_student['name']}** (Class: {selected_student['class_name']})")
                    new_name = st.text_input("Update Name", value=selected_student["name"])
                    new_class = st.selectbox("Update Class", CLASSES, index=CLASSES.index(selected_student["class_name"]))
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("💾 Save Changes"):
                            update_student_db(selected_id, new_name, new_class)
                            st.success("✅ Student updated successfully!")
                            st.rerun()
                    with col2:
                        if st.button("🗑️ Delete Student"):
                            delete_student_db(selected_id)
                            st.warning("⚠️ Student deleted.")
                            st.rerun()

            df_download_button(df, "⬇️ Download Students CSV", "students_backup.csv")

    # -----------------------
    # 🛡️ Manage Admins (super_admin only)
    # -----------------------
    elif selected_tab == "🛡️ Manage Admins" and current_role == "super_admin":
        st.header("🛡️ Manage Admins")

        # Display existing admins
        admins = get_admins()
        st.dataframe(pd.DataFrame([{"username": a.username, "role": a.role} for a in admins]))

        st.subheader("➕ Add / Update Admin")
        new_user = st.text_input("👤 Username", key="admin_new_user")
        new_pass = st.text_input("🔑 Password", type="password", key="admin_new_pass")
        confirm_pass = st.text_input("🔑 Confirm Password", type="password", key="admin_confirm_pass")
        new_role = st.selectbox("🎭 Role", ["admin", "teacher", "moderator", "super_admin"], key="admin_new_role")

        if st.button("Add / Update Admin"):
            if not new_user.strip() or not new_pass.strip():
                st.error("❌ Username & password required.")
            elif new_pass != confirm_pass:
                st.error("❌ Password and Confirm Password do not match.")
            else:
                # Use set_admin which handles hashing internally
                ok = set_admin(new_user.strip(), new_pass.strip(), new_role)
                if ok:
                    st.success(f"✅ Admin '{new_user}' added or updated.")
                    st.rerun()
                else:
                    st.error("❌ Failed to add or update admin.")


    # -----------------------
    # 🔑 Change Password
    # -----------------------
    elif selected_tab == "🔑 Change Password":
        st.subheader("Change Admin Password")
        current_user = st.session_state.get("admin_username")

        old_pw = st.text_input("Current Password", type="password", key="old_pw")
        new_pw = st.text_input("New Password", type="password", key="new_pw")
        confirm_pw = st.text_input("Confirm New Password", type="password", key="confirm_pw")

        if st.button("Update Password"):
            if not old_pw or not new_pw or not confirm_pw:
                st.error("❌ Please fill in all fields.")
            elif new_pw != confirm_pw:
                st.error("❌ New passwords do not match.")
            else:
                # Verify current password
                admin = verify_admin(current_user, old_pw)
                if admin:
                    # Update password (pass plain text, hashing is done inside function)
                    success = update_admin_password(current_user, new_pw)
                    if success:
                        st.success("✅ Password updated successfully.")
                        st.info("🔑 You will be logged out in 3 seconds. Please log in again.")

                        # Countdown logout
                        for i in range(3, 0, -1):
                            st.info(f"⏳ Logging out in {i}...")
                            time.sleep(1)

                        # Reset session state and rerun
                        st.session_state["admin_logged_in"] = False
                        st.session_state["admin_username"] = None
                        st.session_state["admin_role"] = None
                        st.rerun()
                    else:
                        st.error("❌ Failed to update password. Try again.")
                else:
                    st.error("❌ Current password is incorrect.")

    # -----------------------
    # 📤 Upload Questions
    # -----------------------
    elif selected_tab == "📤 Upload Questions":
        st.subheader("📤 Upload Questions to Database")
        cls = st.selectbox("Class", CLASSES, key="upload_class")
        sub = st.selectbox("Subject", SUBJECTS, key="upload_subject")

        existing_count = count_questions_db(cls, sub)
        st.info(f"📊 Currently {existing_count} questions in DB for {cls} - {sub}")

        if st.button("🔍 Preview Existing Questions", key="preview_btn"):
            data = preview_questions_db(cls, sub, limit=10)
            if data:
                st.json(data)
            else:
                st.info("No questions found for this selection.")

        uploaded = st.file_uploader("Upload Question JSON", type=["json"], key="upload_file")

        if uploaded is not None:
            st.success(f"✅ File selected: {uploaded.name}")
            if st.button("✅ Confirm Upload", key="confirm_upload_btn"):
                # Read file content safely once
                try:
                    file_content = uploaded.read()
                    uploaded.seek(0)  # reset file pointer
                    result = handle_uploaded_questions(uploaded, cls, sub)
                except Exception as e:
                    st.error(f"❌ File read error: {e}")
                    st.stop()

                if result.get("success"):
                    st.success(
                        f"🎯 {result['inserted']} questions uploaded successfully (replaced {result['deleted']} old ones)."
                    )

                    # 🧹 Clear cached student question data
                    st.cache_data.clear()
                    st.info("🧠 Cache cleared — new questions will now load instantly for students.")

                    st.session_state.pop("upload_file", None)
                    st.rerun()
                else:
                    st.error(f"❌ Upload failed: {result.get('error')}")

    # -----------------------
    # 🗑️ Delete Questions & Duration
    # -----------------------
    elif selected_tab == "🗑️ Delete Questions & Duration":
        # -----------------------
        # DELETE QUESTION SETS (Bulk)
        # -----------------------
        st.subheader("🗑 Delete Question Sets")
        cls = st.selectbox("Class", CLASSES, key="delete_class")
        sub = st.selectbox("Subject", SUBJECTS, key="delete_subject")

        if cls and sub:
            existing = get_questions_db(cls, sub)
            if existing:
                st.info(f"Found {len(existing)} questions for {cls} - {sub}")
                confirm = st.checkbox("⚠️ I confirm I want to delete ALL questions for this subject",
                                      value=False, key="confirm_delete")
                delete_btn = st.button("🗑️ Delete ALL Questions", type="primary", key="btn_delete_questions")
                if delete_btn:
                    if not confirm:
                        st.error("❌ Please check the confirmation box before deleting.")
                    else:
                        db = get_session()
                        try:
                            db.query(Question).filter(
                                Question.class_name == cls,
                                Question.subject == sub
                            ).delete()
                            db.commit()
                            st.success(f"✅ Deleted all {len(existing)} questions for {cls} - {sub}")
                        finally:
                            db.close()
                        st.rerun()
            else:
                st.warning(f"No questions found for {cls} - {sub}")

        st.divider()

    # ==============================
    # 🗂️ Archive / Restore Questions
    # ==============================
    elif selected_tab == "🗂️ Archive / Restore Questions":
        st.subheader("🗂️ Archive or Restore Questions")

        cls = st.selectbox("Select Class", CLASSES, key="archive_cls")
        sub = st.selectbox("Select Subject", SUBJECTS, key="archive_sub")
        show_archived = st.checkbox("👁️ Show Archived Questions", value=False, key="archive_show")

        if cls and sub:
            # Fetch questions
            # Fetch fresh questions after any changes
            questions = get_questions_db(cls, sub)
            total = len(questions)
            total_archived = sum(1 for q in questions if is_archived(q))
            total_active = total - total_archived

            st.info(f"📊 Total: {total} | ✅ Active: {total_active} | 💤 Archived: {total_archived}")

            # Then filter for display
            filtered_questions = [q for q in questions if is_archived(q) == show_archived]

            # Bulk actions
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗃️ Archive ALL Active", key="bulk_archive"):
                    db = get_session()
                    try:
                        updated = db.query(Question).filter(
                            Question.class_name == cls,
                            Question.subject == sub,
                            Question.archived.is_(False)
                        ).update({"archived": True, "archived_at": datetime.utcnow()})
                        db.commit()
                        st.success(f"🗃️ Archived {updated} questions.")
                    finally:
                        db.close()
                    st.rerun()

            with col2:
                if st.button("♻️ Restore ALL Archived", key="bulk_restore"):
                    db = get_session()
                    try:
                        updated = db.query(Question).filter(
                            Question.class_name == cls,
                            Question.subject == sub,
                            Question.archived.is_(True)
                        ).update({"archived": False, "archived_at": None})
                        db.commit()
                        st.success(f"♻️ Restored {updated} questions.")
                    finally:
                        db.close()
                    st.rerun()

            st.divider()

            # Show individual questions
            if not filtered_questions:
                st.warning(f"No {'archived' if show_archived else 'active'} questions for {cls} - {sub}")
            else:
                for idx, q in enumerate(filtered_questions):
                    q_id = q.get("id") if isinstance(q, dict) else getattr(q, "id", idx)

                    def safe_str(s):
                        return str(s) if s else ""

                    q_text = safe_str(
                        q.get("question_text") if isinstance(q, dict) else getattr(q, "question_text", ""))
                    q_answer = safe_str(q.get("correct_answer") if isinstance(q, dict) else getattr(q, "answer", ""))
                    q_options = q.get("options") if isinstance(q, dict) else getattr(q, "options", [])
                    q_options = q_options or []
                    q_archived = is_archived(q)

                    label = "♻️ Restore" if q_archived else "🗃️ Archive"
                    expander_title = f"Q{q_id}: {q_text[:60]}..." + (" 💤 [Archived]" if q_archived else "")

                    with st.expander(expander_title):
                        st.write(f"**Question:** {q_text}")
                        st.write(f"**Options:** {q_options}")
                        st.write(f"**Answer:** {q_answer}")

                        if st.button(label, key=f"archive_btn_{q_id}_{idx}"):
                            db = get_session()
                            try:
                                q_obj = db.query(Question).get(q_id)
                                if not q_obj:
                                    st.error(f"Question {q_id} not found.")
                                    continue

                                if q_archived:
                                    q_obj.archived = False
                                    q_obj.archived_at = None
                                    st.success(f"♻️ Question {q_id} restored successfully.")
                                else:
                                    q_obj.archived = True
                                    q_obj.archived_at = datetime.utcnow()
                                    st.success(f"🗃️ Question {q_id} archived successfully.")

                                db.commit()
                            finally:
                                db.close()
                            st.rerun()

            # Global download of all archived
            db = get_session()
            archived_all = db.query(Question).filter(Question.archived.is_(True)).order_by(
                Question.class_name.asc(), Question.subject.asc(), Question.id.asc()
            ).all()

            if archived_all:
                data_all = [
                    {
                        "ID": q.id,
                        "Class": q.class_name,
                        "Subject": q.subject,
                        "Question": q.question_text,
                        "Answer": q.answer,
                        "Options": ", ".join(q.options) if q.options else "",
                        "Archived At": q.archived_at.strftime("%Y-%m-%d %H:%M:%S") if q.archived_at else "",
                    }
                    for q in archived_all
                ]
                df_all = pd.DataFrame(data_all)
                st.download_button(
                    label="📥 Download ALL Archived Questions (CSV)",
                    data=df_all.to_csv(index=False),
                    file_name="all_archived_questions.csv",
                    mime="text/csv"
                )
            else:
                st.info("No archived questions found globally.")
            db.close()

        # -----------------------
        # SET DURATION SECTION
        # -----------------------
        st.subheader("⏱ Set Global Test Duration")
        from db_helpers import get_test_duration, set_test_duration  # import functions

        # Get current duration (in seconds) → convert to minutes for display
        current_duration_secs = get_test_duration()
        current_duration_mins = current_duration_secs // 60  # convert to minutes

        st.info(f"Current Test Duration: **{current_duration_mins} minutes**")

        # Input always in minutes
        new_duration_mins = st.number_input(
            "Enter New Duration (minutes):",
            min_value=1,
            max_value=180,
            value=current_duration_mins,
            step=5,
            key="new_duration_input"
        )

        if st.button("💾 Save New Duration", key="btn_save_duration"):
            set_test_duration(new_duration_mins)  # store in DB as minutes
            st.success(f"✅ Test duration updated to {new_duration_mins} minutes.")
            st.rerun()

    # -----------------------
    # 🏆 View Leaderboard (Per Subject)
    # -----------------------
    elif selected_tab == "🏆 View Leaderboard":
        st.subheader("🏆 Leaderboard")

        filter_input = st.text_input("🔍 Search by Name, Access Code, or Class (optional)", key="lb_filter")
        top_n = st.selectbox("Show Top N Students", options=[5, 10, 20, 50, 100, "All"], index=1)

        db = get_session()
        try:
            from sqlalchemy import select

            results = db.execute(
                select(Leaderboard, Student)
                .join(Student, Leaderboard.student_id == Student.id)
                .order_by(Leaderboard.score.desc())
            ).all()

        finally:
            db.close()

        if not results:
            st.info("No leaderboard data available yet.")
        else:
            # Convert results into DataFrame
            df = pd.DataFrame([
                {
                    "Student Name": s.name,
                    "Access Code": s.access_code,
                    "Class": s.class_name,
                    "Subject": getattr(lb, "subject", "Unknown"),  # optional if added later
                    "Score": round(lb.score, 2),
                    "Submitted At": lb.submitted_at.strftime("%Y-%m-%d %H:%M:%S")
                }
                for lb, s in results
            ])

            # If your Leaderboard table doesn’t yet have “subject”, we can derive from TestResult later

            # Filter if needed
            if filter_input.strip():
                df = df[
                    df["Student Name"].str.contains(filter_input.strip(), case=False) |
                    df["Access Code"].str.contains(filter_input.strip(), case=False) |
                    df["Class"].str.contains(filter_input.strip(), case=False)
                    ]
                if df.empty:
                    st.warning("No matching records found.")

            # Determine all subjects present
            subjects = sorted(df["Subject"].unique()) if "Subject" in df.columns else ["General"]

            tabs = st.tabs(subjects)

            for i, subject in enumerate(subjects):
                with tabs[i]:
                    df_sub = df[df["Subject"] == subject].sort_values(by="Score", ascending=False)
                    if top_n != "All":
                        df_sub = df_sub.head(int(top_n))

                    st.write(f"### 🧠 {subject} Leaderboard")
                    st.dataframe(df_sub, use_container_width=True)

                    st.download_button(
                        f"📥 Download {subject} CSV",
                        df_sub.to_csv(index=False).encode("utf-8"),
                        f"leaderboard_{subject.lower()}.csv",
                        "text/csv",
                        use_container_width=True
                    )

    # -----------------------
    # 🔄 Allow Retake
    # -----------------------
    elif selected_tab == "🔄 Allow Retake":
        code = st.text_input("Student Access Code")
        if code:
            student = get_student_by_access_code_db(code)
            if not student:
                st.error("Invalid code.")
            else:
                st.info(f"Student: {student.name} | Class: {student.class_name}")

                st.markdown("### Manage Retake Permissions")

                # 🔘 Toggle all subjects
                toggle_all = st.checkbox("Toggle All Subjects", key="toggle_all")

                subject_permissions = {}
                for subj in SUBJECTS:
                    current_allow = bool(get_retake_db(code, subj))

                    # If toggle_all is set, apply that to all checkboxes
                    if toggle_all:
                        current_allow = True

                    subject_permissions[subj] = st.checkbox(
                        subj,
                        value=current_allow,
                        key=f"allow_{subj}"
                    )

                # 🔘 Save all changes at once
                if st.button("💾 Save All Changes"):
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
            if st.button("📄 Generate Access Slips for All Students"):
                slips_df = df[["name", "class_name", "access_code"]]
                csv_data = slips_df.to_csv(index=False).encode("utf-8")
                st.download_button("⬇️ Download Access Slips CSV", csv_data, "access_slips.csv", "text/csv")
                st.success(f"✅ Generated {len(slips_df)} access slips successfully!")

    # -----------------------
    # ♻️ Reset Tests (UI + action)
    # -----------------------
    elif selected_tab == "♻️ Reset Tests":
        st.subheader("♻️ Reset Student Test Status")
        users = get_users()

        if users:
            student_codes = list(users.keys())
            student_options = [f"{users[code]['name']} ({users[code]['class_name']})" for code in student_codes]
            selected_idx = st.selectbox(
                "Select Student to Edit/Delete/Reset",
                range(len(student_codes)),
                format_func=lambda i: student_options[i]
            )

            selected_code = student_codes[selected_idx]
            selected_student = users[selected_code]

            st.write(f"✏️ Managing **{selected_student['name']}** (Class: {selected_student['class_name']})")

            new_name = st.text_input("Update Name", value=selected_student["name"])
            new_class = st.selectbox("Update Class", CLASSES, index=CLASSES.index(selected_student["class_name"]))

            col1, col2, col3 = st.columns(3)

            # ✅ Update student info
            with col1:
                if st.button("💾 Save Changes"):
                    update_student_db(selected_code, new_name, new_class)
                    st.success("✅ Student updated successfully!")
                    st.rerun()

            # 🗑️ Delete student
            with col2:
                if st.button("🗑️ Delete Student"):
                    delete_student_db(selected_code)
                    st.warning("⚠️ Student deleted.")
                    st.rerun()

            # ♻️ Reset student test attempts
            with col3:
                if st.button("♻️ Reset Test Attempt"):
                    reset_test(selected_code)
                    st.info(f"🔄 Test status for {selected_student['name']} has been reset.")
                    st.rerun()
        else:
            st.info("No students found.")

    # -----------------------
    # 📦 Data Export & Restore (super_admin)
    # -----------------------
    elif selected_tab == "📦 Data Export" and current_role == "super_admin":
        st.subheader("📦 Backup & Restore Database")

        # EXPORT
        st.markdown("### 🔽 Export Current Data")
        students = get_users()
        students_df = pd.DataFrame(students.values()) if students else pd.DataFrame()
        st.write(f"👥 Students: {len(students_df)} records")

        questions_list = []
        for cls in CLASSES:
            for sub in SUBJECTS:
                qs = get_questions_db(cls, sub)
                if qs:
                    questions_list.extend(qs)

        questions_data = [
            {
                "id": getattr(q, "id", ""),
                "class_name": getattr(q, "class_name", ""),
                "subject": getattr(q, "subject", ""),
                "question_text": getattr(q, "question_text", ""),
                "options": getattr(q, "options", ""),
                "answer": getattr(q, "correct_answer", "")
            }
            for q in questions_list
        ]
        questions_df = pd.DataFrame(questions_data) if questions_data else pd.DataFrame()
        st.write(f"❓ Questions: {len(questions_df)} records")

        subs = get_all_submissions_db()
        submissions_data = []
        if subs:
            for s in subs:
                submissions_data.append({
                    "Student": getattr(s, "student_name", ""),
                    "Class": getattr(s, "class_name", ""),
                    "Subject": getattr(s, "subject", ""),
                    "Score": getattr(s, "score", ""),
                    "Date": getattr(s, "timestamp", "")
                })
        submissions_df = pd.DataFrame(submissions_data) if submissions_data else pd.DataFrame()
        st.write(f"📝 Submissions: {len(submissions_df)} records")

        # CSV downloads
        col1, col2, col3 = st.columns(3)
        with col1:
            st.download_button("⬇️ Students CSV", students_df.to_csv(index=False), "students.csv")
        with col2:
            st.download_button("⬇️ Questions CSV", questions_df.to_csv(index=False), "questions.csv")
        with col3:
            st.download_button("⬇️ Submissions CSV", submissions_df.to_csv(index=False), "submissions.csv")

        # Excel download
        excel_bytes = excel_download_buffer({
            "Students": students_df,
            "Questions": questions_df,
            "Submissions": submissions_df
        })
        st.download_button("⬇️ Download All Data (Excel)", data=excel_bytes, file_name="smarttest_backup.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # JSON full backup
        full_backup = {
            "students": students,
            "questions": questions_data,
            "submissions": submissions_data,
        }
        json_bytes = json.dumps(full_backup, indent=2).encode("utf-8")
        st.download_button("⬇️ Full JSON Backup", json_bytes, "smarttest_backup.json", mime="application/json")

        st.divider()

        # RESTORE
        st.markdown("### 🔄 Restore From Backup")
        uploaded_backup = st.file_uploader("Upload Backup JSON", type=["json"])
        if uploaded_backup:
            try:
                backup_data = json.load(uploaded_backup)
                st.info(
                    f"Backup contains: {len(backup_data.get('students', []))} students, "
                    f"{len(backup_data.get('questions', []))} questions, "
                    f"{len(backup_data.get('submissions', []))} submissions."
                )

                st.warning("⚠️ Restoring will erase ALL current students, questions, and submissions!")
                confirm = st.checkbox("✅ I understand and want to proceed")
                if confirm and st.button("🔄 Confirm & Restore"):
                    # simple restore logic: clear existing then bulk insert
                    clear_students_db()
                    clear_questions_db()
                    clear_submissions_db()

                    # Insert students
                    students_in = backup_data.get("students", {})
                    if isinstance(students_in, dict):
                        # If exported as dict {code: {...}} keep values
                        students_in = list(students_in.values())
                    for s in students_in:
                        # expected format to match add_student_db signature,
                        # safest approach is to call low-level insert via db helpers (you may adapt)
                        add_student_db(s.get("name", ""), s.get("class_name", ""))
                    # Insert questions (simple insertion)
                    for q in backup_data.get("questions", []):
                        try:
                            add_question_db(q.get("class_name", ""), q.get("question_text", ""), json.loads(q.get("options")) if isinstance(q.get("options"), str) else q.get("options", []), q.get("answer", ""))
                        except Exception:
                            # fallback: try to insert raw
                            add_question_db(q.get("class_name", ""), q.get("question_text", ""), q.get("options", []), q.get("answer", ""))

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


# entrypoint for app (if used directly)
if __name__ == "__main__":
    ensure_super_admin_exists()
    run_admin_mode()
