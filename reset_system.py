from sqlalchemy import text
from backend.database import get_session

db = get_session()

try:

    print("Starting submission cleanup...\n")

    tables = [

        "student_answers",
        "student_progress",
        "student_results",
        "subjective_grades",
        "leaderboard",
        "student_attempts",
        "archived_progress",
        "anti_cheat_logs",
        "retakes",
        "student_sessions"
    ]

    for table in tables:

        try:

            print(f"Deleting from: {table}")

            db.execute(
                text(f"DELETE FROM {table}")
            )

            # Reset SQLite auto increment
            try:

                db.execute(
                    text(
                        f"""
                        DELETE FROM sqlite_sequence
                        WHERE name='{table}'
                        """
                    )
                )

            except Exception:
                pass

        except Exception as e:

            print(f"Skipping {table}: {e}")

    db.commit()

    print("\n✅ ALL STUDENT SUBMISSIONS CLEARED")

except Exception as e:

    db.rollback()

    print(f"\n❌ RESET FAILED: {e}")

finally:

    db.close()