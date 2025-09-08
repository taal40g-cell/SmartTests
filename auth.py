import pandas as pd
import hashlib
import os
import streamlit as st
def authenticate_student(access_code, users_file='users.csv'):
    try:
        df = pd.read_csv(users_file)
        user_row = df[df['access_code'] == access_code]
        if not user_row.empty:
            user_data = user_row.iloc[0].to_dict()
            return user_data
    except Exception as e:
        print(f"Authentication failed: {e}")
    return None



def get_student_by_code(code):
    if os.path.exists("users.csv"):
        df = pd.read_csv("users.csv")

        # Normalize column names
        df.columns = df.columns.str.strip().str.lower()

        if "access_code" not in df.columns:
            st.error("❌ 'users.csv' is missing an 'access_code' column")
            return None

        student_row = df[df["access_code"] == code]
        if not student_row.empty:
            student_dict = student_row.iloc[0].to_dict()

            # Make sure the access_code is always present
            student_dict["access_code"] = code
            return student_dict
    return None
