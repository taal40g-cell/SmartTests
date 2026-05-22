from pydantic import BaseModel
from typing import Optional

class ViolationSchema(BaseModel):
    progress_id: int
    student_id: int
    subject_id: int
    question_id: Optional[int] = None
    school_id: int
    test_type: str
    event_type: str