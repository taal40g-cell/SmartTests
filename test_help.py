from helpers import load_data, save_data, record_submission, can_retake

# Load current data
data = load_data()
print("Initial data:", data)

# Simulate a student submission
student_name = "John Doe"
student_class = "JHS1"
score = 85

record_submission(student_name, student_class, score)

# Reload to confirm submission was saved
data = load_data()
print("After submission:", data)

# Check if student can retake
allowed, msg = can_retake(student_name, student_class, limit=2)
print(f"Can retake? {allowed}, Message: {msg}")


def can_retake(data, student_name, class_name, limit=3):
    """
    Check if a student can retake the test.
    - data: full leaderboard data
    - student_name: the student's name
    - class_name: class the student belongs to
    - limit: how many times a student is allowed to retake
    """
    if class_name not in data:
        return True  # No class yet, so they can take it

    submissions = [s for s in data[class_name] if s["name"] == student_name]
    return len(submissions) < limit

def can_retake(student_name, class_name, data, max_retake=3):
    """
    Check if a student can retake a test.
    - student_name: the student's name
    - class_name: which class they belong to
    - data: dictionary returned from load_data()
    - max_retake: how many times a student is allowed to retake
    """
    submissions = data.get("submissions", {}).get(class_name, {}).get(student_name, [])
    return len(submissions) < max_retake


# test_help.py
from helpers import load_data, save_data, record_submission, can_retake

print("Testing helpers...")

# Example usage
record_submission("Taal", "JHS1", 8, 10)
print("Can Taal retake?", can_retake("Taal", retake_limit=3))
print(load_data())
