import streamlit as st
from ui import set_background
from selections.student import run_student_mode
from selections.admin import run_admin_mode
import json

# --- Load admin configuration ---
# --- Clear cached data/resources on every run ---
st.cache_data.clear()
st.cache_resource.clear()

# --- Session state defaults ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "access_code" not in st.session_state:
    st.session_state.access_code = ""
if "menu_selection" not in st.session_state:
    st.session_state.menu_selection = "Student Mode"
if "trigger_refresh" not in st.session_state:
    st.session_state.trigger_refresh = False


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
    # Always reset background to latest version
    set_background("assets/scr.png")

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
    if st.session_state.trigger_refresh:
        st.session_state.trigger_refresh = False
        st.session_state.menu_selection = "Student Mode"
        st.rerun()

    # Sidebar menu
    menu_options = ["Student Mode", "Admin Panel",  "Exit App"]
    # safe lookup: if session value not present, fall back to index 0
    try:
        default_index = menu_options.index(st.session_state.menu_selection)
    except ValueError:
        default_index = 0
        st.session_state.menu_selection = menu_options[0]

    mode = st.sidebar.radio("📋 Menu", menu_options, index=default_index)
    st.session_state.menu_selection = mode

    # Mode selection
    if mode == "Student Mode":
        run_student_mode()
    elif mode == "Admin Panel":
        run_admin_mode()


    elif mode == "Exit App":
        st.session_state.logged_in = False
        st.session_state.access_code = ""
        st.session_state.menu_selection = "Student Mode"
        st.success("👋 You have been logged out.")
        st.stop()

if __name__ == "__main__":
    main()
