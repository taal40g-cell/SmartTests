import os
import json
import psycopg2

# ===========================
# Database connection
# ===========================
conn = psycopg2.connect(
    dbname="smarttest",
    user="postgres",
    password="yourpassword",   # change this
    host="localhost",
    port="5432"
)
cur = conn.cursor()

# ===========================
# Config
# ===========================
QUESTIONS_DIR = "questions_json"

def extract_subject_from_filename(filename: str) -> str:
    """
    Extract subject name from filename like:
    questions_jhs1_science.json -> Science
    """
    parts = filename.replace(".json", "").split("_")
    if len(parts) >= 3:
        subject = parts[2]   # e.g., "science"
        return subject.capitalize()
    return "General"

def clean_options(options: list, answer: str) -> list:
    """
    Ensure options list has exactly 4 clean values.
    - Removes placeholders like 'Option A', 'Option B', etc.
    - Ensures the correct answer is always included.
    - Pads with dummy choices if fewer than 4 remain.
    """
    bad_opts = {"option a", "option b", "option c", "option d"}
    clean = [opt.strip() for opt in options if opt and opt.strip().lower() not in bad_opts]

    if answer.strip() not in clean:
        clean.append(answer.strip())

    while len(clean) < 4:
        clean.append(f"Choice {len(clean)+1}")

    return clean[:4]

# ===========================
# Migration
# ===========================
for file in os.listdir(QUESTIONS_DIR):
    if file.endswith(".json"):
        filepath = os.path.join(QUESTIONS_DIR, file)
        subject = extract_subject_from_filename(file)

        print(f"📂 Processing {file} → Subject: {subject}")

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                questions = json.load(f)
        except Exception as e:
            print(f"❌ Failed to load {file}: {e}")
            continue

        for q in questions:
            try:
                class_name = q.get("class_name", "").strip()
                question_text = q.get("question", "").strip()
                options = q.get("options", [])
                answer = q.get("answer", "").strip()

                if not class_name or not question_text or not options or not answer:
                    print(f"⚠️ Skipping incomplete question in {file}: {q}")
                    continue

                # Clean & normalize options
                options = clean_options(options, answer)

                # Insert into DB
                cur.execute("""
                    INSERT INTO questions (class_name, subject, question_text, answer,
                                           option1, option2, option3, option4, options)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    class_name, subject, question_text, answer,
                    options[0], options[1], options[2], options[3],
                    json.dumps(options)
                ))

            except Exception as e:
                print(f"⚠️ Skipping question in {file}: {e}")
                conn.rollback()
                continue

        conn.commit()
        print(f"✅ Finished {file}")

cur.close()
conn.close()
print("🎉 Migration complete.")
