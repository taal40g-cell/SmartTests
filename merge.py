import os
import json

# ------------------------------
# CONFIG
# ------------------------------
QUESTIONS_DIR = "questions"        # folder where individual question files are stored
OUTPUT_FILE = "unified_data.json"  # final merged file

# ------------------------------
# MAIN MERGE FUNCTION
# ------------------------------
def merge_questions():
    unified_data = {}

    # Scan all JSON files in the questions directory
    for filename in os.listdir(QUESTIONS_DIR):
        if filename.endswith(".json"):
            filepath = os.path.join(QUESTIONS_DIR, filename)
            class_subject_key = filename.replace(".json", "").lower()  # e.g., jhs1_english

            with open(filepath, "r", encoding="utf-8") as f:
                try:
                    questions_list = json.load(f)
                    if isinstance(questions_list, list):
                        unified_data[class_subject_key] = questions_list
                    else:
                        print(f"⚠️ Skipping {filename}: not a list of questions")
                except json.JSONDecodeError:
                    print(f"⚠️ Invalid JSON: {filename}")

    # Save merged questions
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(unified_data, f, indent=4, ensure_ascii=False)

    print(f"🎯 All questions merged into {OUTPUT_FILE} (list format)")

# ------------------------------
# RUN SCRIPT
# ------------------------------
if __name__ == "__main__":
    merge_questions()
