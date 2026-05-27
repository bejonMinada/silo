import logging
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

from .auth import COMPANY_DOMAIN, create_access_token, get_current_user, get_db, require_roles
from .database import Base, engine
from .models import (
    Documentation,
    Enrollment,
    EnrollmentStatus,
    Schedule,
    ScheduleRSVP,
    SkillCategory,
    SkillsInventory,
    TechStackSkill,
    TechStackTemplate,
    TrainingModule,
    User,
    UserRole,
    UserTechStack,
)
from .schemas import (
    DocumentationCreate,
    EnrollmentCreate,
    EnrollmentStatusUpdate,
    LoginRequest,
    RoleUpdateRequest,
    ScheduleCreate,
    SkillCreate,
    TechStackAssignRequest,
    TechStackSkillCreate,
    TechStackTemplateCreate,
    TokenResponse,
    TrackChainRequest,
    TrainingModuleCreate,
    UserOut,
)
from .settings import settings

logger = logging.getLogger("silo.api")
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        response.headers["x-request-id"] = request_id
        logger.info(
            "request.completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > settings.max_request_body_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": {
                                "code": "request_too_large",
                                "message": "Request body exceeds allowed size",
                                "request_id": getattr(request.state, "request_id", None),
                            }
                        },
                    )
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": {
                            "code": "invalid_content_length",
                            "message": "Invalid Content-Length header",
                            "request_id": getattr(request.state, "request_id", None),
                        }
                    }
                )
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    _buckets: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        if request.url.path in {"/api/health", "/api/ready"}:
            return await call_next(request)

        now = time.time()
        key = f"{request.client.host}:{request.url.path}" if request.client else request.url.path
        bucket = self._buckets[key]
        window_start = now - settings.rate_limit_window_seconds
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= settings.rate_limit_requests_per_minute:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "rate_limit_exceeded",
                        "message": "Too many requests",
                        "request_id": getattr(request.state, "request_id", None),
                    }
                },
            )
        bucket.append(now)
        return await call_next(request)


app = FastAPI(title="Silo API", debug=settings.debug)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins if settings.cors_allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    if settings.create_schema_on_startup:
        Base.metadata.create_all(bind=engine)
        logger.info("schema.auto_created_on_startup")
    else:
        logger.info("schema.auto_create_disabled_expect_migrations")


def _error_payload(request: Request, code: str, message: str):
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": getattr(request.state, "request_id", None),
        }
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    code = str(exc.status_code)
    if isinstance(exc.detail, str):
        message = exc.detail
    else:
        message = "Request failed"
    return JSONResponse(status_code=exc.status_code, content=_error_payload(request, code, message))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("request.unhandled_exception", exc_info=exc)
    return JSONResponse(status_code=500, content=_error_payload(request, "internal_error", "Internal server error"))


def _validate_prerequisite(db: Session, user_id: int, module_id: int) -> None:
    module = db.query(TrainingModule).filter(TrainingModule.id == module_id).first()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    if not module.prerequisite_id:
        return
    prereq = (
        db.query(Enrollment)
        .filter(
            Enrollment.user_id == user_id,
            Enrollment.module_id == module.prerequisite_id,
            Enrollment.status == EnrollmentStatus.COMPLETED,
        )
        .first()
    )
    if not prereq:
        raise HTTPException(status_code=400, detail="Prerequisite module must be completed first")


def _audit(event: str, actor: User | None, metadata: dict | None = None) -> None:
    logger.info(
        "audit.event",
        extra={
            "event": event,
            "actor_id": actor.id if actor else None,
            "actor_role": actor.role.value if actor else None,
            "metadata": metadata or {},
        },
    )


@app.get("/api/health")
def health():
    return {"status": "ok", "env": settings.app_env}


@app.get("/api/ready")
def ready():
    return {"status": "ready", "database": "configured"}


@app.post("/api/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    if not payload.email.endswith(f"@{COMPANY_DOMAIN}"):
        raise HTTPException(status_code=403, detail="Company domain required")

    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        user = User(email=payload.email, name=payload.name or payload.email.split("@")[0], role=UserRole.EMPLOYEE)
        db.add(user)
        db.commit()
        db.refresh(user)
    token = create_access_token(str(user.id), user.role)
    return TokenResponse(access_token=token)


@app.get("/api/users/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@app.post("/api/admin/users/{user_id}/role", response_model=UserOut)
def set_role(
    user_id: int,
    payload: RoleUpdateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.ADMIN)),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.role = payload.role
    db.commit()
    db.refresh(target)
    _audit("user.role_updated", actor=actor, metadata={"target_user_id": user_id, "new_role": payload.role.value})
    return target


@app.post("/api/training-modules")
def create_module(
    payload: TrainingModuleCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.MANAGER, UserRole.TRAINER, UserRole.ADMIN)),
):
    if payload.prerequisite_id is not None:
        prerequisite = db.query(TrainingModule).filter(TrainingModule.id == payload.prerequisite_id).first()
        if not prerequisite:
            raise HTTPException(status_code=404, detail="Prerequisite module not found")
    module = TrainingModule(
        title=payload.title,
        description=payload.description,
        created_by_id=user.id,
        prerequisite_id=payload.prerequisite_id,
    )
    db.add(module)
    db.commit()
    db.refresh(module)
    return module


@app.post("/api/tracks/chain")
def chain_modules(
    payload: TrackChainRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.MANAGER, UserRole.TRAINER, UserRole.ADMIN)),
):
    modules = db.query(TrainingModule).filter(TrainingModule.id.in_(payload.module_ids)).all()
    if len(modules) != len(payload.module_ids):
        raise HTTPException(status_code=404, detail="One or more modules not found")
    for i, module_id in enumerate(payload.module_ids):
        module = next(m for m in modules if m.id == module_id)
        module.prerequisite_id = payload.module_ids[i - 1] if i > 0 else None
    db.commit()
    return {"message": "Track chained successfully"}


@app.post("/api/schedules")
def create_schedule(
    payload: ScheduleCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.MANAGER, UserRole.TRAINER, UserRole.ADMIN)),
):
    schedule = Schedule(**payload.model_dump())
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


@app.post("/api/schedules/{schedule_id}/rsvp")
def rsvp_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    _validate_prerequisite(db, user.id, schedule.module_id)

    existing = db.query(ScheduleRSVP).filter(ScheduleRSVP.schedule_id == schedule_id).count()
    if existing >= schedule.max_capacity:
        raise HTTPException(status_code=400, detail="Schedule at capacity")

    already = (
        db.query(ScheduleRSVP)
        .filter(ScheduleRSVP.schedule_id == schedule_id, ScheduleRSVP.user_id == user.id)
        .first()
    )
    if already:
        return {"message": "Already RSVP'd"}

    db.add(ScheduleRSVP(schedule_id=schedule_id, user_id=user.id))
    db.commit()
    return {"message": "RSVP successful"}


@app.get("/api/schedules/{schedule_id}/calendar", response_class=PlainTextResponse)
def schedule_ics(schedule_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    module = db.query(TrainingModule).filter(TrainingModule.id == schedule.module_id).first()
    content = "\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "BEGIN:VEVENT",
            f"UID:silo-schedule-{schedule.id}",
            f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART:{schedule.start_time.strftime('%Y%m%dT%H%M%SZ')}",
            f"DTEND:{schedule.end_time.strftime('%Y%m%dT%H%M%SZ')}",
            f"SUMMARY:{module.title if module else 'Training Session'}",
            "END:VEVENT",
            "END:VCALENDAR",
        ]
    )
    return content


@app.post("/api/enrollments")
def enroll(
    payload: EnrollmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _validate_prerequisite(db, user.id, payload.module_id)
    existing = db.query(Enrollment).filter(Enrollment.user_id == user.id, Enrollment.module_id == payload.module_id).first()
    if existing:
        return existing
    enrollment = Enrollment(user_id=user.id, module_id=payload.module_id)
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment


@app.patch("/api/enrollments/{enrollment_id}/status")
def update_enrollment_status(
    enrollment_id: int,
    payload: EnrollmentStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    enrollment = db.query(Enrollment).filter(Enrollment.id == enrollment_id, Enrollment.user_id == user.id).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    if payload.status == EnrollmentStatus.PENDING_VERIFICATION:
        _validate_prerequisite(db, user.id, enrollment.module_id)
    enrollment.status = payload.status
    if payload.status == EnrollmentStatus.COMPLETED:
        enrollment.completion_date = datetime.utcnow()
    db.commit()
    db.refresh(enrollment)
    return enrollment


@app.post("/api/skills")
def add_skill(payload: SkillCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    skill = SkillsInventory(user_id=user.id, is_verified=False, **payload.model_dump())
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return skill


@app.get("/api/skills/pending-verification")
def pending_skills(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.MANAGER, UserRole.TRAINER, UserRole.ADMIN)),
):
    return db.query(SkillsInventory).filter(SkillsInventory.is_verified.is_(False)).all()


@app.post("/api/skills/{skill_id}/verify")
def verify_skill(
    skill_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.MANAGER, UserRole.TRAINER, UserRole.ADMIN)),
):
    skill = db.query(SkillsInventory).filter(SkillsInventory.id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    skill.is_verified = True
    skill.verified_by_id = user.id
    db.commit()
    db.refresh(skill)
    _audit("skill.verified", actor=user, metadata={"skill_id": skill.id, "owner_user_id": skill.user_id})
    return skill


@app.post("/api/documentation")
def create_doc(payload: DocumentationCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = Documentation(author_id=user.id, **payload.model_dump())
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@app.get("/api/documentation")
def list_docs(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Documentation).all()


@app.get("/api/documentation/{doc_id}")
def get_doc(doc_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    doc = db.query(Documentation).filter(Documentation.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@app.post("/api/documentation/{doc_id}/flag-outdated")
def flag_outdated(doc_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    doc = db.query(Documentation).filter(Documentation.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.needs_review_flag = True
    db.commit()
    db.refresh(doc)
    return doc


@app.get("/api/search")
def search(q: str = Query(..., min_length=1), db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    query = f"%{q}%"
    modules = db.query(TrainingModule).filter(TrainingModule.title.ilike(query)).all()
    skills = db.query(SkillsInventory).filter(SkillsInventory.skill_name.ilike(query)).all()
    docs = db.query(Documentation).filter(Documentation.content_markdown.ilike(query)).all()
    return {
        "training_modules": [{"id": m.id, "title": m.title} for m in modules],
        "skills": [{"id": s.id, "skill_name": s.skill_name} for s in skills],
        "documentation": [{"id": d.id, "title": d.title} for d in docs],
    }


@app.get("/api/dashboards/employee")
def employee_dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    total = db.query(Enrollment).filter(Enrollment.user_id == user.id).count()
    completed = (
        db.query(Enrollment)
        .filter(Enrollment.user_id == user.id, Enrollment.status == EnrollmentStatus.COMPLETED)
        .count()
    )
    progress = round((completed / total) * 100, 2) if total else 0

    upcoming = (
        db.query(Schedule)
        .join(ScheduleRSVP, ScheduleRSVP.schedule_id == Schedule.id)
        .filter(ScheduleRSVP.user_id == user.id, Schedule.start_time >= datetime.utcnow())
        .order_by(Schedule.start_time.asc())
        .all()
    )
    in_progress = (
        db.query(Enrollment)
        .filter(Enrollment.user_id == user.id, Enrollment.status == EnrollmentStatus.IN_PROGRESS)
        .all()
    )

    return {
        "progress_percent": progress,
        "up_next_schedules": [
            {"schedule_id": s.id, "module_id": s.module_id, "start_time": s.start_time} for s in upcoming
        ],
        "in_progress_tasks": [{"enrollment_id": e.id, "module_id": e.module_id} for e in in_progress],
    }


@app.get("/api/dashboards/manager")
def manager_dashboard(
    db: Session = Depends(get_db),
    manager: User = Depends(require_roles(UserRole.MANAGER, UserRole.ADMIN)),
):
    team = db.query(User).filter(User.manager_id == manager.id).all()
    core_modules = db.query(TrainingModule).all()

    matrix = []
    for member in team:
        row = {"user_id": member.id, "name": member.name, "statuses": {}}
        for module in core_modules:
            enrollment = (
                db.query(Enrollment)
                .filter(Enrollment.user_id == member.id, Enrollment.module_id == module.id)
                .first()
            )
            row["statuses"][module.id] = enrollment.status.value if enrollment else EnrollmentStatus.NOT_STARTED.value
        matrix.append(row)

    velocity_days = []
    for member in team:
        assigned = db.query(Enrollment).filter(Enrollment.user_id == member.id).all()
        if assigned and all(e.status == EnrollmentStatus.COMPLETED and e.completion_date for e in assigned):
            completion = max(e.completion_date for e in assigned if e.completion_date)
            velocity_days.append((completion - member.created_at).days)

    return {
        "team_readiness_matrix": matrix,
        "core_modules": [{"id": m.id, "title": m.title} for m in core_modules],
        "onboarding_velocity_avg_days": round(sum(velocity_days) / len(velocity_days), 2) if velocity_days else None,
    }


@app.post("/api/tech-stacks")
def create_tech_stack(
    payload: TechStackTemplateCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.MANAGER, UserRole.ADMIN)),
):
    template = TechStackTemplate(created_by_manager_id=user.id, **payload.model_dump())
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@app.post("/api/tech-stacks/{template_id}/skills")
def add_tech_stack_skill(
    template_id: int,
    payload: TechStackSkillCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.MANAGER, UserRole.ADMIN)),
):
    template = db.query(TechStackTemplate).filter(TechStackTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    skill = TechStackSkill(template_id=template_id, **payload.model_dump())
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return skill


@app.post("/api/tech-stacks/{template_id}/assign")
def assign_tech_stack(
    template_id: int,
    payload: TechStackAssignRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.MANAGER, UserRole.ADMIN)),
):
    template = db.query(TechStackTemplate).filter(TechStackTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    assignment = UserTechStack(user_id=payload.user_id, template_id=template_id, assigned_by_id=user.id)
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    _audit(
        "tech_stack.assigned",
        actor=user,
        metadata={"template_id": template_id, "target_user_id": payload.user_id},
    )
    return assignment


@app.get("/api/users/{user_id}/gap-analysis")
def gap_analysis(user_id: int, db: Session = Depends(get_db), requester: User = Depends(get_current_user)):
    if requester.role not in {UserRole.ADMIN, UserRole.MANAGER, UserRole.TRAINER} and requester.id != user_id:
        raise HTTPException(status_code=403, detail="You may only view your own gap analysis")

    assignments = db.query(UserTechStack).filter(UserTechStack.user_id == user_id).all()
    if not assignments:
        return {"user_id": user_id, "assigned_templates": [], "analysis": []}

    user_skills = db.query(SkillsInventory).filter(SkillsInventory.user_id == user_id).all()
    skill_map = {}
    for skill in user_skills:
        best = skill_map.get(skill.skill_name)
        if not best or skill.proficiency_level > best["proficiency_level"]:
            skill_map[skill.skill_name] = {
                "proficiency_level": skill.proficiency_level,
                "is_verified": skill.is_verified,
            }

    analysis = []
    templates = []
    for assignment in assignments:
        template = db.query(TechStackTemplate).filter(TechStackTemplate.id == assignment.template_id).first()
        if not template:
            continue
        templates.append({"id": template.id, "name": template.name})
        required_skills = db.query(TechStackSkill).filter(TechStackSkill.template_id == template.id).all()

        met, below, missing = [], [], []
        for req in required_skills:
            current = skill_map.get(req.skill_name)
            if not current:
                missing.append(
                    {
                        "skill_name": req.skill_name,
                        "required_level": req.min_proficiency_required,
                    }
                )
                continue
            if current["proficiency_level"] >= req.min_proficiency_required:
                met.append(
                    {
                        "skill_name": req.skill_name,
                        "actual_level": current["proficiency_level"],
                        "required_level": req.min_proficiency_required,
                    }
                )
            else:
                below.append(
                    {
                        "skill_name": req.skill_name,
                        "actual_level": current["proficiency_level"],
                        "required_level": req.min_proficiency_required,
                        "gap": req.min_proficiency_required - current["proficiency_level"],
                    }
                )

        analysis.append(
            {
                "template_id": template.id,
                "template_name": template.name,
                "meets_requirement": met,
                "below_requirement": below,
                "missing_skills": missing,
            }
        )

    return {"user_id": user_id, "assigned_templates": templates, "analysis": analysis}


@app.get("/api/users")
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.MANAGER, UserRole.TRAINER, UserRole.ADMIN)),
):
    users = db.query(User).order_by(User.id.asc()).all()
    return [{"id": u.id, "name": u.name, "email": u.email, "role": u.role.value} for u in users]


@app.get("/api/tech-stacks")
def list_tech_stacks(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    templates = db.query(TechStackTemplate).order_by(TechStackTemplate.id.asc()).all()
    return [{"id": t.id, "name": t.name, "description": t.description} for t in templates]


@app.get("/api/seed")
def seed_admin(
    db: Session = Depends(get_db),
    requester: User = Depends(require_roles(UserRole.ADMIN)),
):
    if not settings.enable_seed_endpoint:
        raise HTTPException(status_code=404, detail="Not found")
    admin = db.query(User).filter(User.email == f"admin@{COMPANY_DOMAIN}").first()
    if not admin:
        admin = User(email=f"admin@{COMPANY_DOMAIN}", name="Admin", role=UserRole.ADMIN)
        db.add(admin)
        db.commit()
        db.refresh(admin)
    trainers = db.query(User).filter(User.role == UserRole.TRAINER).count()
    _audit("seed.invoked", actor=requester, metadata={"admin_id": admin.id, "trainer_count": trainers})
    return {"admin_id": admin.id, "trainer_count": trainers}
