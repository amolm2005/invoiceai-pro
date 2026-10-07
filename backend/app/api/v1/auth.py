from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.schemas.auth import (
    CompanySignupRequest, LoginRequest, TokenResponse, RefreshRequest, UserOut
)
from app.services import auth_service
from app.models.company import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=UserOut, status_code=201)
def signup(payload: CompanySignupRequest, db: Session = Depends(get_db)):
    """Creates a new Company (tenant) plus its first Company Admin user."""
    user = auth_service.signup_company(db, payload)
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = auth_service.authenticate_user(db, payload)
    tokens = auth_service.issue_tokens(
        db, user,
        remember_me=payload.remember_me,
        device_info=request.headers.get("user-agent", ""),
        ip_address=request.client.host if request.client else "",
    )
    return tokens


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    return auth_service.refresh_access_token(db, payload.refresh_token)


@router.post("/logout-all", status_code=204)
def logout_all(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    auth_service.logout_all_devices(db, current_user)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
