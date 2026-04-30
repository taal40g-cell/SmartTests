import streamlit as st
# ✅ DB bootstrap (NO circular imports)
from backend.database import engine, init_db, ensure_default_sqlite_data,seed_default_classes
from sqlalchemy import text
from backend.ui import set_background
from selections.student import run_student_mode
from selections.admin import run_admin_mode
from backend import database
print("🔥 ACTIVE DB:", database.engine.url)
from backend.db_helpers import ensure_super_admin_exists
ensure_super_admin_exists()
# ==============================
# App startup (RUN ONCE per session)
# ==============================
if "db_initialized" not in st.session_state:
    database.init_db()
    database.ensure_default_sqlite_data()
    database.seed_default_classes()
    st.session_state.db_initialized = True


# ==============================
# Session state defaults
# ==============================
st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("access_code", "")
st.session_state.setdefault("menu_selection", "Student Mode")
st.session_state.setdefault("trigger_refresh", False)
st.session_state.setdefault("admin_username", "")
st.session_state.setdefault("admin_logged_in", False)
if "schools" not in st.session_state:
    st.session_state.schools = []
# ... rest of your app.py

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

    st.markdown("""
    <style>

    /* 1️⃣ Base Font System */
    html {
        font-size: 16px;  /* Baseline */
    }

    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    /* 2️⃣ Headings */
    h1 { font-size: 2rem; font-weight: 700; }
    h2 { font-size: 1.6rem; font-weight: 600; }
    h3 { font-size: 1.3rem; font-weight: 600; }

    /* 3️⃣ Question Text */
    .question-text {
        font-size: 1.2rem;
        line-height: 1.6;
        font-weight: 500;
    }

    div[role="radiogroup"] label {
    font-size: 1.05rem !important;
    }

    /* 4️⃣ Options */
    .option-text {
        font-size: 1.05rem;
        line-height: 1.5;
    }

    /* 5️⃣ Small Labels (timer, meta info) */
    .meta-text {
        font-size: 0.9rem;
        opacity: 0.8;
    }
    
    
    textarea {
    font-size: 1.05rem !important;
   }

    </style>
    """, unsafe_allow_html=True)


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
        try:
            # ✅ Use engine.connect(), not engine()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))  # simple test query
            st.sidebar.success("✅ Database connected successfully!")

        except Exception as e:
            st.sidebar.error(f"❌ Failed to connect to database:\n{e}")
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
