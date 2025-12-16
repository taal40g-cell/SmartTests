# ================================================
# SmartTests Multi-Tenant Database Models
# SQLAlchemy 2.0 Ready
# ================================================
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, Float, DateTime, Text, JSON,
    ForeignKey, UniqueConstraint, func
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# ================================================
# TENANT MIXIN
# ================================================
class TenantMixin:
    """Adds optional school_id for multi-tenant data."""
    school_id = Column(
        Integer,
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=True,  # superadmin may have no school
        index=True
    )

# ================================================
# SCHOOL
# ================================================
class School(Base):
    __tablename__ = "schools"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    address = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    students = relationship("Student", back_populates="school", cascade="all, delete-orphan")
    admins = relationship("Admin", back_populates="school", cascade="all, delete-orphan")
    users = relationship("User", back_populates="school", cascade="all, delete-orphan")
    questions = relationship("Question", back_populates="school", cascade="all, delete-orphan")
    submissions = relationship("Submission", back_populates="school", cascade="all, delete-orphan")
    leaderboard_entries = relationship("Leaderboard", back_populates="school", cascade="all, delete-orphan")
    retakes = relationship("Retake", back_populates="school", cascade="all, delete-orphan")
    test_results = relationship("TestResult", back_populates="school", cascade="all, delete-orphan")
    subjects = relationship("Subject", back_populates="school", cascade="all, delete-orphan")
    durations = relationship("TestDuration", back_populates="school")
    archived_questions = relationship("ArchivedQuestion", back_populates="school", cascade="all, delete-orphan")
    subjective_submissions = relationship(
    "SubjectiveSubmission", back_populates="school", cascade="all, delete-orphan"
)

# ================================================
# STUDENT
# ================================================
class Student(Base, TenantMixin):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    unique_id = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    class_name = Column(String(50), nullable=False)
    access_code = Column(String(50), unique=True, nullable=False)
    can_retake = Column(Boolean, default=True)
    submitted = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    school = relationship("School", back_populates="students")
    submissions = relationship("Submission", back_populates="student", cascade="all, delete-orphan")
    leaderboard_entries = relationship("Leaderboard", back_populates="student", cascade="all, delete-orphan")
    retakes = relationship("Retake", back_populates="student", cascade="all, delete-orphan")
    test_results = relationship("TestResult", back_populates="student", cascade="all, delete-orphan")
    progress = relationship("StudentProgress", back_populates="student", cascade="all, delete-orphan")
    subjective_submissions = relationship("SubjectiveSubmission", back_populates="student", cascade="all, delete-orphan")

# ================================================
# ADMIN
# ================================================
class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    role = Column(String(50), default="school_admin")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True)
    school = relationship("School", back_populates="admins")

# ================================================
# USER (Teacher / Staff)
# ================================================
class User(Base, TenantMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    questions = relationship("Question", back_populates="creator", cascade="all, delete-orphan")
    archived_questions = relationship("ArchivedQuestion", back_populates="creator")  # ✅ added
    school = relationship("School", back_populates="users")

# ================================================
# SUBJECTS
# ================================================
class Subject(Base, TenantMixin):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    class_name = Column(String(50), nullable=False)

    # Add school_id for multi-tenant
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    questions = relationship("Question", back_populates="subject_rel", cascade="all, delete-orphan")
    archived_questions = relationship("ArchivedQuestion", back_populates="subject_rel")
    school = relationship("School", back_populates="subjects")

    # 🔹 Relationship for Retakes
    retakes = relationship("Retake", back_populates="subject", cascade="all, delete-orphan")

# ================================================
# QUESTIONS
# ================================================
class Question(Base, TenantMixin):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True)
    class_name = Column(String(50), nullable=False)
    subject = Column(String(100), nullable=True)  # optional text field for quick filtering
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    question_text = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)
    answer = Column(String(255), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    archived = Column(Boolean, default=False)
    archived_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    creator = relationship("User", back_populates="questions")
    submissions = relationship("Submission", back_populates="question", cascade="all, delete-orphan")
    school = relationship("School", back_populates="questions")
    subject_rel = relationship("Subject", back_populates="questions", foreign_keys=[subject_id])

# ================================================
# SUBMISSION
# ================================================
class Submission(Base, TenantMixin):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    selected_answer = Column(String(255), nullable=False)
    correct = Column(Boolean, nullable=False)
    subject = Column(String(100), nullable=False)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    student = relationship("Student", back_populates="submissions")
    question = relationship("Question", back_populates="submissions")
    school = relationship("School", back_populates="submissions")

# ================================================
# RETAKE
# ================================================
class Retake(Base, TenantMixin):
    __tablename__ = "retakes"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    can_retake = Column(Boolean, default=False, server_default="0")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("student_id", "subject_id", name="uq_retake_student_subject"),
    )

    # Relationships
    student = relationship("Student", back_populates="retakes")
    subject = relationship("Subject", back_populates="retakes")
    school = relationship("School", back_populates="retakes")

# ================================================
# LEADERBOARD
# ================================================
class Leaderboard(Base, TenantMixin):
    __tablename__ = "leaderboard"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    class_name = Column(String(50))
    score = Column(Float)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    student = relationship("Student", back_populates="leaderboard_entries")
    school = relationship("School", back_populates="leaderboard_entries")

# ================================================
# TEST RESULTS
# ================================================
class TestResult(Base, TenantMixin):
    __tablename__ = "test_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    subject = Column(String(100), nullable=False)
    score = Column(Integer, nullable=False)
    total = Column(Integer, nullable=False)
    percentage = Column(Float, nullable=False)
    taken_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    student = relationship("Student", back_populates="test_results")
    school = relationship("School", back_populates="test_results")



class StudentProgress(Base):
    __tablename__ = "student_progress"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    access_code = Column(String(10), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)  # ✅ changed to ID
    answers = Column(JSON, nullable=False, default=list)
    current_q = Column(Integer, default=0)
    start_time = Column(Float, nullable=False)
    duration = Column(Integer, nullable=False)
    questions = Column(JSON, nullable=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    test_type = Column(String(20), nullable=False, default="objective")
    submitted = Column(Boolean, default=False, nullable=False)
    last_saved = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    student = relationship("Student", back_populates="progress")
    school = relationship("School")
    subject_rel = relationship("Subject")  # Optional: link to subject table


# ================================================
# CONFIG
# ================================================
class Config(Base):
    __tablename__ = "config"

    id = Column(Integer, primary_key=True)
    key = Column(String(50), unique=True, nullable=False)
    value = Column(String(255), nullable=False)

# ================================================
# AUDIT LOG
# ================================================
class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action_type = Column(String(100))
    details = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())



class TestDuration(Base):
    __tablename__ = "test_duration"

    id = Column(Integer, primary_key=True, autoincrement=True)
    class_name = Column(String(50), nullable=False)
    subject = Column(String(100), nullable=False)
    duration = Column(Integer, nullable=False)  # duration in seconds
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)

    # optional relationship for clarity
    school = relationship("School", back_populates="durations", lazy="joined")

# ================================================
# ARCHIVED QUESTIONS
# ================================================
class ArchivedQuestion(Base, TenantMixin):
    __tablename__ = "archived_questions"

    id = Column(Integer, primary_key=True)
    class_name = Column(String(50), nullable=False)
    subject = Column(String(100), nullable=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=True)
    question_text = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)
    answer = Column(String(255), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True))
    archived = Column(Boolean, default=True)
    archived_at = Column(DateTime(timezone=True), server_default=func.now())
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)

    # Relationships
    creator = relationship("User", back_populates="archived_questions", foreign_keys=[created_by])
    school = relationship("School", back_populates="archived_questions")
    subject_rel = relationship("Subject", back_populates="archived_questions", foreign_keys=[subject_id])




# -----------------------------------------------------
# 📝 1. Subjective Questions
# -----------------------------------------------------
class SubjectiveQuestion(Base):
    __tablename__ = "subjective_questions"

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    class_name = Column(String, nullable=False)
    subject = Column(String(100), nullable=False)  # ✅ Add this line
    subject_id = Column(Integer, ForeignKey("subjects.id"))  # ✅ Keep this link
    question_text = Column(Text, nullable=False)
    marks = Column(Integer, default=10)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    subject_rel = relationship("Subject")  # ✅ To access subject details
    answers = relationship("SubjectiveAnswer", back_populates="question", cascade="all, delete-orphan")

class SubjectiveAnswer(Base):
    __tablename__ = "subjective_answers"

    id = Column(Integer, primary_key=True)
    school_id = Column(String, nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"))
    access_code = Column(String, nullable=False)
    class_name = Column(String, nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"))  # ✅ Linked as well
    question_id = Column(Integer, ForeignKey("subjective_questions.id"))
    answer_text = Column(Text)
    uploaded_file = Column(String)
    submitted_on = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="Pending Review")

    question = relationship("SubjectiveQuestion", back_populates="answers")
    grade = relationship("SubjectiveGrade", back_populates="answer", uselist=False)
    subject_rel = relationship("Subject")  # ✅ optional convenience link


class SubjectiveGrade(Base):
    __tablename__ = "subjective_grades"

    id = Column(Integer, primary_key=True)
    school_id = Column(String, nullable=False)
    answer_id = Column(Integer, ForeignKey("subjective_answers.id"))
    teacher_id = Column(Integer, ForeignKey("admins.id"))
    score = Column(Integer)
    comment = Column(Text)
    graded_on = Column(DateTime, default=datetime.utcnow)

    answer = relationship("SubjectiveAnswer", back_populates="grade")


# ================================================
# SUBJECTIVE SUBMISSION
# ================================================
class SubjectiveSubmission(Base, TenantMixin):
    __tablename__ = "subjective_submissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)  # ✅ add this line
    subject = Column(String(100), nullable=False)
    answers = Column(JSON, nullable=False)  # Store all typed answers
    attachments = Column(JSON, nullable=True)  # List of uploaded file paths or URLs
    status = Column(String(50), default="Pending Review")  # Pending / Reviewed / Graded
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())

    # ✅ Relationships
    student = relationship("Student", back_populates="subjective_submissions")
    school = relationship("School", back_populates="subjective_submissions")


class ObjectiveQuestion(Base):
    __tablename__ = "objective_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    class_name = Column(String, nullable=False)
    subject = Column(String(100), nullable=False)
    question_text = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)
    correct_answer = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)



