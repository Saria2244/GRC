# backend/app/core/enums.py

from enum import Enum


class UserRole(str, Enum):
    """
    All valid user roles in the system.
    Inheriting from str means it serializes as a plain string
    in JSON responses and database values automatically.
    """
    ADMIN        = "ADMIN"
    AUDITOR      = "AUDITOR"
    RISK_MANAGER = "RISK_MANAGER"
    EMPLOYEE     = "EMPLOYEE"


class TenantStatus(str, Enum):
    PROVISIONING = "PROVISIONING"
    ACTIVE       = "ACTIVE"
    DISABLED     = "DISABLED"


class JobType(str, Enum):
    INGEST_POLICY   = "INGEST_POLICY"
    GAP_ANALYSIS    = "GAP_ANALYSIS"
    CHECKLIST_GEN   = "CHECKLIST_GEN"
    RISK_SUGGESTION = "RISK_SUGGESTION"


class JobStatus(str, Enum):
    QUEUED    = "QUEUED"
    RUNNING   = "RUNNING"
    SUCCESS   = "SUCCESS"
    FAILED    = "FAILED"
    CANCELLED = "CANCELLED"


class DocumentStatus(str, Enum):
    UPLOADED        = "UPLOADED"
    TEXT_EXTRACTED  = "TEXT_EXTRACTED"
    CHUNKED         = "CHUNKED"
    EMBEDDED        = "EMBEDDED"
    READY           = "READY"
    FAILED          = "FAILED"


class RiskSeverity(str, Enum):
    LOW      = "LOW"
    MEDIUM   = "MEDIUM"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"


class RiskStatus(str, Enum):
    OPEN        = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED    = "RESOLVED"
    CLOSED      = "CLOSED"


class AuditStatus(str, Enum):
    PENDING     = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED   = "COMPLETED"

class AuditType(str, Enum):
    GOVERNANCE              = "Governance and Accountability"
    FAIRNESS                = "Fairness/Non-Discrimination and Ethics"
    TRANSPARENCY            = "Transparency and Explainability"
    DATA_QUALITY            = "Data Quality, Privacy and Security"
    MONITORING              = "Continuous Monitoring and Review"
    HUMAN_OVERSIGHT         = "Human Oversight and Consumer Protection"
    INTEGRATION             = "Integration with Existing Frameworks"
    OUTSOURCING             = "Outsourcing and Third-Party Risk"
    ETHICAL_COLLABORATION   = "Ethical Collaboration and Innovation"
# ── Permission map — what each role can access ─────────────
#
# This is the single source of truth for permissions.
# Every route dependency reads from here.

ROLE_PERMISSIONS = {
    UserRole.ADMIN: {
        "can_manage_users":       True,
        "can_upload_standards":   True,
        "can_create_audits":      True,
        "can_submit_audits":      True,
        "can_view_all_risks":     True,
        "can_close_risks":        True,
        "can_upload_evidence":    True,
        "can_approve_reports":    True,
        "can_view_audit_log":     True,
        "can_manage_settings":    True,
        "data_scope":             "FULL",
    },
    UserRole.AUDITOR: {
        "can_manage_users":       False,
        "can_upload_standards":   False,
        "can_create_audits":      True,
        "can_submit_audits":      True,
        "can_view_all_risks":     True,
        "can_close_risks":        True,
        "can_upload_evidence":    True,
        "can_approve_reports":    True,
        "can_view_audit_log":     True,
        "can_manage_settings":    False,
        "data_scope":             "FULL",
    },
    UserRole.RISK_MANAGER: {
        "can_manage_users":       False,
        "can_upload_standards":   False,
        "can_create_audits":      False,
        "can_submit_audits":      False,
        "can_view_all_risks":     True,
        "can_close_risks":        False,
        "can_upload_evidence":    True,
        "can_approve_reports":    False,
        "can_view_audit_log":     False,
        "can_manage_settings":    False,
        "data_scope":             "FULL",
    },
    UserRole.EMPLOYEE: {
        "can_manage_users":       False,
        "can_upload_standards":   False,
        "can_create_audits":      False,
        "can_submit_audits":      False,
        "can_view_all_risks":     False,
        "can_close_risks":        False,
        "can_upload_evidence":    False,
        "can_approve_reports":    False,
        "can_view_audit_log":     False,
        "can_manage_settings":    False,
        "data_scope":             "SELF_ONLY",
    },
}


def has_permission(role: UserRole, permission: str) -> bool:
    """
    Check if a role has a specific permission.

    Usage:
        if has_permission(current_user.role, "can_create_audits"):
            ...
    """
    return ROLE_PERMISSIONS.get(role, {}).get(permission, False)