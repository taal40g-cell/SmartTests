import streamlit as st
from database import engine, test_db_connection
from models import Base
from db_helpers import ensure_super_admin_exists

# ==============================
# Step 1: Create tables
# ==============================

# ==============================
# Step 4: Import UI components
# ==============================
from ui import set_background
from selections.student import run_student_mode
from selections.admin import run_admin_mode

# ==============================
# Step 5: Session state defaults
# ==============================
st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("access_code", "")
st.session_state.setdefault("menu_selection", "Student Mode")
st.session_state.setdefault("trigger_refresh", False)
st.session_state.setdefault("admin_username", "")
st.session_state.setdefault("admin_logged_in", False)

# --- Results page ---
def results_page():
    query_params = st.query_params
    access_code = query_params.get("access_code", [None])[0]

    st.title("Results Page" if access_code else "SmarTest App")
    if access_code:
        st.success(f"Showing results for access code: {access_code}")
    else:
        st.write("No access code provided. Use Student/Admin menu below.")


# --- Main app ---
def main():
    set_background("assets/sic.png")

    # Handle results page query param
    page = st.query_params.get("page", [None])[0]
    if page == "results":
        results_page()
        return

    # App header
    st.markdown(
        "<h1 style='text-align: center; text-decoration: underline; "
        "font-weight: bold; color: white; background-color: '></h1>",
        unsafe_allow_html=True
    )

    # Refresh logic
    if st.session_state.get("trigger_refresh", False):
        st.session_state.trigger_refresh = False
        st.session_state.menu_selection = "Student Mode"
        st.rerun()

    # --- Sidebar menu ---
    st.sidebar.subheader("📋 Main Menu")
    menu_options = ["Student Mode", "Admin Panel", "Exit App"]
    mode = st.sidebar.radio("Select Mode", menu_options, key="menu_selection")

    # --- Sidebar database test button ---
    if st.sidebar.button("🧩 Test Database Connection"):
        if test_db_connection():
            st.sidebar.success("✅ Database connected successfully!")
        else:
            st.sidebar.error("❌ Failed to connect to database.")

    # --- Mode selection ---
    if mode == "Student Mode":
        run_student_mode()
    elif mode == "Admin Panel":
        run_admin_mode()
    elif mode == "Exit App":
        st.session_state.clear()
        st.session_state.menu_selection = "Student Mode"
        st.success("👋 All sessions cleared.")
        st.rerun()


if __name__ == "__main__":
    main()
