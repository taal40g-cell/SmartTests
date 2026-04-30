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
# CLASS
# ================================================
class Class(Base, TenantMixin):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    normalized_name = Column(String(50), nullable=False)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("normalized_name", "school_id", name="uq_class_school"),
    )

    # Relationships
    students = relationship("Student", back_populates="class_")  # do NOT delete students automatically
    school = relationship("School", back_populates="classes")

    subjects = relationship(
        "Subject",
        back_populates="class_",
        cascade="all, delete-orphan"  # safe: subjects cannot exist without a class
    )

    archived_questions = relationship(
        "ArchivedQuestion",
        back_populates="class_",
        cascade="all, delete-orphan"  # safe
    )

    durations = relationship(
        "TestDuration",
        back_populates="class_",
        cascade="all, delete-orphan"  # safe
    )

    progress = relationship(
        "StudentProgress",
        back_populates="class_"  # do NOT delete historical progress
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
    is_system = Column(Boolean, default=False, nullable=False, index=True)

    # Relationships
    durations = relationship("TestDuration", back_populates="school", cascade="all, delete-orphan")
    students = relationship("Student", back_populates="school")  # do NOT delete students automatically
    admins = relationship("Admin", back_populates="school", cascade="all, delete-orphan")
    users = relationship("User", back_populates="school", cascade="all, delete-orphan")
    progress = relationship("StudentProgress", back_populates="school")  # historical, keep safe
    leaderboard_entries = relationship("Leaderboard", back_populates="school")  # keep historical
    retakes = relationship("Retake", back_populates="school")  # keep historical
    test_results = relationship("TestResult", back_populates="school")  # keep historical
    subjects = relationship("Subject", back_populates="school", cascade="all, delete-orphan")
    archived_questions = relationship("ArchivedQuestion", back_populates="school", cascade="all, delete-orphan")
    classes = relationship("Class", back_populates="school", cascade="all, delete-orphan")


# ================================================
# STUDENT
# ================================================
from sqlalchemy import UniqueConstraint
class Student(Base, TenantMixin):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    unique_id = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)

    # ❗ REMOVE global unique=True
    access_code = Column(String(50), nullable=False)

    can_retake = Column(Boolean, default=True)
    submitted = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)

    __table_args__ = (
        # ✅ Student identity
        UniqueConstraint("name", "class_id", "school_id", name="uq_student_identity"),

        # ✅ Access code scoped to school
        UniqueConstraint("access_code", "school_id", name="uq_access_code_school"),
    )

    # Relationships
    school = relationship("School", back_populates="students")
    progress = relationship("StudentProgress", back_populates="student")
    leaderboard_entries = relationship("Leaderboard", back_populates="student")
    retakes = relationship("Retake", back_populates="student")
    test_results = relationship("TestResult", back_populates="student")
    class_ = relationship("Class", back_populates="students")



# ================================================
# ADMIN
# ================================================
from sqlalchemy import UniqueConstraint
class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True)
    username = Column(String(100), nullable=False)
    password_hash = Column(String(200), nullable=False)
    role = Column(String(50), default="school_admin")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True)
    school = relationship("School", back_populates="admins")

    __table_args__ = (
        UniqueConstraint("username", "school_id", name="uq_admin_username_school"),
    )

# ================================================
# USER (Teacher / Staff)
# ================================================
class User(Base, TenantMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(255), nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    archived_questions = relationship("ArchivedQuestion", back_populates="creator")  # ✅ added
    school = relationship("School", back_populates="users")

# ================================================
# SUBJECTS
# ================================================
class Subject(Base, TenantMixin):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)

    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("name", "class_id", "school_id", name="uq_subject_class_school"),
    )

    # Relationships
    class_ = relationship("Class", back_populates="subjects")
    archived_questions = relationship("ArchivedQuestion", back_populates="subject_rel")
    school = relationship("School", back_populates="subjects")
    retakes = relationship("Retake", back_populates="subject", cascade="all, delete-orphan")
    durations = relationship("TestDuration", back_populates="subject")  # added



# ================================================
# QUESTIONS (Deprecated / for reference only)
# ================================================
# class Question(Base, TenantMixin):
#     __tablename__ = "questions"
#
#     id = Column(Integer, primary_key=True)
#
#     # 🔥 Replace class_name with class_id
#     class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
#
#     subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
#     question_text = Column(Text, nullable=False)
#     options = Column(JSON, nullable=False)
#     answer = Column(String(255), nullable=False)
#     test_type = Column(String(50), nullable=False, default="objective")
#     created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     archived = Column(Boolean, default=False)
#     archived_at = Column(DateTime(timezone=True), nullable=True)
#     school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
#
#     # Relationships
#     creator = relationship("User", back_populates="questions")
#     school = relationship("School", back_populates="questions")
#     subject_rel = relationship("Subject", back_populates="questions", foreign_keys=[subject_id])
#     class_ = relationship("Class")  # optional, to easily get class info


# ================================================
# RETAKE (FIXED STRUCTURE)
# ================================================
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime,
    ForeignKey, UniqueConstraint, Index, func
)
from sqlalchemy.sql import expression

class Retake(Base, TenantMixin):
    __tablename__ = "retakes"

    id = Column(Integer, primary_key=True)

    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)

    test_type = Column(String(20), nullable=False, default="objective")

    can_retake = Column(
        Boolean,
        default=False,
        server_default=expression.false()
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "subject_id",
            "school_id",
            "class_id",
            "test_type",
            name="uq_retake_full_identity"
        ),
        Index(
            "idx_retake_lookup",
            "student_id",
            "subject_id",
            "school_id",
            "class_id",
            "test_type"
        ),
    )

    school = relationship("School", back_populates="retakes")
    student = relationship("Student", back_populates="retakes")
    subject = relationship("Subject", back_populates="retakes")
    class_ = relationship("Class")



# ================================================
# LEADERBOARD
# ================================================
class Leaderboard(Base, TenantMixin):
    __tablename__ = "leaderboard"


    id = Column(Integer, primary_key=True)

    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)

    score = Column(Float, nullable=False)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    student = relationship("Student", back_populates="leaderboard_entries")
    class_ = relationship("Class")
    school = relationship("School", back_populates="leaderboard_entries")



# ================================================
# TEST RESULTS
# ================================================
from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func




class TestResult(Base):
    __tablename__ = "test_results"

    id = Column(Integer, primary_key=True, autoincrement=True)

    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False, index=True)

    score = Column(Integer, nullable=False)
    total = Column(Integer, nullable=False)
    percentage = Column(Float, nullable=False)

    taken_at = Column(DateTime(timezone=True), server_default=func.now())

    # -------------------------
    # Relationships
    # -------------------------
    student = relationship("Student", back_populates="test_results")  # no delete-orphan
    school = relationship("School", back_populates="test_results")    # no delete-orphan
    subject = relationship("Subject")  # optional back_populates if needed
    student_class = relationship("Class")  # optional back_populates if needed



from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from datetime import datetime

class AntiCheatLog(Base):
    __tablename__ = "anti_cheat_logs"

    id = Column(Integer, primary_key=True, index=True)

    progress_id = Column(Integer, ForeignKey("student_progress.id"), index=True)

    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)

    school_id = Column(Integer, nullable=False, index=True)

    test_type = Column(String, nullable=False)  # objective / subjective
    event_type = Column(String, nullable=False)  # paste / tab_switch / window_blur / etc

    timestamp = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_student_subject", "student_id", "subject_id"),
        Index("idx_progress_event", "progress_id", "event_type"),
    )



# ================================================
# StudentProgress
# ================================================
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy import Column, Integer, String, Boolean, Float, JSON, DateTime, Text, ForeignKey, UniqueConstraint, Index
class StudentProgress(Base):
    __tablename__ = "student_progress"

    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "access_code",
            "subject_id",
            "school_id",
            "class_id",
            "test_type",
            name="uq_student_test_session"
        ),
        Index(
            "idx_progress_lookup",
            "student_id",
            "access_code",
            "subject_id",
            "school_id",
            "class_id",
            "test_type"
        ),
    )

    # -------------------------
    # Primary Key
    # -------------------------
    id = Column(Integer, primary_key=True)

    # -------------------------
    # Identity Fields
    # -------------------------
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)

    access_code = Column(String(10), nullable=False)

    # -------------------------
    # Test Metadata
    # -------------------------
    test_type = Column(String(20), nullable=False, default="objective")

    answers = Column(JSON, nullable=False, default=lambda: [])
    attachments = Column(JSON, nullable=True)

    current_q = Column(Integer, default=0)

    # ✅ FIXED (CRITICAL)
    start_time = Column(Float, nullable=True)   # was NOT NULL ❌
    duration = Column(Integer, nullable=True)    # was NOT NULL ❌

    # -------------------------
    # Audit Fields
    # -------------------------
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_saved = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    submitted = Column(Boolean, default=False, nullable=False)

    # -------------------------
    # Review / Grading Workflow
    # -------------------------
    review_status = Column(String(20), default="pending", nullable=False)
    locked = Column(Boolean, default=False, nullable=False)

    score = Column(Float, nullable=True)
    review_comment = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(String(100), nullable=True)

    # -------------------------
    # Relationships
    # -------------------------
    student = relationship("Student", back_populates="progress")
    school = relationship("School", back_populates="progress")
    subject = relationship("Subject")
    class_ = relationship("Class")

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
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    duration = Column(Integer, nullable=False)  # duration in seconds
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)

    # Relationships
    school = relationship("School", back_populates="durations")  # ✅ ensure School has .durations
    class_ = relationship("Class", back_populates="durations")   # optional but recommended
    subject = relationship("Subject", back_populates="durations")

# ================================================
# ARCHIVED QUESTIONS
# ================================================
class ArchivedQuestion(Base, TenantMixin):
    __tablename__ = "archived_questions"

    id = Column(Integer, primary_key=True)

    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)

    question_text = Column(Text, nullable=False)
    options = Column(JSON, nullable=True)

    answer = Column(String(255), nullable=True)

    test_type = Column(String(50), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True))
    archived_at = Column(DateTime(timezone=True), server_default=func.now())

    creator = relationship("User", back_populates="archived_questions")
    school = relationship("School", back_populates="archived_questions")
    subject_rel = relationship("Subject", back_populates="archived_questions")
    class_ = relationship("Class", back_populates="archived_questions")


# ================================================
# ARCHIVED PROGRESS
# ================================================


class ArchivedProgress(Base):
    __tablename__ = "archived_progress"

    id = Column(Integer, primary_key=True)

    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)

    test_type = Column(String(20), nullable=False)

    answers_snapshot = Column(JSON, nullable=False)
    questions_snapshot = Column(JSON, nullable=False)

    score = Column(Float, nullable=True)

    submitted_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # Cross-device integrity token
    session_hash = Column(String(255), nullable=False)

    __table_args__ = (
        Index("idx_archive_lookup", "student_id", "subject_id", "school_id"),
    )


# -----------------------------------------------------
# 📝 1. Subjective Questions
# -----------------------------------------------------
class SubjectiveQuestion(Base, TenantMixin):
    __tablename__ = "subjective_questions"

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)

    question_text = Column(Text, nullable=False)
    marks = Column(Integer, default=10)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    subject = relationship("Subject")

class SubjectiveGrade(Base, TenantMixin):
    __tablename__ = "subjective_grades"

    id = Column(Integer, primary_key=True)

    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)

    question_id = Column(Integer, ForeignKey("subjective_questions.id"), nullable=True)

    score = Column(Integer, nullable=False)
    feedback = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True),
                        server_default=func.now())



class ObjectiveQuestion(Base, TenantMixin):
    __tablename__ = "objective_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)

    question_text = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)
    correct_answer = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    subject = relationship("Subject")




from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, UniqueConstraint, Index
from datetime import datetime

class StudentAnswer(Base):
    __tablename__ = "student_answers"

    id = Column(Integer, primary_key=True, index=True)

    progress_id = Column(Integer, ForeignKey("student_progress.id"), nullable=False, index=True)
    question_id = Column(Integer, nullable=False, index=True)

    answer = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)

    # 🚀 Prevent duplicate answers for same question in same session
    __table_args__ = (
        UniqueConstraint("progress_id", "question_id", name="uq_progress_question"),
        Index("idx_progress_question", "progress_id", "question_id"),
    )




class StudentResult(Base):
    __tablename__ = "student_results"

    id = Column(Integer, primary_key=True)

    progress_id = Column(Integer, ForeignKey("student_progress.id"), index=True)

    score = Column(Integer)
    percent = Column(Float)

    review_status = Column(String, default="pending")
    review_comment = Column(Text)

    reviewed_at = Column(DateTime)
    reviewed_by = Column(Integer)