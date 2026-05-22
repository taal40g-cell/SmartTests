import streamlit as st
import sqlite3

# --- Connect to DB ---
conn = sqlite3.connect(r"C:\Users\User\Desktop\SmartTests\smarttest.db")
cursor = conn.cursor()

# --- Admin Info (Example) ---
admin_id = 1  # Replace with session-based admin ID if available

# --- School Selector ---
cursor.execute("SELECT DISTINCT school_id FROM subjective_questions")
schools = [row[0] for row in cursor.fetchall()]
school_id = st.selectbox("Select School", schools)

st.header("📋 Subjective Grading Dashboard")

# --- Fetch Students for the School ---
cursor.execute("""
    SELECT DISTINCT sp.student_id
    FROM student_progress sp
    JOIN student_answers sa ON sa.progress_id = sp.id
    JOIN subjective_questions sq ON sa.question_id = sq.id
    WHERE sq.school_id=?
    ORDER BY sp.student_id
""", (school_id,))
students = [row[0] for row in cursor.fetchall()]

if not students:
    st.info("No students found for this school.")
else:
    for student_id in students:
        with st.expander(f"Student ID: {student_id}", expanded=False):
            # Fetch answers with question text and max marks
            cursor.execute("""
                SELECT sa.id, sa.question_id, sq.question_text, sa.answer, sq.marks
                FROM student_answers sa
                JOIN subjective_questions sq ON sa.question_id = sq.id
                JOIN student_progress sp ON sa.progress_id = sp.id
                WHERE sp.student_id=? AND sq.school_id=?
            """, (student_id, school_id))
            answers = cursor.fetchall()

            if not answers:
                st.info("No answers found for this student.")
                continue

            scores_dict = {}
            for answer_id, question_id, question_text, answer_text, max_marks in answers:
                # Check if already graded
                cursor.execute("""
                    SELECT score FROM subjective_grades
                    WHERE student_id=? AND question_id=?
                """, (student_id, question_id))
                row = cursor.fetchone()
                initial_score = row[0] if row else 0

                col1, col2, col3 = st.columns([1, 3, 1])
                with col1:
                    st.markdown(f"**QID:** {question_id}")
                with col2:
                    st.markdown(f"**Question:** {question_text}")
                    st.markdown(f"**Answer:** {answer_text}")
                    if initial_score:
                        st.markdown(f"✅ Already graded: {initial_score}")
                    else:
                        st.markdown("⚠️ Not graded yet")
                with col3:
                    score = st.number_input(
                        "Score",
                        min_value=0,
                        max_value=max_marks,
                        value=initial_score,
                        key=f"score_{answer_id}"
                    )
                    scores_dict[answer_id] = (student_id, question_id, score)

                st.markdown("---")

            # Submit Grades Button
            if st.button(f"Submit Grades for Student {student_id}", key=f"submit_{student_id}"):
                for answer_id, (stu_id, q_id, score) in scores_dict.items():
                    cursor.execute("""
                        INSERT OR REPLACE INTO subjective_grades
                        (student_id, question_id, score, graded_by, timestamp)
                        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (stu_id, q_id, score, admin_id))
                conn.commit()
                st.success(f"✅ Grades submitted for Student {student_id}!")

# --- Close DB ---
conn.close()