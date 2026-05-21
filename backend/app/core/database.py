# backend/app/core/database.py

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

# ─── Separate Base for each database ──────────────────────
# IMPORTANT: Each database needs its own Base so SQLAlchemy
# knows which tables belong to which database.
ControlBase = declarative_base()
StandardsBase = declarative_base()

# ─── Three database engines ───────────────────────────────
control_engine = create_engine(
    os.getenv("CONTROL_DB_URL"),
    pool_pre_ping=True,
    echo=False
)

standards_engine = create_engine(
    os.getenv("STANDARDS_DB_URL"),
    pool_pre_ping=True,
    echo=False
)

# ─── Session factories ────────────────────────────────────
ControlSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=control_engine
)

StandardsSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=standards_engine
)

# ─── Dependency functions (used in FastAPI routes) ────────
def get_control_db():
    db = ControlSessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_standards_db():
    db = StandardsSessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_tenant_db(db_url: str):
    """
    Dynamically connect to a specific tenant database.
    Called with the tenant's connection URL from control_db.
    """
    engine = create_engine(db_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    return db

def test_all_connections():
    """Run this once to verify all three DBs are reachable."""
    results = {}
    for name, engine in [
        ("control_db", control_engine),
        ("standards_db", standards_engine),
    ]:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            results[name] = "OK"
        except Exception as e:
            results[name] = f"FAILED: {e}"
    return results