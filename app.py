import streamlit as st
from ui import set_background
from selections.student import run_student_mode
from selections.admin import run_admin_mode

def results_page():
    query_params = st.query_params
    access_code = query_params.get("access_code", [None])[0]

    if access_code:
        st.title("Results Page")
        st.success(f"Showing results for access code: {access_code}")
    else:
        st.title("SmarTest App")
        st.write("No access code provided. Use Student/Admin menu below.")


# Make sure these are set before you use them
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "access_code" not in st.session_state:
    st.session_state.access_code = ""

def main():
    set_background("assets/fl.png")
    page = st.query_params.get("page", [None])[0]

    if page == "results":
        results_page()
        return
    st.markdown(
        "<h1 style='text-align: center; text-decoration: underline; font-weight: bold; color: white; background-color: #ff69b4'>🎓 SmarTest</h1>",
        unsafe_allow_html=True,
    )
    # One-time rerun logic
    if st.session_state.get("trigger_refresh", False):
        st.session_state.trigger_refresh = False  # reset flag
        st.session_state.menu_selection = "Student Mode"  # or your preferred default
        st.rerun()

    # Default menu selection
    menu_options = ["Student Mode", "Admin Panel", "Refresh App", "Exit App"]
    default_index = menu_options.index(st.session_state.get("menu_selection", "Student Mode"))

    mode = st.sidebar.radio("📋 Menu", menu_options, index=default_index)
    st.session_state.menu_selection = mode

    if mode == "Student Mode":
        run_student_mode()

    elif mode == "Admin Panel":
        run_admin_mode()

    elif mode == "Refresh App":
        st.session_state.trigger_refresh = True  # set flag
        st.rerun()  # rerun with the flag set

    elif mode == "Exit App":
        st.session_state.logged_in = False
        st.session_state.access_code = ""
        st.session_state.menu_selection = "Student Mode"
        st.success("👋 You have been logged out.")
        st.stop()

if __name__ == "__main__":
    main()
