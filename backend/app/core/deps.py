"""
Reusable FastAPI dependencies.

`get_current_user` is the single choke point through which every protected
request passes. It decodes the JWT and loads the user. `require_roles` builds
on it for RBAC. `get_current_user` is also what guarantees tenant isolation:
every downstream query MUST filter by `current_user.company_id`, never trust
a company_id passed in the request body/query for a non-super-admin.
"""
import uuid
from typing import Iterable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models.company import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        raise credentials_exception

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
    if user is None or not user.is_active:
        raise credentials_exception

    return user


def require_roles(*allowed_roles: Iterable[UserRole]):
    """Usage: Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN))"""

    def _checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return current_user

    return _checker


def get_tenant_id(current_user: User = Depends(get_current_user)) -> uuid.UUID:
    """Every tenant-scoped route depends on this instead of trusting client input."""
    if current_user.role == UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Super admin must specify a company_id explicitly via admin endpoints",
        )
    if current_user.company_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User has no associated company")
    return current_user.company_id
