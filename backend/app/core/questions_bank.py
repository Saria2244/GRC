# backend/app/core/questions_bank.py

from app.core.enums import AuditType

# ── The 10 standard compliance questions ──────────────────
# These are shown for every audit type.
# You can customize per type later by adding
# type-specific lists below.

STANDARD_QUESTIONS = [
    {
        "question_index": 1,
        "question_text": (
            "Does the bank have a documented AI/ML governance framework "
            "approved by senior management and/or the Board, with clearly "
            "assigned accountability for AI model selection, development, "
            "deployment, monitoring, and risk management?"
        ),
        "question_type": "OPEN_TEXT",
        "accepted_formats": ["TEXT", "IMAGE", "BOTH"],
        "policy_reference": "Governance and Accountability"
    },
    {
        "question_index": 2,
        "question_text": (
            "How does the bank ensure regular reporting to senior management "
            "and the Board on AI/ML performance, risks, incidents, and "
            "compliance issues?"
        ),
        "question_type": "OPEN_TEXT",
        "accepted_formats": ["TEXT", "IMAGE", "BOTH"],
        "policy_reference": "Governance and Accountability"
    },
    {
        "question_index": 3,
        "question_text": (
            "What controls does the bank use to ensure AI/ML systems do not "
            "create discriminatory, manipulative, or unfair outcomes for "
            "customers, and how often are bias tests performed?"
        ),
        "question_type": "OPEN_TEXT",
        "accepted_formats": ["TEXT", "IMAGE", "BOTH"],
        "policy_reference": "Fairness/Non-Discrimination and Ethics"
    },
    {
        "question_index": 4,
        "question_text": (
            "How does the bank inform customers when AI is being used, "
            "especially for high-impact decisions, and how does it explain "
            "AI-supported decisions in understandable language?"
        ),
        "question_type": "OPEN_TEXT",
        "accepted_formats": ["TEXT", "IMAGE", "BOTH"],
        "policy_reference": "Transparency and Explainability"
    },
    {
        "question_index": 5,
        "question_text": (
            "Describe in detail how the bank provides customers the ability "
            "to request human review, challenge AI-generated decisions, "
            "correct inaccurate input data, or opt out of AI processing "
            "where appropriate. Provide supporting documentation or evidence."
        ),
        "question_type": "OPEN_TEXT",
        "accepted_formats": ["TEXT", "IMAGE", "BOTH"],
        "policy_reference": "Human Oversight and Consumer Protection"
    },
    {
        "question_index": 6,
        "question_text": (
            "What controls ensure that data used in AI/ML models is accurate, "
            "relevant, up to date, lawfully processed, traceable, and "
            "protected from unauthorized access or misuse?"
        ),
        "question_type": "OPEN_TEXT",
        "accepted_formats": ["TEXT", "IMAGE", "BOTH"],
        "policy_reference": "Data Quality, Privacy and Security"
    },
    {
        "question_index": 7,
        "question_text": (
            "How does the bank continuously monitor AI/ML systems after "
            "deployment, test updates before implementation, detect unintended "
            "outcomes, and stop or suspend models when necessary?"
        ),
        "question_type": "OPEN_TEXT",
        "accepted_formats": ["TEXT", "IMAGE", "BOTH"],
        "policy_reference": "Continuous Monitoring and Review"
    },
    {
        "question_index": 8,
        "question_text": (
            "Which human oversight model does the bank apply for each AI use "
            "case — human-in-the-loop, human-on-the-loop, or "
            "human-out-of-the-loop — and how does it ensure the level of "
            "oversight matches customer risk? Provide examples and evidence."
        ),
        "question_type": "OPEN_TEXT",
        "accepted_formats": ["TEXT", "IMAGE", "BOTH"],
        "policy_reference": "Human Oversight and Consumer Protection"
    },
    {
        "question_index": 9,
        "question_text": (
            "Explain how AI risk is integrated into the bank's "
            "enterprise-wide risk management, conduct risk, compliance, "
            "internal audit, and control frameworks rather than managed "
            "separately. Provide policy documents or evidence."
        ),
        "question_type": "OPEN_TEXT",
        "accepted_formats": ["TEXT", "IMAGE", "BOTH"],
        "policy_reference": "Integration with Existing Frameworks"
    },
    {
        "question_index": 10,
        "question_text": (
            "Where the bank uses third-party or cloud-based AI solutions, "
            "how does it perform due diligence, document provider selection, "
            "maintain audit rights, test solutions before deployment, and "
            "ensure third-party models meet the same standards as "
            "internal models?"
        ),
        "question_type": "OPEN_TEXT",
        "accepted_formats": ["TEXT", "IMAGE", "BOTH"],
        "policy_reference": "Outsourcing and Third-Party Risk"
    },
]

def get_questions_for_audit_type(audit_type: str) -> list:
    """
    Returns the 10 questions for a given audit type.
    Currently all types return the same questions.
    Later you can add type-specific question lists here.
    """
    return STANDARD_QUESTIONS