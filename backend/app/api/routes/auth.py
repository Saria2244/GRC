# backend/app/api/routes/auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_control_db, get_tenant_db
from app.core.security import verify_password, create_access_token
from app.core.dependencies import get_current_user
from app.schemas.auth_schemas import (
    SignupRequest, LoginRequest, TokenResponse,
    UserResponse, CreateUserRequest
)
from app.services.tenant_service import provision_tenant, get_tenant_db_url
from app.models.control_models import Tenant
from app.models.tenant_models import User
from app.core.security import get_password_hash
import datetime

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=TokenResponse)
def signup(
    request: SignupRequest,
    control_db: Session = Depends(get_control_db)
):
    """
    Register a new organization. Creates a tenant + provisions
    a dedicated database + seeds the first Admin user.
    """
    # Check slug is not already taken
    from app.services.tenant_service import create_slug
    slug = create_slug(request.name)
    existing = control_db.query(Tenant).filter(
        Tenant.slug == slug
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="An organization with this name already exists"
        )

    # Provision tenant (creates DB, seeds admin user)
    result = provision_tenant(
        control_db=control_db,
        tenant_name=request.name,
        country=request.country,
        admin_email=request.email,
        admin_password=request.password
    )

    # Issue JWT token
    token = create_access_token({
        "user_id": result["admin_user_id"],
        "tenant_id": result["tenant_id"],
        "role": "ADMIN",
        "email": request.email
    })

    return TokenResponse(
        access_token=token,
        user_id=result["admin_user_id"],
        email=request.email,
        role="ADMIN",
        tenant_id=result["tenant_id"]
    )


@router.post("/login", response_model=TokenResponse)
def login(
    request: LoginRequest,
    control_db: Session = Depends(get_control_db)
):
    """
    Login with email + password.
    Searches all active tenants to find the user.
    """
    from app.models.control_models import TenantDatabase

    # Find which tenant this email belongs to
    all_tenant_dbs = control_db.query(TenantDatabase).join(
        Tenant, Tenant.id == TenantDatabase.tenant_id
    ).filter(Tenant.status == "ACTIVE").all()

    found_user = None
    found_tenant_id = None

    for tenant_db_record in all_tenant_dbs:
        db_url = (
            f"postgresql://{tenant_db_record.db_user}"
            f":{tenant_db_record.db_password_enc}"
            f"@{tenant_db_record.db_host}"
            f":{tenant_db_record.db_port}"
            f"/{tenant_db_record.db_name}"
        )
        try:
            tenant_db = get_tenant_db(db_url)
            user = tenant_db.query(User).filter(
                User.email == request.email
            ).first()
            if user:
                found_user = user
                found_tenant_id = str(tenant_db_record.tenant_id)
                # Update last login
                user.last_login_at = datetime.datetime.utcnow()
                tenant_db.commit()
                break
        except Exception:
            continue

    if not found_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not verify_password(request.password, found_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not found_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )

    token = create_access_token({
        "user_id": str(found_user.id),
        "tenant_id": found_tenant_id,
        "role": found_user.role,
        "email": found_user.email
    })

    return TokenResponse(
        access_token=token,
        user_id=str(found_user.id),
        email=found_user.email,
        role=found_user.role,
        tenant_id=found_tenant_id
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user=Depends(get_current_user)):
    """Return the currently logged-in user's profile."""
    return current_user


@router.post("/users", response_model=UserResponse)
def create_user(
    request: CreateUserRequest,
    current_user=Depends(get_current_user)
):
    """
    Admin only: create additional users within the same tenant.
    """
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin access required")

    valid_roles = ["ADMIN", "AUDITOR", "RISK_MANAGER", "EMPLOYEE"]
    if request.role not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Must be one of: {valid_roles}"
        )

    tenant_db = get_tenant_db(current_user.tenant_db_url)

    # Check email not already taken in this tenant
    existing = tenant_db.query(User).filter(
        User.email == request.email
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    new_user = User(
        email=request.email,
        hashed_password=get_password_hash(request.password),
        role=request.role,
        is_active=True
    )
    tenant_db.add(new_user)
    tenant_db.commit()
    tenant_db.refresh(new_user)
    return new_user