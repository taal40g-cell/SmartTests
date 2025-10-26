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
    school = relationship("School", back_populates="users")

# ================================================
# SUBJECTS
# ================================================
class Subject(Base, TenantMixin):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    class_name = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    questions = relationship("Question", back_populates="subject_rel", cascade="all, delete-orphan")
    school = relationship("School", back_populates="subjects")

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
    subject = Column(String(100), nullable=False)
    can_retake = Column(Boolean, default=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("student_id", "subject", name="uq_retake_student_subject"),)

    # Relationships
    student = relationship("Student", back_populates="retakes")
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

# ================================================
# STUDENT PROGRESS
# ================================================
class StudentProgress(Base):
    __tablename__ = "student_progress"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    access_code = Column(String(10), nullable=False)
    subject = Column(String(100), nullable=False)
    answers = Column(JSON, nullable=False, default=list)
    current_q = Column(Integer, default=0)
    start_time = Column(Float, nullable=False)
    duration = Column(Integer, nullable=False)
    questions = Column(JSON, nullable=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)  # new column
    last_saved = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship
    student = relationship("Student", back_populates="progress")
    school = relationship("School")  # optional, for easier access to school info

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

