# backend/app/services/tenant_service.py

import os
import uuid
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.models.control_models import Tenant, TenantDatabase
from app.models.tenant_models import TenantBase, User
from app.core.security import get_password_hash
from dotenv import load_dotenv

load_dotenv()

DB_HOST = "localhost"
DB_PORT = 5432
DB_USER = "grc_app"
DB_PASSWORD = os.getenv("TENANT_DB_PASSWORD", "your_strong_password")


def create_slug(name: str) -> str:
    """Convert tenant name to a URL-safe slug."""
    return name.lower().strip().replace(" ", "_").replace("-", "_")


def provision_tenant(
    control_db: Session,
    tenant_name: str,
    country: str,
    admin_email: str,
    admin_password: str
) -> dict:
    """
    Full tenant provisioning flow:
    1. Create tenant row in control_db
    2. Clone tenant_template database
    3. Store connection info in control_db
    4. Seed admin user into new tenant DB
    5. Activate tenant
    """

    tenant_id = uuid.uuid4()
    db_name = f"tenant_{str(tenant_id).replace('-', '_')}"
    slug = create_slug(tenant_name)

    # ── 1. Create tenant row ──────────────────────────────
    tenant = Tenant(
        id=tenant_id,
        name=tenant_name,
        slug=slug,
        default_country=country,
        status="PROVISIONING"
    )
    control_db.add(tenant)
    control_db.flush()  # get the ID without committing yet

    # ── 2. Clone tenant_template into new database ────────
    # Must use postgres superuser URL for CREATE DATABASE
    postgres_url = os.getenv("POSTGRES_SUPERUSER_URL",
        f"postgresql://postgres:{os.getenv('POSTGRES_PASSWORD')}@localhost:5432/postgres"
    )
    admin_engine = create_engine(
        postgres_url,
        isolation_level="AUTOCOMMIT"  # Required for CREATE DATABASE
    )
    with admin_engine.connect() as conn:
        conn.execute(text(
            f"CREATE DATABASE {db_name} TEMPLATE tenant_template"
        ))
    admin_engine.dispose()

    # ── 3. Store connection info in control_db ────────────
    tenant_db_url = (
        f"postgresql://{DB_USER}:{DB_PASSWORD}"
        f"@{DB_HOST}:{DB_PORT}/{db_name}"
    )
    tenant_db_record = TenantDatabase(
        tenant_id=tenant_id,
        db_name=db_name,
        db_host=DB_HOST,
        db_port=DB_PORT,
        db_user=DB_USER,
        db_password_enc=DB_PASSWORD  # encrypt this in production
    )
    control_db.add(tenant_db_record)

    # ── 4. Seed admin user in new tenant DB ───────────────
    tenant_engine = create_engine(tenant_db_url)
    TenantSessionLocal = __import__(
        'sqlalchemy.orm', fromlist=['sessionmaker']
    ).sessionmaker(bind=tenant_engine)
    tenant_session = TenantSessionLocal()

    admin_user = User(
        email=admin_email,
        hashed_password=get_password_hash(admin_password),
        role="ADMIN",
        is_active=True
    )
    tenant_session.add(admin_user)
    tenant_session.commit()
    admin_user_id = str(admin_user.id)
    tenant_session.close()
    tenant_engine.dispose()

    # ── 5. Activate tenant ────────────────────────────────
    tenant.status = "ACTIVE"
    control_db.commit()

    return {
        "tenant_id": str(tenant_id),
        "db_name": db_name,
        "db_url": tenant_db_url,
        "admin_user_id": admin_user_id
    }


def get_tenant_db_url(control_db: Session, tenant_id: str) -> str:
    """Look up a tenant's database URL from control_db."""
    record = control_db.query(TenantDatabase).filter(
        TenantDatabase.tenant_id == tenant_id
    ).first()
    if not record:
        return None
    return (
        f"postgresql://{record.db_user}:{record.db_password_enc}"
        f"@{record.db_host}:{record.db_port}/{record.db_name}"
    )
