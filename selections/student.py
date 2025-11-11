import uuid
import time
import json
import random
from datetime import datetime, timedelta
import streamlit as st
import qrcode, io
import pandas as pd
from ui import render_test, generate_pdf,get_test_type
from helpers import get_subjective_questions,get_objective_questions,render_subjective_test,save_student_answers,get_subjective_questions
from db_helpers import (
    load_questions_db,
    show_question_tracker,
    can_take_test,
    get_users,load_subjects,
    get_test_duration,load_student_results,
    get_student_by_access_code_db,
    decrement_retake,load_progress, save_progress, clear_progress
)
def get_student_display(student) -> str:
    """Return a formatted display string for both dict and ORM student."""
    if hasattr(student, "__dict__"):  # ORM object
        name = getattr(student, "name", "Student")
        class_name = getattr(student, "class_name", "Unknown")
    else:  # dictionary
        name = student.get("name", "Student")
        class_name = student.get("class_name", "Unknown")
    return f"Welcome {name} | Class: {class_name.upper()}"

from streamlit_autorefresh import st_autorefresh
# ==============================
# Main Student Mode
# ==============================
def run_student_mode():
    users_dict = get_users()

    # -----------------------------
    # Initialize session defaults
    # -----------------------------
    defaults = {
        "test_started": False,
        "submitted": False,
        "logged_in": False,
        "student": {},
        "answers": [],
        "current_q": 0,
        "current_page": 0,
        "questions": [],
        "subject": None,
        "marked_for_review": set(),
        "duration": None,
        "start_time": None,
        "test_end_time": None,  # ✅ Add this line
        "five_min_warned": False,
        "saved_to_db": False,
        "last_auto_save": 0
    }

    for key, val in defaults.items():
        st.session_state.setdefault(key, val)

    def _normalize_answers(answers, questions):
        """
        Normalize student's answers to match the number and type of questions.
        Handles both objective (indexed) and subjective (text) answers safely.
        """

        n = len(questions)

        # Handle dictionary-style answers (e.g., from saved progress)
        if isinstance(answers, dict):
            normalized = []
            for i in range(n):
                v = answers.get(str(i), answers.get(i, ""))
                if isinstance(v, (int, float)):
                    normalized.append(str(int(v)))
                elif isinstance(v, str):
                    normalized.append(v.strip())
                else:
                    normalized.append("")
            return normalized

        # Handle list-style answers
        if not isinstance(answers, list):
            return [""] * n

        # Pad or trim list to match question length
        if len(answers) < n:
            answers += [""] * (n - len(answers))
        elif len(answers) > n:
            answers = answers[:n]

        # Normalize all elements
        normalized = []
        for ans in answers:
            if isinstance(ans, (int, float)):
                normalized.append(str(int(ans)))  # store as text safely
            elif isinstance(ans, str):
                normalized.append(ans.strip())
            else:
                normalized.append("")

        return normalized

    # -----------------------------
    # Header & Banner
    # -----------------------------
    st.markdown("### SmartTest Student Portal")
    st.markdown("Welcome to your personalized test center.")
    st.markdown(
        """
        <marquee behavior="scroll" direction="left" scrollamount="5"
            style="color: #F54927; padding: 10px; border-radius: 15px; font-weight: bold;">
           Retakes are controlled by Admins! Submit your test before time runs out 
        </marquee>
        """,
        unsafe_allow_html=True
    )

    # -----------------------------
    # CSS Styling
    # -----------------------------
    st.markdown("""
        <style>
        .small-input input, .small-input select { width: 150px !important; padding: 6px; font-size: 14px; }
        div[data-baseweb="input"], div[data-baseweb="select"] { width: 220px !important; margin-left: 0 !important; }
        .card { padding: 1rem; margin-top: 0.8rem; border-radius: 10px; border: 1px solid #ddd; background-color: #fafafa; box-shadow: 1px 1px 4px rgba(0,0,0,0.08); }
        </style>
    """, unsafe_allow_html=True)

    # -------------------------
    # LOGIN (Access Code)
    # -------------------------
    if not st.session_state.get("logged_in", False):
        st.markdown("<div style='font-size:16px; font-weight:600;'>Enter Access Code:</div>", unsafe_allow_html=True)
        access_code_input = st.text_input("Access Code", placeholder="Code issued by Admin", key="access_code_input",
                                          label_visibility="collapsed")

        if access_code_input:
            access_code = access_code_input.strip().upper()
            student_obj = get_student_by_access_code_db(access_code)
            if not student_obj:
                st.error("Invalid login code ❌")
                st.stop()

            # Convert ORM -> dict
            student = {
                "id": student_obj.id,
                "name": student_obj.name,
                "class_name": getattr(student_obj, "class_name", "") or "",
                "access_code": access_code,
                "can_retake": bool(getattr(student_obj, "can_retake", True)),
                "school_id": getattr(student_obj, "school_id", None)
            }

            # Persist in session
            st.session_state.update({
                "logged_in": True,
                "student": student,
                "class_name": student["class_name"],
            })

            # Reset stale session vars
            for k in ["test_started", "submitted", "questions", "answers", "current_q",
                      "marked_for_review", "start_time", "duration", "saved_to_db",
                      "test_phase", "test_type"]:
                st.session_state.pop(k, None)

            st.success(f"Welcome, {student['name']} — Class: {student['class_name']}")
            st.rerun()

        st.stop()

    # -------------------------
    # Sidebar: Past Performance
    # -------------------------
    with st.sidebar:
        st.header("📊 Past Performance")
        perf_code = st.text_input("Enter Access Code", key="sidebar_access_code")

        def gen_qr(data):
            qr = qrcode.QRCode(version=1, box_size=6, border=2)
            qr.add_data(data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, "PNG")
            buf.seek(0)
            return buf

        APP_URL = "https://smarttests-1.onrender.com"

        if perf_code:
            perf_code = perf_code.strip().upper()
            stud = get_student_by_access_code_db(perf_code)
            if not stud:
                st.error("Invalid access code")
            else:
                st.success(f"{stud.name} — {stud.class_name}")
                st.image(gen_qr(f"{APP_URL}?access_code={perf_code}"))

                results = load_student_results(perf_code)
                if results:
                    df = pd.DataFrame([{
                        "Class": r.class_name,
                        "Subject": r.subject,
                        "Score": r.score,
                        "Percentage": f"{r.percentage:.2f}%",
                        "Date": r.taken_at.strftime("%Y-%m-%d %H:%M")
                    } for r in sorted(results, key=lambda x: x.taken_at, reverse=True)])

                    def color_pct(val):
                        try:
                            n = float(val.strip('%'))
                            if n >= 70: return 'background-color: #a6f1a6'
                            if n >= 50: return 'background-color: #fff6a6'
                            return 'background-color: #f7a6a6'
                        except Exception:
                            return ''

                    st.dataframe(df.style.applymap(color_pct, subset=['Percentage']), use_container_width=True)
                    st.download_button("⬇️ Download CSV", df.to_csv(index=False).encode(), "results.csv", "text/csv")
                else:
                    st.info("No results yet.")

                if st.button("🔄 Refresh Test (Clear Progress)"):
                    for k in ["test_started", "submitted", "questions", "answers", "current_q",
                              "marked_for_review", "start_time", "duration", "saved_to_db"]:
                        st.session_state.pop(k, None)
                    try:
                        clear_progress(perf_code, st.session_state.get("subject"))
                        st.success("Progress cleared from DB.")
                    except Exception as e:
                        st.warning(f"Could not clear DB progress: {e}")
                    st.success("Local session cleared. Start new test.")
                    st.rerun()

    # -------------------------
    # Main Student UI
    # -------------------------
    student = st.session_state.get("student", {})
    class_name = st.session_state.get("class_name") or student.get("class_name") or ""
    school_id = str(student.get("school_id", ""))  # Ensure string

    if not class_name:
        st.error("Class not set for student — contact admin.")
        st.stop()

    # Load subjects once and cache in session_state
    if "subjects" not in st.session_state:
        try:
            st.session_state.subjects = load_subjects(class_name, school_id)
        except Exception as e:
            st.error(f"Failed to load subjects: {e}")
            st.session_state.subjects = []

    subjects = st.session_state.subjects
    if not subjects:
        st.warning("No subjects available for your class. Contact admin.")
        st.stop()

    # -------------------------
    # Select Subject
    # -------------------------
    st.markdown("#### 📘 Select Subject")
    selected_subject = st.selectbox(
        "Subject",
        [s["name"] if isinstance(s, dict) else s for s in st.session_state.subjects],
        key="subject_select_box"
    )
    st.session_state.subject = selected_subject

    # -------------------------
    # Determine Subject ID (for DB use)
    # -------------------------
    selected_subject_id = None
    subjects = st.session_state.subjects
    if subjects and isinstance(subjects[0], dict):
        for s in subjects:
            if s.get("name") == selected_subject:
                selected_subject_id = s.get("id")
                break
    elif subjects and isinstance(subjects[0], str):
        selected_subject_id = selected_subject  # fallback
    if selected_subject_id is None:
        st.error(f"❌ Selected subject ID not found for '{selected_subject}'")
        st.stop()

    school_id = str(st.session_state.student.get("school_id", ""))

    # -------------------------
    # Load Questions (once per subject)
    # -------------------------
    key_obj = f"objective_{st.session_state.class_name}_{selected_subject}_{school_id}"
    key_subj = f"subjective_{st.session_state.class_name}_{selected_subject}_{school_id}"

    if key_obj not in st.session_state:
        st.session_state[key_obj] = get_objective_questions(
            st.session_state.class_name, selected_subject, school_id
        ) or []

    if key_subj not in st.session_state:
        st.session_state[key_subj] = get_subjective_questions(
            st.session_state.class_name, selected_subject, school_id
        ) or []

    objective_questions = st.session_state[key_obj]
    subjective_questions = st.session_state[key_subj]


    # -------------------------
    # Choose Test Type
    # -------------------------
    # Always show both options
    test_options = ["Objective", "Subjective"]

    # Mark options with no questions
    if not objective_questions:
        test_options[0] += " (No questions)"
    if not subjective_questions:
        test_options[1] += " (No questions)"

    st.markdown(
        """
        <div style="
            display: inline-block;
            font-size: 20px;
            font-weight: bold;
            color: #f3f6f6;
            border-bottom: 4px solid #4CAF50;
            border-radius: 2px;
            padding-bottom: 2px;
            margin-bottom: 10px;
        ">
            🧩 Choose Test Type
        </div>
        """,
        unsafe_allow_html=True
    )

    # ✅ Single radio with unique key
    test_choice = st.radio(
        "Choose type",
        test_options,
        index=0,
        horizontal=True,
        key=f"test_type_radio_{st.session_state.class_name}_{selected_subject}"
    )

    # Normalize value for internal use
    if "objective" in test_choice.lower():
        st.session_state.test_type = "objective"
    else:
        st.session_state.test_type = "subjective"

    st.session_state.test_phase = st.session_state.test_type

    # -------------------------
    # Start / Resume Buttons
    # -------------------------
    access_code = st.session_state.student.get("access_code", "").strip()
    saved_progress = load_progress(access_code, selected_subject) if access_code else None

    col1, col2 = st.columns([1, 3])
    start_clicked = col1.button("🚀 Start Test", key=f"start_btn_{selected_subject}", use_container_width=True)

    resume_clicked = False
    if saved_progress and not saved_progress.get("submitted", False):
        resume_clicked = col2.button("🔄 Resume Test", key=f"resume_btn_{selected_subject}", use_container_width=True)
    elif saved_progress and saved_progress.get("submitted", False):
        col2.info("✅ You already submitted this test.")

    # -------------------------
    # Resume Test Logic
    # -------------------------
    if resume_clicked and saved_progress:
        questions = saved_progress.get("questions", [])
        answers = _normalize_answers(saved_progress.get("answers", []), questions)

        # Preserve option order from saved progress
        for q in questions:
            q_type = q.get("type", "objective").lower()
            if q_type == "objective":
                opts = q.get("options", [])
                if isinstance(opts, str):
                    try:
                        opts = json.loads(opts)
                    except Exception:
                        opts = [x.strip() for x in opts.split(",") if x.strip()]
                q["options"] = opts
                q["correct_answer_text"] = str(q.get("correct_answer_text", "")).strip()
                q["answer_index"] = opts.index(q["correct_answer_text"]) if q["correct_answer_text"] in opts else -1
            else:
                q["options"] = []

        st.session_state.update({
            "test_started": True,
            "submitted": False,
            "questions": questions,
            "answers": answers,
            "current_q": saved_progress.get("current_q", 0),
            "duration": saved_progress.get("duration", 1800),
            "start_time": saved_progress.get("start_time", time.time()),
            "marked_for_review": set(saved_progress.get("marked_for_review", [])),
            "saved_to_db": False
        })

        st.session_state.test_end_time = datetime.fromtimestamp(
            st.session_state.start_time + st.session_state.duration
        )

        st.success("✅ Resumed saved progress.")
        st.rerun()

    # ==============================
    # Start New Test
    # ==============================
    if start_clicked:
        allowed, msg = can_take_test(access_code, selected_subject)
        if not allowed:
            st.error(msg)
            st.stop()

        try:
            decrement_retake(access_code, selected_subject)
        except Exception:
            pass

        test_type = st.session_state.test_type
        objective_qs = get_objective_questions(st.session_state.class_name, selected_subject, school_id) or []
        subjective_qs = get_subjective_questions(st.session_state.class_name, selected_subject, school_id) or []

        questions = []
        if test_type == "objective":
            for q in objective_qs:
                q["type"] = "objective"
                questions.append(q)
        elif test_type == "subjective":
            for q in subjective_qs:
                q["type"] = "subjective"
                q["options"] = []
                questions.append(q)
        else:  # fallback mixed
            for q in objective_qs:
                q["type"] = "objective"
                questions.append(q)
            for q in subjective_qs:
                q["type"] = "subjective"
                q["options"] = []
                questions.append(q)

        if not questions:
            st.warning(f"No {test_type} questions found for {st.session_state.class_name} / {selected_subject}.")
            st.stop()

        # Randomize once
        random.shuffle(questions)

        # Prepare options and correct answers
        for q in questions:
            if q["type"] == "objective":
                opts = q.get("options", [])
                if not isinstance(opts, list):
                    opts = [str(opts)]
                correct_text = str(q.get("answer", "")).strip()
                q["correct_answer_text"] = correct_text
                random.shuffle(opts)
                q["options"] = opts
                q["answer_index"] = opts.index(correct_text) if correct_text in opts else -1
                q.pop("answer", None)
            else:
                q["options"] = []

        duration_secs = get_test_duration(st.session_state.class_name, selected_subject, school_id) or 1800

        st.session_state.update({
            "test_id": str(uuid.uuid4()),
            "test_started": True,
            "submitted": False,
            "questions": questions,
            "answers": [""] * len(questions),
            "current_q": 0,
            "marked_for_review": set(),
            "duration": duration_secs,
            "start_time": time.time(),
            "five_min_warned": False,
            "saved_to_db": False
        })

        st.session_state.test_end_time = datetime.now() + timedelta(seconds=duration_secs)
        st.success(f"✅ {test_type.capitalize()} test started — {int(duration_secs // 60)} minutes")
        st.rerun()

    # -------------------------
    # Test In Progress
    # -------------------------
    if st.session_state.get("test_started") and not st.session_state.get("submitted"):
        remaining = int(st.session_state.test_end_time.timestamp() - datetime.now().timestamp())
        if remaining <= 0:
            st.warning("⏰ Time is up! Submitting automatically...")
            st.session_state.submitted = True
            save_progress(access_code, selected_subject, st.session_state.answers, st.session_state.current_q,
                          st.session_state.start_time, st.session_state.duration, st.session_state.questions)
            st.rerun()

        mins, secs = divmod(remaining, 60)
        st.markdown(
            f"<div style='text-align:right; font-size:20px; color:#f44336;'>⏱️ Time Left: {mins:02d}:{secs:02d}</div>",
            unsafe_allow_html=True
        )

        show_question_tracker(st.session_state.questions, st.session_state.current_q, st.session_state.answers)

        questions = st.session_state.questions
        q_index = st.session_state.current_q
        q = questions[q_index]
        q_type = q.get("type", "objective").lower()

        st.markdown('<div class="card">', unsafe_allow_html=True)
        question_text = q.get("question_text") or q.get("question") or "No question text"
        st.markdown(f"### Q{q_index + 1}. {question_text}")

        if q_type == "objective":
            options = q.get("options", [])
            placeholder = "Choose one:"
            if placeholder not in options:
                options = [placeholder] + options
            selected = st.session_state.answers[q_index]
            if selected not in options:
                selected = placeholder
            choice = st.radio("Choose one:", options, index=options.index(selected), key=f"q_{q_index}")
            st.session_state.answers[q_index] = "" if choice == placeholder else choice
        else:
            text_ans = st.text_area("Your answer:", value=st.session_state.answers[q_index], key=f"q_{q_index}")
            st.session_state.answers[q_index] = text_ans.strip()

        mark_toggle = st.checkbox("🔖 Mark this question for review",
                                  value=q_index in st.session_state.marked_for_review, key=f"mark_review_{q_index}")
        if mark_toggle:
            st.session_state.marked_for_review.add(q_index)
        else:
            st.session_state.marked_for_review.discard(q_index)

        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("⬅️ Previous", use_container_width=True, disabled=q_index == 0):
                st.session_state.current_q = max(0, q_index - 1)
        with col2:
            if st.button("➡️ Next", use_container_width=True, disabled=q_index == len(questions) - 1):
                st.session_state.current_q = min(len(questions) - 1, q_index + 1)
        with col3:
            if st.button("✅ Submit Test", use_container_width=True):
                st.session_state.submitted = True
                save_progress(access_code, selected_subject, st.session_state.answers, st.session_state.current_q,
                              st.session_state.start_time, st.session_state.duration, st.session_state.questions)
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # ==============================
    # After Submission: Score Calculation + Feedback
    # ==============================
    if st.session_state.get("submitted", False):
        questions = st.session_state.get("questions", [])
        answers = st.session_state.get("answers", [])

        if not questions:
            st.warning("⚠️ No questions loaded. Please contact admin.")
            st.stop()

        details = []
        correct = 0
        import re

        def normalize_answer(ans: str) -> str:
            ans = str(ans).lower().strip()
            ans = ans.replace("×", "x").replace("÷", "/").replace("^2", "²")
            ans = ans.replace(" per ", "/")
            ans = re.sub(r"\s+", " ", ans)
            ans = re.sub(r"[^\w\s/.\-+]", "", ans)
            return ans

        for i, q in enumerate(questions):
            selected = answers[i] if i < len(answers) else ""

            # If answer is invalid or default
            if not selected or selected == "Choose one:" or selected not in q.get("options", []):
                student_answer = "No Answer"
            else:
                student_answer = selected

            correct_answer = q.get("correct_answer_text", "N/A")

            sa = normalize_answer(student_answer)
            ca = normalize_answer(correct_answer)
            is_correct = sa == ca
            if is_correct:
                correct += 1
            details.append({
                "question": q.get("question", ""),
                "your_answer": student_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct
            })

        total_questions = len(questions)
        percent = (correct / total_questions * 100) if total_questions else 0

        # 🎉 Motivational Message
        if percent >= 80:
            st.success(f"🏆 Excellent work! You scored {percent:.1f}% — Outstanding performance!")
        elif percent >= 50:
            st.info(f"👍 Good job! You scored {percent:.1f}% — Keep practicing to improve.")
        else:
            st.warning(f"💪 Don’t give up! You scored {percent:.1f}% — Review and try again.")

        # Show summary
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.success(f"Score: {correct}/{total_questions} ({percent:.2f}%)")
        col1, col2 = st.columns(2)
        col1.success(f"✅ Correct: {correct}")
        col2.error(f"❌ Wrong: {total_questions - correct}")

        with st.expander("📋 View Answer Breakdown"):
            for i, d in enumerate(details, 1):
                color = "green" if d["is_correct"] else "red"
                st.markdown(
                    f"<p style='color:{color};'><b>Q{i}:</b> {d['question']}<br>"
                    f"Your Answer: <b>{d['your_answer']}</b><br>"
                    f"Correct: <b>{d['correct_answer']}</b></p>",
                    unsafe_allow_html=True
                )

        # Save results to DB (best-effort)
        if not st.session_state.get("saved_to_db", False):
            try:
                save_student_answers(
                    access_code=st.session_state.student["access_code"],
                    subject=st.session_state.subject,
                    questions=questions,
                    answers=answers
                )
                st.session_state.saved_to_db = True
            except Exception:
                pass

        # ✅ Generate PDF result with school info and logo
        school_name = st.session_state.get('school_name', 'Smart Test School')
        school_id = st.session_state.get('school_id', '—')

        pdf_bytes = generate_pdf(
            name=st.session_state.student['name'],
            class_name=st.session_state.student.get('class_name', ''),
            subject=st.session_state.subject,
            correct=correct,
            total=total_questions,
            percent=percent,
            details=details,
            school_name=school_name,
            school_id=school_id,
            logo_path="logo.png"
        )

        # 📥 Download button
        st.download_button(
            "📄 Download Result as PDF",
            data=pdf_bytes,
            file_name=f"result_{st.session_state.student['name']}_{st.session_state.subject}.pdf",
            mime="application/pdf",
            key="download_result_pdf"
        )

        # ✅ Return to Subject Selection
        if st.button("🔙 Return to Subject Selection"):
            # Keep login info but clear test session
            for key in [
                "submitted", "questions", "answers", "test_started", "saved_to_db",
                "subject", "current_q", "start_time", "duration", "five_min_warned"
            ]:
                st.session_state.pop(key, None)

            st.success("✅ Test completed — ready to choose another subject.")
            st.rerun()
