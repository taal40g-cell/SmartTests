import streamlit as st
from helpers import (
    require_admin_login,
    add_user_ui,
    load_users,
    save_users,
    generate_access_code,
    generate_access_slips,
    load_admin_config,
    save_admin_config,
    delete_question_file,
    change_admin_password_ui,
    load_leaderboard,
)

def run_admin_mode():
    if not require_admin_login():
        return
    st.markdown("""
        <style>
        /* Target the selectbox container */
        div[data-baseweb="select"] > div {
            transition: background-color 0.3s ease;
            border-radius: 10px;
        }

        /* Hover effect on the selectbox */
        div[data-baseweb="select"] > div:hover {
            background-color: #800080; /* Purple */
            color: white;
        }

        /* Make the text inside selectbox white for contrast */
        div[data-baseweb="select"] span {
            color: white;
            font-weight: bold;
        }
        </style>
    """, unsafe_allow_html=True)

    st.sidebar.title("Admin Panel")
    selected_tab = st.sidebar.selectbox("Choose Action", [
        "Add User",
        "Bulk Add Students",
        "Change Password",
        "Upload Questions",
        "Delete Questions & Set Duration",
        "View Leaderboard",
        "Allow Retake Access",
        "Generate Access Slips",
        "Logout"
    ])

    st.title("Admin Dashboard")

    if selected_tab == "Add User":
        add_user_ui()

    elif selected_tab == "Bulk Add Students":
        st.subheader("Bulk Add Students")
        uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
        if uploaded_file:
            import pandas as pd
            df = pd.read_csv(uploaded_file)
            if "name" in df.columns and "class" in df.columns:
                users = load_users()
                for _, row in df.iterrows():
                    access_code = generate_access_code(row["name"])
                    users.append({
                        "name": row["name"],
                        "class": row["class"],
                        "access_code": access_code,
                        "can_retake": True
                    })
                save_users(users)
                st.success("Bulk users added.")
            else:
                st.error("CSV must have 'name' and 'class' columns.")

    elif selected_tab == "Change Password":
        change_admin_password_ui()

    elif selected_tab == "Upload Questions":
        st.subheader("Upload Questions")
        classes = ["JHS1", "JHS2", "JHS3"]
        subjects = ["English", "Math", "Science"]
        selected_class = st.selectbox("Class", classes)
        selected_subject = st.selectbox("Subject", subjects)
        uploaded = st.file_uploader("Upload Questions JSON", type=["json"])
        if uploaded:
            import json
            try:
                questions = json.loads(uploaded.read().decode("utf-8"))
                from helpers import save_questions
                save_questions(selected_class, selected_subject, questions)
                st.success(f"Uploaded {len(questions)} questions for {selected_class} - {selected_subject}")
            except Exception:
                st.error("Invalid JSON.")

    elif selected_tab == "Delete Questions & Set Duration":
        st.subheader("Manage Questions / Duration")
        classes = ["JHS1", "JHS2", "JHS3"]
        subjects = ["English", "Math", "Science"]
        sel_cls = st.selectbox("Class", classes)
        sel_sub = st.selectbox("Subject", subjects)
        if st.button("Delete Questions"):
            delete_question_file(sel_cls, sel_sub)
            st.success("Questions deleted.")

        admin_config = load_admin_config()
        duration = st.slider("Test Duration (minutes)", 5, 120, admin_config.get("duration", 30))
        if st.button("Save Duration"):
            save_admin_config({"duration": duration})
            st.success("Duration saved.")

    elif selected_tab == "View Leaderboard":
        st.subheader("Leaderboard")
        lb = load_leaderboard()
        if lb:
            import pandas as pd
            st.dataframe(pd.DataFrame(lb))
        else:
            st.info("No entries yet.")

    elif selected_tab == "Allow Retake Access":
        st.subheader("Toggle Retake Access")
        users = load_users()
        if users:
            for idx, user in enumerate(users):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**{user['name']} ({user['class']}) - {user['access_code']}**")
                with col2:
                    current = user.get("can_retake", True)
                    new_val = st.checkbox("Allow", value=current, key=f"retake_{idx}")
                    if new_val != current:
                        users[idx]["can_retake"] = new_val
                        save_users(users)
                        st.success(f"Updated retake for {user['name']}")
        else:
            st.info("No users found.")

    elif selected_tab == "Generate Access Slips":
        st.subheader("Access Slips")
        users = load_users()
        if st.button("Generate & Download ZIP"):
            zip_buffer = generate_access_slips(users)
            st.download_button("Download ZIP", zip_buffer, file_name="AccessSlips.zip")

    elif selected_tab == "Logout":
        st.session_state["admin_logged_in"] = False
        st.success("Logged out.")
        st.rerun()
