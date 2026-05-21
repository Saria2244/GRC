
import os
import json
import re
# import google.generativeai as genai
from google.genai import Client
from PIL import Image
import io
from dotenv import load_dotenv

load_dotenv()

client = Client(api_key=os.getenv("GEMINI_API_KEY"))
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")


def parse_json_from_response(text: str) -> any:
    """
    Safely parse JSON from Gemini response.
    Handles cases where Gemini wraps JSON in markdown code blocks.
    """
    # Strip markdown code blocks if present
    text = text.strip()
    text = re.sub(r'^```json\s*', '', text)
    text = re.sub(r'^```\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return json.loads(text.strip())


def generate_audit_questions(
    standard_chunks: list,
    framework: str,
    country: str
) -> list:
    """
    Call Gemini to generate 10 compliance audit questions
    from the standard chunks.

    Returns a list of dicts:
    [
        {
            "question_text": "...",
            "question_type": "YES_NO" or "OPEN_TEXT",
            "policy_reference": "chunk_id or section name"
        }
    ]
    """
    # Build context from chunks
    chunks_text = "\n\n".join([
        f"[Section {i+1}]: {chunk.chunk_text[:800]}"
        for i, chunk in enumerate(standard_chunks[:8])
        # Use first 8 chunks for context
    ])

    prompt = f"""
You are a senior compliance auditor specializing in {framework} for {country}.

Based on the following official {framework} compliance standard text,
generate exactly 10 audit questions that an organization must answer
to verify their compliance.

RULES:
- Generate a mix: 5 YES_NO questions and 5 OPEN_TEXT questions
- Each question must directly relate to the standard text provided
- YES_NO questions should be about specific controls or requirements
- OPEN_TEXT questions should ask for descriptions of processes or evidence
- Keep questions clear, specific, and actionable
- Do NOT number the questions

STANDARD TEXT:
{chunks_text}

Return ONLY a valid JSON array with exactly 10 items, no extra text:
[
  {{
    "question_text": "Is multi-factor authentication enabled for all administrative accounts?",
    "question_type": "YES_NO",
    "policy_reference": "Access Control Requirements"
  }},
  {{
    "question_text": "Describe your organization's data breach notification process.",
    "question_type": "OPEN_TEXT",
    "policy_reference": "Incident Response"
  }}
]
"""

    model = genai.GenerativeModel(GEMINI_MODEL)
    response = model.generate_content(prompt)

    questions = parse_json_from_response(response.text)

    # Ensure exactly 10 questions
    if len(questions) > 10:
        questions = questions[:10]

    return questions


def analyze_text_answer(
    question_text: str,
    answer_text: str,
    standard_context: str,
    question_type: str
) -> dict:
    """
    Gemini analyzes a text or YES/NO answer against
    the standard requirement.

    Returns:
    {
        "score": 0.0-1.0,
        "feedback": "explanation",
        "is_compliant": true/false
    }
    """
    prompt = f"""
You are a compliance auditor evaluating an answer against a compliance standard.

STANDARD REQUIREMENT CONTEXT:
{standard_context[:600]}

AUDIT QUESTION:
{question_text}

USER'S ANSWER:
{answer_text}

Evaluate if this answer demonstrates compliance with the standard requirement.

Scoring guide:
- 1.0 = Fully compliant, clear evidence provided
- 0.7-0.9 = Mostly compliant, minor gaps
- 0.4-0.6 = Partially compliant, significant gaps
- 0.1-0.3 = Minimal compliance, major issues
- 0.0 = Non-compliant or no answer provided

Return ONLY valid JSON, no extra text:
{{
  "score": 0.8,
  "feedback": "The organization has MFA enabled but only for admin accounts, not all users as required.",
  "is_compliant": true
}}
"""

    model = genai.GenerativeModel(GEMINI_MODEL)
    response = model.generate_content(prompt)
    return parse_json_from_response(response.text)


def analyze_image_answer(
    question_text: str,
    image_bytes: bytes,
    standard_context: str
) -> dict:
    """
    Gemini Vision analyzes an uploaded image as compliance evidence.

    Returns:
    {
        "score": 0.0-1.0,
        "feedback": "explanation",
        "image_analysis": "what was seen in the image",
        "is_compliant": true/false
    }
    """
    prompt = f"""
You are a compliance auditor reviewing visual evidence for a compliance audit.

COMPLIANCE QUESTION:
{question_text}

STANDARD REQUIREMENT CONTEXT:
{standard_context[:400]}

The user has submitted an image as evidence for the above question.

Analyze the image and determine:
1. What does the image show?
2. Does it answer the compliance question?
3. Is this sufficient evidence of compliance?

Return ONLY valid JSON, no extra text:
{{
  "score": 0.85,
  "image_analysis": "Screenshot shows MFA configuration screen with authentication enabled for all admin users",
  "feedback": "Image clearly demonstrates MFA is configured as required by the standard.",
  "is_compliant": true
}}
"""

    try:
        image = Image.open(io.BytesIO(image_bytes))
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content([prompt, image])
        return parse_json_from_response(response.text)
    except Exception as e:
        return {
            "score": 0.0,
            "image_analysis": f"Could not analyze image: {str(e)}",
            "feedback": "Image analysis failed. Please provide a text answer.",
            "is_compliant": False
        }


def generate_risk_from_answer(
    question_text: str,
    answer_text: str,
    ai_score: float,
    standard_context: str,
    framework: str,
    country: str
) -> dict:
    """
    For low-scoring answers, Gemini generates a risk ticket
    with a specific suggested fix.

    Returns:
    {
        "title": "...",
        "severity": "HIGH/MEDIUM/LOW/CRITICAL",
        "description": "...",
        "suggested_fix": "..."
    }
    """
    prompt = f"""
You are a compliance risk analyst.

A compliance audit question was answered poorly or not at all.

FRAMEWORK: {framework} ({country})
STANDARD REQUIREMENT:
{standard_context[:500]}

AUDIT QUESTION:
{question_text}

USER ANSWER:
{answer_text or "No answer provided"}

COMPLIANCE SCORE: {ai_score:.0%}

Generate a risk ticket for this compliance gap with a specific,
actionable remediation plan.

Severity guide:
- CRITICAL: score below 20% — fundamental requirement missing
- HIGH: score 20-40% — major gap with significant risk
- MEDIUM: score 40-60% — partial compliance, notable gaps
- LOW: score 60-75% — minor gaps, mostly compliant

Return ONLY valid JSON, no extra text:
{{
  "title": "Missing Multi-Factor Authentication for Admin Accounts",
  "severity": "HIGH",
  "description": "Administrative accounts lack MFA protection as required by the standard. This creates significant unauthorized access risk.",
  "suggested_fix": "1. Enable MFA in your identity provider settings\\n2. Enforce MFA policy for all admin roles\\n3. Document the MFA configuration\\n4. Test recovery procedures"
}}
"""

    model = genai.GenerativeModel(GEMINI_MODEL)
    response = model.generate_content(prompt)
    return parse_json_from_response(response.text)

def verify_evidence(
    risk_title: str,
    risk_description: str,
    suggested_fix: str,
    evidence_text: str,
    framework: str
) -> dict:
    """
    AI verifies whether submitted evidence adequately
    addresses the identified risk.

    Returns:
    {
        "verified": true/false,
        "confidence": 0.0-1.0,
        "reasoning": "explanation",
        "recommendation": "CLOSE/NEEDS_MORE_EVIDENCE/REJECT"
    }
    """
    prompt = f"""
You are a senior compliance auditor reviewing evidence submitted
to close a risk ticket.

FRAMEWORK: {framework}

RISK TITLE:
{risk_title}

RISK DESCRIPTION:
{risk_description}

SUGGESTED FIX THAT WAS RECOMMENDED:
{suggested_fix or "No specific fix was suggested"}

EVIDENCE SUBMITTED BY THE ORGANIZATION:
{evidence_text}

Your task: Determine if this evidence adequately demonstrates
that the organization has addressed the identified risk.

Evaluation criteria:
- Does the evidence directly address the risk described?
- Is the evidence specific and verifiable?
- Does it show the suggested fix has been implemented?
- Is it sufficient to close this risk?

Recommendation guide:
- CLOSE: Evidence clearly shows the risk has been resolved
- NEEDS_MORE_EVIDENCE: Partially addressed but more proof needed
- REJECT: Evidence does not address the risk at all

Return ONLY valid JSON, no extra text:
{{
  "verified": true,
  "confidence": 0.85,
  "reasoning": "The evidence demonstrates that MFA has been enabled for all admin accounts with screenshots and policy documentation provided.",
  "recommendation": "CLOSE"
}}
"""
    response_text = call_gemini_with_retry(prompt)
    return parse_json_from_response(response_text)

