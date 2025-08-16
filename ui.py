import streamlit as st
import os
import base64

def set_background(file_path, force_reload=True):
    """
    Sets a Streamlit app background using a local image.
    Automatically encodes to base64 to avoid caching issues.
    If force_reload=True, clears Streamlit cache to show the latest image.
    """
    if not os.path.exists(file_path):
        st.error(f"Background file not found: {file_path}")
        return

    # Force clear caches if requested
    if force_reload:
        try:
            st.cache_data.clear()
            st.cache_resource.clear()
        except AttributeError:
            # Older Streamlit versions may not have clear() methods
            pass

    with open(file_path, "rb") as f:
        image_bytes = f.read()
    base64_image = base64.b64encode(image_bytes).decode()

    st.markdown(
        f"""
        <style>
            .stApp {{
                background-image: url("data:image/png;base64,{base64_image}");
                background-size: cover;
                background-repeat: no-repeat;
                background-attachment: fixed;
            }}
        </style>
        """,
        unsafe_allow_html=True
    )
