from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, Float, JSON, ForeignKey, UniqueConstraint, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
Base = declarative_base()

# -----------------------------
# Students
# -----------------------------
class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True)  # auto increment
    unique_id = Column(String(20), unique=True, nullable=False, index=True)  # permanent tracking ID
    name = Column(String(255), nullable=False)
    class_name = Column(String(50), nullable=False)
    access_code = Column(String(50), unique=True, nullable=False)  # used for login
    can_retake = Column(Boolean, default=True)
    submitted = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # ✅ Relationships
    submissions = relationship("Submission", back_populates="student")
    results = relationship("TestResult", back_populates="student")
    leaderboard_entries = relationship("Leaderboard", back_populates="student")


# -----------------------------
# Users (Admins / Teachers)
# -----------------------------
class Admin(Base):
    __tablename__ = "admins"
    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    role = Column(String(50), default="super_admin")  # add this
    created_at = Column(DateTime(timezone=True), server_default=func.now())



class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=False)  # hashed passwords
    role = Column(String(50), nullable=False)       # "admin" or "teacher"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # ✅ Add this line
    questions = relationship("Question", back_populates="creator")

# -----------------------------
# Questions (no subject)
# -----------------------------
class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True)
    class_name = Column(String(50), nullable=False)
    subject = Column(String(100), nullable=False)
    question_text = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)
    answer = Column(String(255), nullable=False)  # ✅ renamed, consistent
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # ✅ New archive-related fields
    archived = Column(Boolean, default=False)
    archived_at = Column(DateTime(timezone=True), nullable=True)

    # Optional: link back to creator
    creator = relationship("User", back_populates="questions", lazy="joined")

    # ✅ Add this relationship (this fixes your error)
    submissions = relationship("Submission", back_populates="question", cascade="all, delete-orphan")

# -----------------------------
# Submissions
# -----------------------------
class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    selected_answer = Column(String(255), nullable=False)
    correct = Column(Boolean, nullable=False)
    subject = Column(String(100), nullable=False, default="Unknown")
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())

    # ✅ Relationships
    student = relationship("Student", back_populates="submissions")
    question = relationship("Question", back_populates="submissions")


# -----------------------------
# Retakes
# -----------------------------
class Retake(Base):
    __tablename__ = "retakes"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    subject = Column(String(100))  # per-subject retake tracking
    can_retake = Column(Boolean, default=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("student_id", "subject", name="uq_retake_student_subject"),)

# -----------------------------
# Leaderboard
# -----------------------------
class Leaderboard(Base):
    __tablename__ = "leaderboard"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    class_name = Column(String(50))
    score = Column(Float)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())

    # ✅ Relationship
    student = relationship("Student", back_populates="leaderboard_entries")


# -----------------------------
# Audit / Action Log
# -----------------------------
class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action_type = Column(String(100))  # e.g., 'upload_question', 'delete_question'
    details = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# -----------------------------
# Config (optional settings)
# -----------------------------
class Config(Base):
    __tablename__ = "config"
    id = Column(Integer, primary_key=True)
    key = Column(String(50), unique=True, nullable=False)
    value = Column(String(255), nullable=False)


# -----------------------------
# Test Results
# -----------------------------
class TestResult(Base):
    __tablename__ = "test_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    subject = Column(String(100), nullable=False)
    score = Column(Integer, nullable=False)
    total = Column(Integer, nullable=False)
    percentage = Column(Float, nullable=False)
    taken_at = Column(DateTime(timezone=True), server_default=func.now())

    # ✅ Relationship
    student = relationship("Student", back_populates="results")


class StudentProgress(Base):
    __tablename__ = "student_progress"

    id = Column(Integer, primary_key=True)
    access_code = Column(String(10), nullable=False)
    subject = Column(String(100), nullable=False)
    answers = Column(JSON, nullable=False, default=list)
    current_q = Column(Integer, default=0)
    start_time = Column(Float, nullable=False)
    duration = Column(Integer, nullable=False)
    questions = Column(JSON, nullable=True)  # ✅ added to keep order fixed
    last_saved = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
