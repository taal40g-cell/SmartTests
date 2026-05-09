import streamlit as st
import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")

# Load .env once
load_dotenv(ENV_PATH)

ENV = os.getenv("ENV", "local")

# Debug ONLY ONCE
if "env_debug_done" not in st.session_state:
    print("📁 BASE_DIR:", BASE_DIR)
    print("📄 ENV_PATH:", ENV_PATH)
    print("📄 EXISTS:", os.path.exists(ENV_PATH))
    print("🚀 ENV =", ENV)
    print("📁 WORKING DIR:", os.getcwd())
    st.session_state.env_debug_done = True
# ==============================
# SAFE IMPORTS
# ==============================
from backend import database   # ✅ THIS WAS MISSING
from backend.ui import set_background
from selections.student import run_student_mode
from selections.admin import run_admin_mode
from backend.db_helpers import ensure_super_admin_exists


# ==============================
# SESSION DEFAULTS (MUST BE FIRST)
# ==============================
st.session_state.setdefault("menu_selection", "Student Mode")
st.session_state.setdefault("db_initialized", False)
st.session_state.setdefault("trigger_refresh", False)
st.session_state.setdefault("admin_logged_in", False)
st.session_state.setdefault("logged_in", False)


# ==============================
# DB BOOTSTRAP (SAFE)
# ==============================
if not st.session_state.db_initialized:
    try:
        database.startup()               # ✅ now works
        ensure_super_admin_exists()
        st.session_state.db_initialized = True

    except Exception as e:
        st.error("⚠️ Database not available. App will run in limited mode.")
        st.exception(e)

# ==============================
# UI SETUP
# ==============================
set_background()


# ==============================
# RESULTS PAGE
# ==============================
def results_page():
    query_params = st.query_params
    access_code = query_params.get("access_code", [None])[0]

    st.title("Results Page" if access_code else "SmartTest App")

    if access_code:
        st.success(f"Showing results for access code: {access_code}")
    else:
        st.write("No access code provided.")


# ==============================
# MAIN APP
# ==============================
def main():

    # Handle query param routing
    page = st.query_params.get("page", [None])[0]
    if page == "results":
        results_page()
        return

    # ==========================
    # SIDEBAR MENU
    # ==========================
    st.sidebar.subheader("📋 Main Menu")

    menu_buttons = [
        ("🎓 Student Mode", "Student Mode"),
        ("🛠️ Admin Panel", "Admin Panel"),
        ("🚪 Exit App", "Exit App")
    ]

    for label, mode_name in menu_buttons:
        if st.sidebar.button(label, use_container_width=True):
            st.session_state.menu_selection = mode_name
            st.rerun()

    from sqlalchemy import text  # ✅ add this at top

    # ==========================
    # DB TEST BUTTON (SAFE)
    # ==========================
    st.sidebar.markdown("---")

    if st.sidebar.button("🧪 Test Database"):
        try:
            engine = database.get_engine()
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchall()  # force execution

            st.sidebar.success("✅ DB Connected")

        except Exception as e:
            st.sidebar.error("❌ DB Failed")
            st.sidebar.exception(e)
    # ==========================
    # ROUTING
    # ==========================
    mode = st.session_state.menu_selection

    if mode == "Student Mode":
        run_student_mode()

    elif mode == "Admin Panel":
        run_admin_mode()

    elif mode == "Exit App":
        st.session_state.clear()
        st.session_state.menu_selection = "Student Mode"
        st.success("👋 Session cleared")
        st.rerun()


# ==============================
# RUN APP
# ==============================
if __name__ == "__main__":
    main()