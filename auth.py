import pandas as pd
import hashlib
import os
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
        student_row = df[df["access_code"] == code]
        if not student_row.empty:
            return student_row.iloc[0].to_dict()
    return None
