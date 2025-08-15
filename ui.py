import streamlit as st
import os
import base64

def set_background(file_path):
    """
    Sets a Streamlit app background using a local image.
    Automatically encodes to base64 to avoid caching issues.
    """
    if not os.path.exists(file_path):
        st.error(f"Background file not found: {file_path}")
        return

    # Open and encode image as base64
    with open(file_path, "rb") as f:
        image_bytes = f.read()
    base64_image = base64.b64encode(image_bytes).decode()

    # Apply CSS to set as app background
    background_style = f"""
        <style>
            .stApp {{
                background-image: url("data:image/png;base64,{base64_image}");
                background-size: cover;
                background-repeat: no-repeat;
                background-attachment: fixed;
            }}
        </style>
    """
    st.markdown(background_style, unsafe_allow_html=True)
