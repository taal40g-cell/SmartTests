# ============================================
# app.py — SmartTest Admin (Full Clean Rewrite)
# ============================================

import os
import json
import time
import io
from datetime import datetime
import pandas as pd
import streamlit as st

# === Local imports (adjust paths if your helper file lives elsewhere) ===
# Subject & utility helpers (from the helper module you created)
from ui import (
    CLASSES,
    load_subjects,
    save_subjects,
    manage_subjects_ui,
    df_download_button,
    excel_download_buffer,is_archived
)

# Models
from models import Leaderboard, Student

# DB helpers
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
    get_test_duration,
    set_test_duration,
)

# ==============================
# Role tabs
# ==============================
ROLE_TABS = {
    "super_admin": [
        "➕ Add User",
        "📥 Bulk Add Students",
        "👥 Manage Students",
        "🛡️ Manage Admins",
        "📚 Manage Subjects",
        "🔑 Change Password",
        "📤 Upload Questions",
        "🗑️ Delete Questions & Duration",
        "🗂️ Archive / Restore Questions",
        "⏱ Set Duration",
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
        "📚 Manage Subjects",
        "🔑 Change Password",
        "📤 Upload Questions",
        "🗑️ Delete Questions & Duration",
        "🗂️ Archive / Restore Questions",
        "⏱ Set Duration",
        "🏆 View Leaderboard",
        "🔄 Allow Retake",
        "🖨️ Generate Access Slips",
        "♻️ Reset Tests",
        "🚪 Logout"
    ],
    "teacher": [
        "👥 Manage Students",
        "📚 Manage Subjects",
        "📤 Upload Questions",
        "🗑️ Delete Questions & Duration",
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

    current_user = st.session_state.get("admin_username", "")
    all_admins = get_admins(as_dict=True)
    current_role = all_admins.get(current_user, "admin")
    available_tabs = ROLE_TABS.get(current_role, ROLE_TABS["admin"])

    st.sidebar.title(f"⚙️ Admin Panel ({current_user} – {current_role})")
    selected_tab = st.sidebar.radio("Choose Action", available_tabs, key="selected_tab_radio")
    st.session_state["selected_tab"] = selected_tab

    st.title("🛠️ SmartTest — Admin Dashboard")

    # -----------------------
    # ➕ Add single student
    # -----------------------
    if selected_tab == "➕ Add User":
        st.subheader("Add a Student")
        name = st.text_input("Student Name", key="add_name")
        class_name = st.selectbox("Class", CLASSES, key="add_class")

        if st.button("Add Student", key="add_student_btn"):
            if not name or not name.strip():
                st.error("❌ Enter student name.")
            else:
                student_info = add_student_db(name.strip(), class_name)
                st.success(
                    f"✅ {student_info['name']} added | "
                    f"Class: {student_info['class_name']} | "
                    f"Access Code: {student_info['access_code']} | "
                    f"Unique ID: {student_info['unique_id']}"
                )

    # -----------------------
    # 📥 Bulk Add Students
    # -----------------------
    elif selected_tab == "📥 Bulk Add Students":
        st.subheader("📥 Bulk Upload Students (CSV)")
        uploaded = st.file_uploader("Upload CSV with columns 'name' & 'class'", type=["csv"], key="bulk_students")
        if uploaded:
            try:
                df = pd.read_csv(uploaded)
                if not {"name", "class"}.issubset(df.columns):
                    st.error("❌ CSV must have 'name' and 'class' columns")
                else:
                    students_list = [(str(r["name"]).strip(), str(r["class"]).strip()) for _, r in df.iterrows()]
                    result = bulk_add_students_db(students_list)
                    summary = result.get("summary", {})
                    st.success(f"✅ {summary.get('new',0)} new students added!")
                    if summary.get("reused"):
                        st.info(f"♻️ {summary['reused']} existing students reused.")
                    for student in result.get("students", []):
                        if student.get("status") == "new":
                            icon = "✅"
                        else:
                            icon = "♻️"
                        st.markdown(
                            f"{icon} **{student.get('name')}** | Class: {student.get('class_name')} | "
                            f"Access Code: `{student.get('access_code')}`"
                        )
                    added_students = [s for s in result.get("students", []) if s.get("status") == "new"]
                    if added_students:
                        df_added = pd.DataFrame(added_students)
                        csv_data = df_added.to_csv(index=False).encode("utf-8")
                        st.download_button("📥 Download Added Students CSV", csv_data, "bulk_added_students.csv", "text/csv")
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

            records = df.to_dict("records")
            student_ids = [r["id"] for r in records]
            selected_id = st.selectbox("Select Student ID", student_ids, key="manage_student_select")

            if selected_id:
                selected_student = next((u for u in users.values() if u["id"] == selected_id), None)
                if selected_student:
                    st.write(f"✏️ Editing **{selected_student['name']}** (Class: {selected_student['class_name']})")
                    new_name = st.text_input("Update Name", value=selected_student["name"], key="upd_name")
                    new_class = st.selectbox("Update Class", CLASSES, index=CLASSES.index(selected_student["class_name"]), key="upd_class")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("💾 Save Changes", key="save_student_changes"):
                            update_student_db(selected_id, new_name.strip(), new_class)
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
        admins = get_admins()
        df_admins = pd.DataFrame([{"username": a.username, "role": a.role} for a in admins])
        st.dataframe(df_admins, use_container_width=True)

        st.subheader("➕ Add / Update Admin")
        new_user = st.text_input("👤 Username", key="admin_new_user")
        new_pass = st.text_input("🔑 Password", type="password", key="admin_new_pass")
        confirm_pass = st.text_input("🔑 Confirm Password", type="password", key="admin_confirm_pass")
        new_role = st.selectbox("🎭 Role", ["admin", "teacher", "moderator", "super_admin"], key="admin_new_role")

        if st.button("Add / Update Admin", key="add_update_admin_btn"):
            if not new_user.strip() or not new_pass:
                st.error("❌ Username & password required.")
            elif new_pass != confirm_pass:
                st.error("❌ Password and Confirm Password do not match.")
            else:
                ok = set_admin(new_user.strip(), new_pass.strip(), new_role)
                if ok:
                    st.success(f"✅ Admin '{new_user}' added or updated.")
                    st.rerun()
                else:
                    st.error("❌ Failed to add or update admin.")

    # -----------------------
    # 📚 Manage Subjects
    # -----------------------
    elif selected_tab == "📚 Manage Subjects":
        st.subheader("📚 Manage Subjects")
        subjects = load_subjects()

        st.write("### 📋 Current Subjects")
        if subjects:
            for i, subj in enumerate(subjects):
                c1, c2 = st.columns([8, 1])
                c1.write(f"{i+1}. {subj}")
                # delete button with confirm
                if c2.button("🗑️", key=f"del_subject_{i}"):
                    confirm_key = f"confirm_del_{i}"
                    confirm = st.checkbox(f"Confirm delete {subj}", key=confirm_key)
                    if confirm:
                        subjects.pop(i)
                        save_subjects(subjects)
                        st.success(f"✅ Deleted subject: {subj}")
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
                save_subjects(sorted(subjects))
                st.success(f"Added subject: {name}")
                st.rerun()
        st.caption("Subjects are stored in `subjects.json`. Edit there if needed.")

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
    # 📤 Upload Questions
    # -----------------------
    elif selected_tab == "📤 Upload Questions":
        st.subheader("📤 Upload Questions to Database")

        cls = st.selectbox("Select Class", CLASSES, key="upload_class")
        sub_list = load_subjects()
        sub = st.selectbox("Select Subject", sub_list, key="upload_subject")

        existing_count = count_questions_db(cls, sub)
        st.info(f"📊 Currently {existing_count} questions in DB for {cls} - {sub}")

        if st.button("🔍 Preview Existing Questions", key="preview_btn"):
            data = preview_questions_db(cls, sub, limit=10)
            if data:
                st.json(data)
            else:
                st.info("No questions found for this selection yet.")

        uploaded = st.file_uploader("📁 Upload Question JSON file", type=["json"], key="upload_file")
        if uploaded is not None:
            st.success(f"✅ File selected: {uploaded.name}")
            if st.button("✅ Confirm Upload", key="confirm_upload_btn"):
                try:
                    content = uploaded.read().decode("utf-8", errors="ignore").strip()
                    uploaded.seek(0)

                    # quick normalization for pasted arrays
                    if "][" in content:
                        content = content.replace("][", "],[")

                    if not content.startswith("["):
                        content = "[" + content
                    if not content.endswith("]"):
                        content = content + "]"

                    try:
                        valid_questions = json.loads(content)
                    except json.JSONDecodeError:
                        # fallback: extract objects
                        import re
                        content_clean = re.sub(r",\s*(\]|\})", r"\1", content)
                        matches = re.findall(r"\{.*?\}", content_clean, flags=re.DOTALL)
                        valid_questions = [json.loads(m) for m in matches]

                    if not isinstance(valid_questions, list):
                        st.error("⚠️ JSON must be a list of question objects.")
                        st.stop()

                    cleaned_questions = []
                    for idx, q in enumerate(valid_questions, start=1):
                        if not isinstance(q, dict):
                            st.error(f"⚠️ Question {idx} is not an object.")
                            st.stop()
                        missing = [k for k in ["question", "options", "answer"] if k not in q]
                        if missing:
                            st.error(f"⚠️ Question {idx} missing fields: {', '.join(missing)}")
                            st.stop()

                        question = str(q.get("question", "")).strip()
                        options = q.get("options", [])
                        answer = str(q.get("answer", "")).strip()

                        if isinstance(options, str):
                            options = [o.strip() for o in options.split(",") if o.strip()]

                        if not question:
                            st.error(f"⚠️ Question {idx} has empty text.")
                            st.stop()
                        if not isinstance(options, list) or len(options) < 2:
                            st.error(f"⚠️ Question {idx} must have at least 2 options.")
                            st.stop()
                        if not answer:
                            st.error(f"⚠️ Question {idx} missing answer.")
                            st.stop()

                        cleaned_questions.append({
                            "question": question,
                            "options": options,
                            "answer": answer
                        })

                    result = handle_uploaded_questions(cls, sub, cleaned_questions)
                    if result.get("success"):
                        st.success(f"🎯 Uploaded {result.get('inserted',0)} new questions (replaced {result.get('deleted',0)} old ones).")
                        st.cache_data.clear()
                        st.info("🧠 Cache cleared — students will load updated questions.")
                        st.session_state.pop("upload_file", None)
                        st.rerun()
                    else:
                        st.error(f"❌ Upload failed: {result.get('error')}")
                except Exception as e:
                    st.error(f"❌ Upload failed: {e}")

    # -----------------------
    # 🗑️ Delete Questions & Duration
    # -----------------------
    elif selected_tab == "🗑️ Delete Questions & Duration":
        st.subheader("🗑 Delete Question Sets")

        cls = st.selectbox("Select Class", CLASSES, key="delete_class")
        sub_list = load_subjects()
        sub = st.selectbox("Select Subject", sub_list, key="delete_subject")

        if cls and sub:
            db = get_session()
            try:
                cls_lower = cls.strip().lower()
                sub_lower = sub.strip().lower()
                existing = db.query(Question).filter(Question.class_name == cls_lower, Question.subject == sub_lower).all()
                if existing:
                    st.info(f"📚 Found {len(existing)} questions for {cls} - {sub}")
                    confirm = st.checkbox(f"⚠️ Confirm deletion of ALL questions for {cls} - {sub}", key="confirm_delete_questions")
                    if st.button("🗑️ Delete ALL Questions", key="delete_all_questions_btn"):
                        if not confirm:
                            st.error("❌ Please confirm before deleting.")
                        else:
                            deleted_count = db.query(Question).filter(Question.class_name == cls_lower, Question.subject == sub_lower).delete(synchronize_session=False)
                            db.commit()
                            st.success(f"✅ Deleted {deleted_count} questions for {cls} - {sub}")
                            st.cache_data.clear()
                            st.rerun()
                else:
                    st.warning(f"No questions found for {cls} - {sub}")
            except Exception as e:
                db.rollback()
                st.error(f"❌ Error deleting questions: {e}")
            finally:
                db.close()

        st.divider()
        # Duration section (moved here for convenience)
        st.subheader("⏱ Set Global Test Duration")
        try:
            current_duration_secs = get_test_duration() or 600
        except Exception:
            current_duration_secs = 600
        current_duration_mins = max(1, current_duration_secs // 60)
        st.info(f"Current Test Duration: **{current_duration_mins} minutes**")
        new_duration_mins = st.number_input("Enter New Duration (minutes):", min_value=1, max_value=180, value=current_duration_mins, step=5, key="new_duration_input")
        if st.button("💾 Save New Duration", key="save_duration_btn"):
            try:
                set_test_duration(new_duration_mins)
                st.success(f"✅ Test duration updated to {new_duration_mins} minutes.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Failed to save duration: {e}")

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

            # -----------------------
            # 🗃️ Archive / Restore
            # -----------------------
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

            # Global archived download
            db = get_session()
            try:
                archived_all = db.query(Question).filter(Question.archived.is_(True)).order_by(Question.class_name.asc(), Question.subject.asc(), Question.id.asc()).all()
                if archived_all:
                    data_all = []
                    for q in archived_all:
                        data_all.append({
                            "ID": q.id,
                            "Class": q.class_name,
                            "Subject": q.subject,
                            "Question": q.question_text,
                            "Answer": getattr(q, "correct_answer", "") or getattr(q, "answer", ""),
                            "Options": ", ".join(q.options) if getattr(q, "options", None) else "",
                            "Archived At": q.archived_at.strftime("%Y-%m-%d %H:%M:%S") if q.archived_at else ""
                        })
                    df_all = pd.DataFrame(data_all)
                    st.download_button("📥 Download ALL Archived Questions (CSV)", df_all.to_csv(index=False).encode("utf-8"), "all_archived_questions.csv", "text/csv")
                else:
                    st.info("No archived questions found globally.")
            finally:
                db.close()

    # -----------------------
    # 🏆 Leaderboard
    # -----------------------
    elif selected_tab == "🏆 View Leaderboard":
        st.subheader("🏆 Leaderboard")
        filter_input = st.text_input("🔍 Search by Name, Access Code, or Class (optional)", key="lb_filter")
        top_n = st.selectbox("Show Top N Students", options=[5, 10, 20, 50, 100, "All"], index=1)

        db = get_session()
        try:
            from sqlalchemy import select
            results = (
                db.query(Leaderboard, Student)
                .join(Student, Leaderboard.student_id == Student.id)
                .order_by(Leaderboard.score.desc())
                .all()
            )

        finally:
            db.close()

        if not results:
            st.info("No leaderboard data available yet.")
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
                df = df[df["Student Name"].str.contains(filter_input.strip(), case=False) |
                        df["Access Code"].str.contains(filter_input.strip(), case=False) |
                        df["Class"].str.contains(filter_input.strip(), case=False)]
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
                    st.download_button(f"📥 Download {subject} CSV", df_sub.to_csv(index=False).encode("utf-8"), f"leaderboard_{subject.lower()}.csv", "text/csv")

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
    # ♻️ Reset Tests
    # -----------------------
    elif selected_tab == "♻️ Reset Tests":
        st.subheader("♻️ Reset Student Test Status")
        users = get_users()
        if users:
            student_codes = list(users.keys())
            student_options = [f"{users[code]['name']} ({users[code]['class_name']})" for code in student_codes]
            selected_idx = st.selectbox("Select Student to Edit/Delete/Reset", range(len(student_codes)), format_func=lambda i: student_options[i], key="reset_select")
            selected_code = student_codes[selected_idx]
            selected_student = users[selected_code]
            st.write(f"✏️ Managing **{selected_student['name']}** (Class: {selected_student['class_name']})")
            new_name = st.text_input("Update Name", value=selected_student["name"], key="reset_new_name")
            new_class = st.selectbox("Update Class", CLASSES, index=CLASSES.index(selected_student["class_name"]) if selected_student["class_name"] in CLASSES else 0, key="reset_new_class")
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("💾 Save Changes", key="reset_save_btn"):
                    update_student_db(selected_code, new_name, new_class)
                    st.success("✅ Student updated successfully!")
                    st.rerun()
            with col2:
                if st.button("🗑️ Delete Student", key="reset_delete_btn"):
                    delete_student_db(selected_code)
                    st.warning("⚠️ Student deleted.")
                    st.rerun()
            with col3:
                if st.button("♻️ Reset Test Attempt", key="reset_attempt_btn"):
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
        st.markdown("### 🔽 Export Current Data")
        students = get_users()
        students_df = pd.DataFrame(students.values()) if students else pd.DataFrame()
        st.write(f"👥 Students: {len(students_df)} records")
        questions_list = []
        for cls in CLASSES:
            for sub in load_subjects():
                qs = get_questions_db(cls, sub)
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
                "answer": getattr(q, "correct_answer", "") or getattr(q, "answer", "")
            })
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

        col1, col2, col3 = st.columns(3)
        with col1:
            st.download_button("⬇️ Students CSV", students_df.to_csv(index=False), "students.csv")
        with col2:
            st.download_button("⬇️ Questions CSV", questions_df.to_csv(index=False), "questions.csv")
        with col3:
            st.download_button("⬇️ Submissions CSV", submissions_df.to_csv(index=False), "submissions.csv")

        excel_bytes = excel_download_buffer({"Students": students_df, "Questions": questions_df, "Submissions": submissions_df})
        st.download_button("⬇️ Download All Data (Excel)", data=excel_bytes, file_name="smarttest_backup.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        full_backup = {"students": students, "questions": questions_data, "submissions": submissions_data}
        json_bytes = json.dumps(full_backup, indent=2).encode("utf-8")
        st.download_button("⬇️ Full JSON Backup", json_bytes, "smarttest_backup.json", mime="application/json")

        st.markdown("---")
        st.markdown("### 🔄 Restore From Backup")
        uploaded_backup = st.file_uploader("Upload Backup JSON", type=["json"], key="restore_backup")
        if uploaded_backup:
            try:
                backup_data = json.load(uploaded_backup)
                st.info(f"Backup contains: {len(backup_data.get('students', []))} students, {len(backup_data.get('questions', []))} questions, {len(backup_data.get('submissions', []))} submissions.")
                st.warning("⚠️ Restoring will erase ALL current students, questions, and submissions!")
                confirm = st.checkbox("✅ I understand and want to proceed", key="confirm_restore")
                if confirm and st.button("🔄 Confirm & Restore", key="confirm_restore_btn"):
                    clear_students_db()
                    clear_questions_db()
                    clear_submissions_db()
                    students_in = backup_data.get("students", {})
                    if isinstance(students_in, dict):
                        students_in = list(students_in.values())
                    for s in students_in:
                        add_student_db(s.get("name", ""), s.get("class_name", ""))
                    for q in backup_data.get("questions", []):
                        try:
                            opts = q.get("options", [])
                            if isinstance(opts, str):
                                opts = json.loads(opts) if opts.startswith("[") else [x.strip() for x in opts.split(",") if x.strip()]
                        except Exception:
                            opts = q.get("options", []) or []
                        add_question_db(q.get("class_name", ""), q.get("question_text", ""), opts, q.get("answer", ""))
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
