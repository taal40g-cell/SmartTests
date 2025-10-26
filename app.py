import streamlit as st
from database import engine, test_db_connection
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

    st.title("Results Page" if access_code else "SmartTest App")
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
        "<h1 style='text-align: center; text-decoration: underline; font-weight: bold; color: white;'></h1>",
        unsafe_allow_html=True
    )

    # Refresh logic
    if st.session_state.get("trigger_refresh", False):
        st.session_state.trigger_refresh = False
        st.session_state.menu_selection = "Student Mode"
        st.rerun()

    # ============================
    # 🎯 Sidebar Navigation Buttons
    # ============================
    st.sidebar.subheader("📋 Main Menu")

    # Sidebar custom style
    st.sidebar.markdown("""
        <style>
        div[data-testid="stSidebar"] div[data-testid="stButton"] > button {
            background-color: #f0f2f6;
            color: #333;
            border: none;
            border-radius: 10px;
            padding: 0.6em 1em;
            width: 100%;
            text-align: left;
            font-weight: 500;
            font-size: 15px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            transition: all 0.2s ease-in-out;
            margin-bottom: 6px;
        }
        div[data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {
            background-color: #007bff !important;
            color: white !important;
            transform: translateY(-2px);
        }
        .selected-mode {
            background-color: #0066cc !important;
            color: white !important;
            font-weight: 600;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }
        </style>
    """, unsafe_allow_html=True)

    # Initialize mode if not set
    if "menu_selection" not in st.session_state:
        st.session_state.menu_selection = "Student Mode"

    # Button layout
    menu_buttons = [
        ("🎓 Student Mode", "Student Mode"),
        ("🛠️ Admin Panel", "Admin Panel"),
        ("🚪 Exit App", "Exit App")
    ]

    for label, mode_name in menu_buttons:
        key = f"mode_btn_{mode_name.replace(' ', '_').lower()}"
        is_active = st.session_state.menu_selection == mode_name

        # Apply selected style dynamically
        if is_active:
            st.sidebar.markdown(
                f"<style>div[data-testid='stSidebar'] div[data-testid='stButton'][key='{key}'] button{{background-color:#0066cc;color:white;font-weight:600;}}</style>",
                unsafe_allow_html=True
            )

        if st.sidebar.button(label, key=key, use_container_width=True):
            st.session_state.menu_selection = mode_name
            st.rerun()

    # ============================
    # 🧩 Sidebar Test Connection
    # ============================
    st.sidebar.markdown("---")
    if st.sidebar.button("🧩 Test Database Connection"):
        if test_db_connection():
            st.sidebar.success("✅ Database connected successfully!")
        else:
            st.sidebar.error("❌ Failed to connect to database.")

    # ============================
    # 📍 Load Selected Section
    # ============================
    mode = st.session_state.menu_selection
    if mode == "Student Mode":
        run_student_mode()
    elif mode == "Admin Panel":
        run_admin_mode()
    elif mode == "Exit App":
        st.session_state.clear()
        st.session_state.menu_selection = "Student Mode"
        st.success("👋 All sessions cleared.")
        st.rerun()


# --- Run the app ---
if __name__ == "__main__":
    main()
