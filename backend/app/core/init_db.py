# backend/app/core/init_db.py

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

from app.core.database import (
    ControlBase, StandardsBase,
    control_engine, standards_engine,
    test_all_connections
)
from app.models import control_models, standards_models
from app.models.tenant_models import TenantBase


def drop_tables_cascade(engine, base, db_name):
    """
    Drop all tables using CASCADE to handle foreign key dependencies.
    This is safer than SQLAlchemy's default drop_all which fails
    when foreign keys exist between tables.
    """
    with engine.connect() as conn:
        # Get all table names in the public schema
        result = conn.execute(text("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
        """))
        tables = [row[0] for row in result]

        if not tables:
            print(f"  No tables to drop in {db_name}")
            return

        # Drop all tables at once with CASCADE
        tables_str = ", ".join(tables)
        conn.execute(text(
            f"DROP TABLE IF EXISTS {tables_str} CASCADE"
        ))
        conn.commit()
        print(f"  Dropped all tables in {db_name}")


def drop_and_recreate_control_db():
    print("Dropping and recreating control_db tables...")
    drop_tables_cascade(control_engine, ControlBase, "control_db")
    ControlBase.metadata.create_all(bind=control_engine)
    print("  control_db tables created.")


def drop_and_recreate_standards_db():
    print("Dropping and recreating standards_db tables...")
    drop_tables_cascade(standards_engine, StandardsBase, "standards_db")
    StandardsBase.metadata.create_all(bind=standards_engine)
    print("  standards_db tables created.")


def drop_and_recreate_tenant_template():
    print("Dropping and recreating tenant_template tables...")
    template_engine = create_engine(
        os.getenv("TENANT_TEMPLATE_DB_URL"), echo=False
    )
    drop_tables_cascade(template_engine, TenantBase, "tenant_template")
    TenantBase.metadata.create_all(bind=template_engine)
    print("  tenant_template tables created.")


def verify_pgvector(engine, db_name):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT '[1,2,3]'::vector"))
        print(f"  pgvector OK in {db_name}")
    except Exception as e:
        print(f"  pgvector FAILED in {db_name}: {e}")


if __name__ == "__main__":
    print("\n=== GRC Vault — Database Initialization ===\n")

    print("Testing database connections...")
    results = test_all_connections()
    for db, status in results.items():
        print(f"  {db}: {status}")

    template_engine = create_engine(os.getenv("TENANT_TEMPLATE_DB_URL"))
    verify_pgvector(standards_engine, "standards_db")
    verify_pgvector(template_engine, "tenant_template")

    drop_and_recreate_control_db()
    drop_and_recreate_standards_db()
    drop_and_recreate_tenant_template()

    print("\n=== All databases initialized successfully ===\n")