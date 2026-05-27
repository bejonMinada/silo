from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

from .models import EnrollmentStatus, SkillCategory, UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    name: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RoleUpdateRequest(BaseModel):
    role: UserRole


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: UserRole
    manager_id: int | None

    class Config:
        from_attributes = True


class TrainingModuleCreate(BaseModel):
    title: str
    description: str
    prerequisite_id: int | None = None


class TrackChainRequest(BaseModel):
    module_ids: list[int]


class ScheduleCreate(BaseModel):
    module_id: int
    trainer_id: int
    start_time: datetime
    end_time: datetime
    max_capacity: int = Field(ge=1)


class EnrollmentCreate(BaseModel):
    module_id: int


class EnrollmentStatusUpdate(BaseModel):
    status: EnrollmentStatus


class SkillCreate(BaseModel):
    skill_name: str
    category: SkillCategory
    proficiency_level: int = Field(ge=1, le=5)
    shadowing_context_notes: str | None = None


class DocumentationCreate(BaseModel):
    title: str
    content_markdown: str


class TechStackTemplateCreate(BaseModel):
    name: str
    description: str


class TechStackSkillCreate(BaseModel):
    skill_name: str
    min_proficiency_required: int = Field(ge=1, le=5)


class TechStackAssignRequest(BaseModel):
    user_id: int
