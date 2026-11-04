from __future__ import annotations

import re
from datetime import datetime

from mcp.server.fastmcp import FastMCP
from sqlalchemy import text

from .common import as_json, ensure_capstone_tables, from_json, make_engine, server_host, server_port, write_audit

mcp = FastMCP("documents-mcp", host=server_host(), port=server_port(8103))


def _classify_text(text: str) -> str:
    lower = text.lower()
    if "invoice" in lower or "billed" in lower:
        return "invoice"
    if "prescription" in lower:
        return "prescription"
    if "doctor" in lower or "treatment" in lower:
        return "doctor_note"
    return "claim_form"


def _extract_amount(text: str) -> float | None:
    matches = re.findall(r"(?:usd|\$)?\s*(\d+(?:\.\d{1,2})?)", text.lower())
    if not matches:
        return None
    try:
        return float(matches[-1])
    except ValueError:
        return None


@mcp.tool()
def list_documents(case_id: str) -> list[dict]:
    ensure_capstone_tables()
    engine = make_engine()
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT case_id, doc_id, doc_type, content, extracted_json, created_at
                FROM cap_documents
                WHERE case_id = :case_id
                ORDER BY created_at ASC
                """
            ),
            {"case_id": case_id},
        ).mappings().all()
    results: list[dict] = []
    for row in rows:
        payload = dict(row)
        payload["extracted"] = from_json(payload.pop("extracted_json"))
        results.append(payload)
    return results


@mcp.tool()
def extract_text(case_id: str, doc_id: str) -> dict:
    ensure_capstone_tables()
    engine = make_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT content
                FROM cap_documents
                WHERE case_id = :case_id AND doc_id = :doc_id
                """
            ),
            {"case_id": case_id, "doc_id": doc_id},
        ).mappings().first()
    if not row:
        return {"error": f"Unknown document {doc_id} for case {case_id}"}

    # Placeholder confidence until Docling OCR is integrated.
    return {"case_id": case_id, "doc_id": doc_id, "text": row["content"], "ocr_confidence": 0.99}


@mcp.tool()
def classify_document(case_id: str, doc_id: str) -> dict:
    extracted = extract_text(case_id, doc_id)
    if "error" in extracted:
        return extracted
    doc_type = _classify_text(extracted["text"])
    return {"case_id": case_id, "doc_id": doc_id, "doc_type": doc_type}


@mcp.tool()
def extract_fields(case_id: str, doc_id: str) -> dict:
    extracted = extract_text(case_id, doc_id)
    if "error" in extracted:
        return extracted

    text_value = extracted["text"]
    fields = {
        "amount": _extract_amount(text_value),
        "has_instruction_like_text": "ignore previous instructions" in text_value.lower(),
    }

    engine = make_engine()
    with engine.begin() as conn:
        before = conn.execute(
            text(
                """
                SELECT extracted_json
                FROM cap_documents
                WHERE case_id = :case_id AND doc_id = :doc_id
                """
            ),
            {"case_id": case_id, "doc_id": doc_id},
        ).mappings().first()
        before_payload = from_json(before["extracted_json"]) if before else {}
        conn.execute(
            text(
                """
                UPDATE cap_documents
                SET extracted_json = :extracted_json
                WHERE case_id = :case_id AND doc_id = :doc_id
                """
            ),
            {
                "case_id": case_id,
                "doc_id": doc_id,
                "extracted_json": as_json(fields),
            },
        )
    write_audit(case_id, "documents-agent", "extract_fields", before_payload, fields)
    return {"case_id": case_id, "doc_id": doc_id, "fields": fields}


@mcp.tool()
def validate_case_documents(case_id: str, required_docs: list[str]) -> dict:
    docs = list_documents(case_id)
    present = {item["doc_id"].lower() for item in docs}
    missing = sorted(doc for doc in required_docs if doc.lower() not in present)
    return {"case_id": case_id, "missing_documents": missing, "valid": not missing}


@mcp.resource("document://{case_id}/{doc_id}")
def document_resource(case_id: str, doc_id: str) -> str:
    docs = list_documents(case_id)
    for doc in docs:
        if doc["doc_id"] == doc_id:
            return as_json(doc)
    return as_json({"error": f"Unknown document {doc_id} for case {case_id}"})


@mcp.tool()
def upsert_document(case_id: str, doc_id: str, content: str, doc_type: str = "unknown") -> dict:
    ensure_capstone_tables()
    engine = make_engine()
    now = datetime.utcnow().isoformat()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO cap_documents (case_id, doc_id, doc_type, content, extracted_json, created_at)
                VALUES (:case_id, :doc_id, :doc_type, :content, :extracted_json, :created_at)
                ON CONFLICT(case_id, doc_id) DO UPDATE SET
                    doc_type = excluded.doc_type,
                    content = excluded.content
                """
            ),
            {
                "case_id": case_id,
                "doc_id": doc_id,
                "doc_type": doc_type,
                "content": content,
                "extracted_json": as_json({}),
                "created_at": now,
            },
        )
    write_audit(case_id, "documents-agent", "upsert_document", {}, {"doc_id": doc_id, "doc_type": doc_type})
    return {"case_id": case_id, "doc_id": doc_id, "saved": True}


def main() -> None:
    ensure_capstone_tables()
    mcp.run("stdio")


if __name__ == "__main__":
    main()
