# migrate_json_to_db_full.py
import json
import os
from database import engine, SessionLocal
from models import Base, User, Admin, Question, Submission, Retake, Leaderboard, Config

UNIFIED_FILE = "unified_data.json"

def migrate():
    if not os.path.exists(UNIFIED_FILE):
        print("⚠️ No unified_data.json found. Nothing to migrate.")
        return

    # Create all tables
    Base.metadata.create_all(bind=engine)

    with open(UNIFIED_FILE, "r") as f:
        data = json.load(f)

    db = SessionLocal()

    users_count = admins_count = questions_count = submissions_count = retakes_count = leaderboard_count = config_count = 0

    try:
        # --- Migrate Users ---
        users = data.get("users", {})
        for code, u in users.items():
            if not db.query(User).filter_by(access_code=code).first():
                db.add(User(
                    name=u.get("name", ""),
                    student_class=u.get("class", ""),
                    access_code=u.get("access_code", code),
                    can_retake=u.get("can_retake", True),
                    submitted=u.get("submitted", False)
                ))
                users_count += 1

        # --- Migrate Admins ---
        admins = data.get("admins", {})
        for username, a in admins.items():
            if not db.query(Admin).filter_by(username=username).first():
                db.add(Admin(
                    username=username,
                    password=a.get("password"),
                    role=a.get("role", "admin")
                ))
                admins_count += 1

        # --- Migrate Questions ---
        questions = data.get("questions", {})
        for key, qlist in questions.items():
            if "_" in key:
                class_name, subject = key.split("_", 1)
            else:
                class_name, subject = key, ""
            if not db.query(Question).filter_by(class_name=class_name, subject_name=subject).first():
                db.add(Question(
                    class_name=class_name,
                    subject_name=subject,
                    data=qlist
                ))
                questions_count += 1

        # --- Migrate Submissions ---
        submissions = data.get("submissions", [])
        for s in submissions:
            if not db.query(Submission).filter_by(
                access_code=s.get("access_code"),
                subject=s.get("subject")
            ).first():
                db.add(Submission(
                    access_code=s.get("access_code"),
                    subject=s.get("subject"),
                    score=s.get("score", 0),
                    answers=s.get("answers", {})
                ))
                submissions_count += 1

        # --- Migrate Retakes ---
        retakes = data.get("retakes", {})
        for code, subjects in retakes.items():
            for subj, allowed in subjects.items():
                if not db.query(Retake).filter_by(access_code=code, subject=subj).first():
                    db.add(Retake(
                        access_code=code,
                        subject=subj,
                        allowed=allowed
                    ))
                    retakes_count += 1

        # --- Migrate Leaderboard ---
        leaderboard = data.get("leaderboard", [])
        for entry in leaderboard:
            if not db.query(Leaderboard).filter_by(
                access_code=entry.get("access_code"),
                subject=entry.get("subject")
            ).first():
                db.add(Leaderboard(
                    name=entry.get("name", ""),
                    access_code=entry.get("access_code", ""),
                    subject=entry.get("subject", ""),
                    score=entry.get("score", 0),
                    timestamp=entry.get("timestamp")
                ))
                leaderboard_count += 1

        # --- Migrate Config ---
        config = data.get("config", {})
        for key, value in config.items():
            if not db.query(Config).filter_by(key=key).first():
                db.add(Config(key=key, value=value))
                config_count += 1

        db.commit()

        print(f"✅ Full migration completed.")
        print(f" - {users_count} users processed")
        print(f" - {admins_count} admins processed")
        print(f" - {questions_count} question sets processed")
        print(f" - {submissions_count} submissions processed")
        print(f" - {retakes_count} retake records processed")
        print(f" - {leaderboard_count} leaderboard entries processed")
        print(f" - {config_count} config entries processed")

    except Exception as e:
        db.rollback()
        print(f"❌ Migration failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
