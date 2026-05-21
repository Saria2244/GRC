# backend/app/core/dependencies.py

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_control_db, get_tenant_db
from app.core.security import decode_token
from app.core.enums import UserRole, has_permission
from app.services.tenant_service import get_tenant_db_url
from app.models.tenant_models import User

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    control_db: Session = Depends(get_control_db)
):
    token = credentials.credentials
    payload = decode_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    tenant_id = payload.get("tenant_id")
    user_id   = payload.get("user_id")

    if not tenant_id or not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token"
        )

    db_url = get_tenant_db_url(control_db, tenant_id)
    if not db_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )

    tenant_db = get_tenant_db(db_url)
    user = tenant_db.query(User).filter(User.id == user_id).first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    user.tenant_id     = tenant_id
    user.tenant_db_url = db_url
    return user


def require_roles(*roles: UserRole):
    """
    Restrict a route to specific roles.
    Usage: Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR))
    """
    def checker(current_user=Depends(get_current_user)):
        if current_user.role not in [r.value for r in roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required: {[r.value for r in roles]}"
            )
        return current_user
    return checker


def require_permission(permission: str):
    """
    Restrict a route by permission name instead of role name.
    Usage: Depends(require_permission("can_create_audits"))

    This is more flexible than require_roles because you check
    what a role CAN DO, not what the role IS CALLED.
    """
    def checker(current_user=Depends(get_current_user)):
        if not has_permission(current_user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Your role does not have '{permission}' permission"
            )
        return current_user
    return checker


# ── Named shortcuts — import these directly in your routes ─

def admin_only(
    user=Depends(require_roles(UserRole.ADMIN))
):
    return user


def auditor_or_admin(
    user=Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR))
):
    return user


def risk_manager_or_above(
    user=Depends(require_roles(
        UserRole.ADMIN, UserRole.AUDITOR, UserRole.RISK_MANAGER
    ))
):
    return user


def any_authenticated_user(user=Depends(get_current_user)):
    return user