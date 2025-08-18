from helpers import generate_access_slips

# Sample users
test_users = [
    {"access_code": "abcd1234", "name": "John Doe", "class": "JHS1", "can_retake": True},
    {"access_code": "efgh5678", "name": "Jane Smith", "class": "JHS2", "can_retake": False},
]

# Generate access slips with QR codes
zip_buffer = generate_access_slips(test_users)

# Save ZIP to file so you can open it
with open("TestAccessSlips.zip", "wb") as f:
    f.write(zip_buffer.getbuffer())

print("[OK] Test access slips generated in TestAccessSlips.zip")

