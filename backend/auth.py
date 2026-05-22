
import random
from database import get_session
from models import ObjectiveQuestion  # updated model




def patch_objective_questions_with_options():
    db = get_session()
    try:
        # Fetch only objective questions with empty options
        questions = db.query(ObjectiveQuestion).filter(
            (ObjectiveQuestion.options == None) | (ObjectiveQuestion.options == [])
        ).all()

        print(f"🔍 Found {len(questions)} questions with empty options")

        if not questions:
            print("✅ No questions need patching.")
            return

        for q in questions:
            # Customize distractors here
            distractors = ["Option A", "Option B", "Option C"]

            # Ensure correct answer is included
            correct = q.correct_answer.strip() if q.correct_answer else "Answer"
            options = distractors + [correct]
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
    patch_objective_questions_with_options()