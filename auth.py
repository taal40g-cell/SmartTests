# patch_fill_options.py
import random
from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import JSONB
from database import get_session
from models import Question

def patch_questions_with_options():
    db = get_session()
    try:
        # Fetch only questions with empty options ([])
        questions = db.query(Question).filter(
            cast(Question.options, JSONB) == []
        ).all()

        print(f"🔍 Found {len(questions)} questions with empty options")

        if not questions:
            print("✅ No questions need patching.")
            return

        for q in questions:
            # You can customize distractors here per subject/class
            distractors = ["Option A", "Option B", "Option C"]

            # Make sure correct answer is included, randomize order
            options = distractors + [q.correct_answer]
            random.shuffle(options)

            q.options = options
            print(f"✅ Patched Q{q.id}: {q.question_text[:50]}...")

        db.commit()
        print(f"🎉 Successfully updated {len(questions)} questions")
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    patch_questions_with_options()
