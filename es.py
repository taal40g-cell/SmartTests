# ======================================================
# SmartTests Streamlit App with Dual DB (PostgreSQL + SQLite)
# ======================================================
import streamlit as st
from datetime import datetime
import json
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from models import Base, Student, StudentProgress, Submission, TestResult, Leaderboard, SubjectiveSubmission

# ======================================================
# 1️⃣ DB CONNECTIONS
# ======================================================
# PostgreSQL
PG_USER = os.getenv("PG_USER", "smarttestdb_2_user")
PG_PASSWORD = os.getenv("PG_PASSWORD", "QZOkC4mtDk70RsMM2VgyooOU1gOmPbwh")
PG_HOST = os.getenv("PG_HOST", "dpg-d4gm1kili9vc73dn0d3g-a.oregon-postgres.render.com")
PG_PORT = os.getenv("PG_PORT", 5432)
PG_DB = os.getenv("PG_DB", "smarttestdb_2")

PG_URL = f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}?sslmode=require"

# SQLite fallback
SQLITE_URL = "sqlite:///smarttest_db.sqlite"

# Engines and sessions
engine_pg = create_engine(PG_URL, connect_args={"connect_timeout": 5}, echo=False)
engine_sqlite = create_engine(SQLITE_URL, echo=False)
SessionPG = sessionmaker(bind=engine_pg)
SessionSQLite = sessionmaker(bind=engine_sqlite)

# Get active DB session
def get_db_session():
    try:
        session = SessionPG()
        session.execute("SELECT 1")
        return session, "pg"
    except OperationalError:
        session = SessionSQLite()
        return session, "sqlite"

# ======================================================
# 2️⃣ SYNC LOCAL (SQLite) → POSTGRESQL
# ======================================================
def sync_local_to_pg():
    sqlite_session = SessionSQLite()
    pg_session = SessionPG()
    try:
        unsynced = sqlite_session.query(StudentProgress).filter_by(submitted=False).all()
        for p in unsynced:
            exists = pg_session.query(StudentProgress).filter_by(
                student_id=p.student_id, subject=p.subject
            ).first()
            if not exists:
                pg_session.add(p)
        pg_session.commit()
        if unsynced:
            print(f"✅ Synced {len(unsynced)} progress records SQLite → PostgreSQL")
    except Exception as e:
        pg_session.rollback()
        print("❌ Sync failed:", e)
    finally:
        sqlite_session.close()
        pg_session.close()

# ======================================================
# 3️⃣ SAVE HELPERS
# ======================================================
def save_obj(obj):
    session, db_type = get_db_session()
    try:
        session.add(obj)
        session.commit()
        print(f"✅ Saved to {db_type.upper()}")
    except Exception as e:
        session.rollback()
        print(f"❌ Failed to save to {db_type.upper()}: {e}")
    finally:
        session.close()

# ======================================================
# 4️⃣ AUTO-SYNC ON APP START
# ======================================================
sync_local_to_pg()

# ======================================================
# 5️⃣ STREAMLIT APP
# ======================================================
st.set_page_config(page_title="SmartTests", layout="wide")

st.title("🧠 SmartTests")

# ---------------------
# Student Login
# ---------------------
access_code = st.text_input("Enter your access code:")
student_obj = None
if access_code:
    session, db_type = get_db_session()
    student_obj = session.query(Student).filter_by(access_code=access_code).first()
    session.close()
    if student_obj:
        st.success(f"Welcome {student_obj.name} ({student_obj.class_name})")
    else:
        st.error("❌ Invalid access code")

# ---------------------
# Start Test / Load Progress
# ---------------------
if student_obj:
    session, db_type = get_db_session()
    progress = session.query(StudentProgress).filter_by(
        student_id=student_obj.id, submitted=False
    ).first()
    session.close()

    if not progress:
        if st.button("🚀 Start Test"):
            progress = StudentProgress(
                student_id=student_obj.id,
                access_code=access_code,
                subject="jhs_1_eng",
                answers=[],
                current_q=0,
                start_time=datetime.now().timestamp(),
                duration=3600,
                questions=["Q1","Q2","Q3"],  # replace with actual questions
                school_id=student_obj.school_id,
                test_type="objective",
            )
            save_obj(progress)
    else:
        st.info(f"📌 Resuming test. Question {progress.current_q + 1}/{len(progress.questions)}")

# ---------------------
# Submit / Save Progress
# ---------------------
if progress:
    # simulate answering
    if st.button("✅ Submit Answer / Save Progress"):
        progress.answers.append("A")  # example answer
        progress.current_q += 1
        save_obj(progress)
        st.success(f"Progress saved. Current question: {progress.current_q}")

    # Final submission
    if st.button("🏁 Submit Test"):
        progress.submitted = True
        save_obj(progress)
        st.balloons()
        st.success("🎉 Test submitted!")

# ---------------------
# View Performance
# ---------------------
if student_obj:
    session, db_type = get_db_session()
    results = session.query(TestResult).filter_by(student_id=student_obj.id).all()
    session.close()
    if results:
        st.subheader("📊 Your Results")
        for r in results:
            st.write(f"{r.subject}: {r.score}/{r.total} ({r.percentage}%)")
