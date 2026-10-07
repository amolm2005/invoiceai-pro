import uuid
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.core.config import settings
from app.models.company import Company, User, UserRole, RefreshSession
from app.schemas.auth import CompanySignupRequest, LoginRequest


def signup_company(db: Session, payload: CompanySignupRequest) -> User:
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    company = Company(name=payload.company_name, email=payload.email)
    db.add(company)
    db.flush()  # get company.id without committing yet

    admin_user = User(
        company_id=company.id,
        full_name=payload.admin_full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.COMPANY_ADMIN,
        is_email_verified=False,
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    return admin_user


def authenticate_user(db: Session, payload: LoginRequest) -> User:
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    user.last_login_at = datetime.utcnow()
    db.commit()
    return user


def issue_tokens(db: Session, user: User, remember_me: bool, device_info: str = "", ip_address: str = "") -> dict:
    session_id = str(uuid.uuid4())
    days = settings.REFRESH_TOKEN_EXPIRE_DAYS * (3 if remember_me else 1)

    session = RefreshSession(
        id=uuid.UUID(session_id),
        user_id=user.id,
        device_info=device_info,
        ip_address=ip_address,
        expires_at=datetime.utcnow() + timedelta(days=days),
    )
    db.add(session)
    db.commit()

    access_token = create_access_token(str(user.id), str(user.company_id) if user.company_id else None, user.role.value)
    refresh_token = create_refresh_token(str(user.id), session_id)
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


def refresh_access_token(db: Session, refresh_token: str) -> dict:
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    session_id = payload.get("session_id")
    session = db.query(RefreshSession).filter(RefreshSession.id == uuid.UUID(session_id)).first()
    if not session or session.is_revoked or session.expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or revoked")

    user = db.query(User).filter(User.id == uuid.UUID(payload["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    access_token = create_access_token(str(user.id), str(user.company_id) if user.company_id else None, user.role.value)
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


def logout_all_devices(db: Session, user: User) -> None:
    db.query(RefreshSession).filter(RefreshSession.user_id == user.id).update({"is_revoked": True})
    db.commit()
