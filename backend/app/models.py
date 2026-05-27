from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class UserRole(str, Enum):
    ADMIN = "Admin"
    MANAGER = "Manager"
    TRAINER = "Trainer"
    EMPLOYEE = "Employee"


class EnrollmentStatus(str, Enum):
    NOT_STARTED = "Not Started"
    IN_PROGRESS = "In Progress"
    PENDING_VERIFICATION = "Pending Verification"
    COMPLETED = "Completed"


class SkillCategory(str, Enum):
    CORE = "Core Job Role"
    SECONDARY = "Secondary"
    SOFT = "Soft Skill"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), default=UserRole.EMPLOYEE)
    manager_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    manager = relationship("User", remote_side=[id], backref="direct_reports")


class TrainingModule(Base):
    __tablename__ = "training_modules"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    prerequisite_id: Mapped[int | None] = mapped_column(ForeignKey("training_modules.id"), nullable=True)

    prerequisite = relationship("TrainingModule", remote_side=[id])


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("training_modules.id"))
    trainer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    max_capacity: Mapped[int] = mapped_column(Integer)


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("user_id", "module_id", name="uq_user_module"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    module_id: Mapped[int] = mapped_column(ForeignKey("training_modules.id"))
    status: Mapped[EnrollmentStatus] = mapped_column(SQLEnum(EnrollmentStatus), default=EnrollmentStatus.NOT_STARTED)
    verified_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    completion_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SkillsInventory(Base):
    __tablename__ = "skills_inventory"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    skill_name: Mapped[str] = mapped_column(String(255), index=True)
    category: Mapped[SkillCategory] = mapped_column(SQLEnum(SkillCategory))
    proficiency_level: Mapped[int] = mapped_column(Integer)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    shadowing_context_notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Documentation(Base):
    __tablename__ = "documentation"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    content_markdown: Mapped[str] = mapped_column(Text)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    needs_review_flag: Mapped[bool] = mapped_column(Boolean, default=False)


class ScheduleRSVP(Base):
    __tablename__ = "schedule_rsvps"
    __table_args__ = (UniqueConstraint("schedule_id", "user_id", name="uq_schedule_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("schedules.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class TechStackTemplate(Base):
    __tablename__ = "tech_stack_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    created_by_manager_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class TechStackSkill(Base):
    __tablename__ = "tech_stack_skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("tech_stack_templates.id"))
    skill_name: Mapped[str] = mapped_column(String(255))
    min_proficiency_required: Mapped[int] = mapped_column(Integer)


class UserTechStack(Base):
    __tablename__ = "user_tech_stacks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    template_id: Mapped[int] = mapped_column(ForeignKey("tech_stack_templates.id"))
    assigned_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    assigned_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
