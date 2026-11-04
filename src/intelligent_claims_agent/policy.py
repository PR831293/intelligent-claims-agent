from __future__ import annotations

import re
from typing import Iterable

from .models import ClaimInput, Document

INJECTION_PATTERNS = [
    r"ignore\s+previous\s+instructions",
    r"system\s+prompt",
    r"override\s+policy",
    r"execute\s+this\s+command",
]

HIGH_RISK_KEYWORDS = {
    "fraud",
    "forged",
    "counterfeit",
    "stolen",
    "identity mismatch",
}

REQUIRED_DOCUMENTS_BY_TYPE: dict[str, set[str]] = {
    "medical": {"claim_form", "invoice", "doctor_note"},
    "dental": {"claim_form", "invoice"},
    "pharmacy": {"claim_form", "prescription", "invoice"},
}

PII_PATTERNS = {
    "email": re.compile(r"\b[\w.-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    "phone": re.compile(r"\b(?:\+?\d{1,3}[\s.-]?)?(?:\d{3}[\s.-]?){2}\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
}


def detect_instruction_injection(documents: Iterable[Document]) -> list[str]:
    flags: list[str] = []
    for doc in documents:
        text = doc.content.lower()
        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, text):
                flags.append(f"{doc.name}: matched pattern '{pattern}'")
    return flags


def redact_pii(text: str) -> str:
    redacted = text
    for pii_type, pattern in PII_PATTERNS.items():
        redacted = pattern.sub(f"[{pii_type.upper()}_REDACTED]", redacted)
    return redacted


def missing_required_documents(claim: ClaimInput) -> list[str]:
    required = REQUIRED_DOCUMENTS_BY_TYPE.get(claim.claim_type.lower(), {"claim_form", "invoice"})
    provided = {doc.name.strip().lower() for doc in claim.documents}
    missing = sorted(required - provided)
    return missing


def validate_claim_basics(claim: ClaimInput) -> list[str]:
    errors: list[str] = []
    if not claim.claim_id.strip():
        errors.append("claim_id is required")
    if not claim.member_id.strip():
        errors.append("member_id is required")
    if claim.amount <= 0:
        errors.append("amount must be greater than zero")
    if not claim.documents:
        errors.append("at least one document is required")
    return errors


def detect_high_risk_content(documents: Iterable[Document]) -> list[str]:
    flags: list[str] = []
    for doc in documents:
        text = doc.content.lower()
        for keyword in HIGH_RISK_KEYWORDS:
            if keyword in text:
                flags.append(f"{doc.name}: contains high-risk keyword '{keyword}'")
    return flags
