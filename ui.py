import qrcode

# Example list of student access codes
access_codes = ["zaki2446", "john123", "mary789"]

for code in access_codes:
    # URL points to your Streamlit app with access_code param
    url = f"http://localhost:8501/?access_code={code}"  # replace localhost with deployed URL
    img = qrcode.make(url)
    img.save(f"qr_{code}.png")
    print(f"QR code saved: qr_{code}.png -> {url}")

import streamlit as st
import plotly.express as px
import pandas as pd

def show_question_status_chart(questions, answers, marked_review, class_name, subject_name):
    data = []
    for i, q in enumerate(questions):
        if i in marked_review:
            status = "Marked for Review"
        elif answers[i] is None:
            status = "Unanswered"
        else:
            status = "Answered"
        data.append({"Question": f"Q{i+1}", "Status": status})

    df = pd.DataFrame(data)
    color_map = {
        "Answered": "green",
        "Unanswered": "red",
        "Marked for Review": "orange"
    }

    fig = px.bar(
        df, x="Question", y=["Status"], color="Status",
        color_discrete_map=color_map,
        title=f" Question Status - {class_name} {subject_name}"
    )
    st.plotly_chart(fig, use_container_width=True)
import streamlit as st

def show_header():
    st.markdown("<h2 style='text-align: center;'>?? SmartTest Student Portal</h2>", unsafe_allow_html=True)
    st.write("Welcome to your personalized test center.")

def layout_top_controls(class_name, subject_name, duration):
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"?? Class: **{class_name}**")
        st.info(f"?? Subject: **{subject_name}**")
    with col2:
        from datetime import datetime

        if "test_start_time" in st.session_state and "test_end_time" in st.session_state:
            now = datetime.now()
            remaining = st.session_state.test_end_time - now
            if remaining.total_seconds() > 0:
                minutes, seconds = divmod(int(remaining.total_seconds()), 60)
                st.success(f"Time Remaining: {minutes:02}:{seconds:02}")
            else:
                st.error("? Time's up!")


import streamlit as st
import base64

def set_background(image_file="assets/fl.png"):
    with open(image_file, "rb") as f:
        base64_image = base64.b64encode(f.read()).decode()

    background_style = f"""
        <style>
            .stApp {{
                background-image: url("data:image/png;base64,{base64_image}");
                background-size: cover;
            }}
        </style>
    """
    st.markdown(background_style, unsafe_allow_html=True)
