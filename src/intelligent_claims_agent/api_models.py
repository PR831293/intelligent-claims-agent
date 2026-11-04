from __future__ import annotations

from pydantic import BaseModel, Field


class DocumentIn(BaseModel):
    name: str
    content: str


class ClaimInputIn(BaseModel):
    claim_id: str
    member_id: str
    claim_type: str
    amount: float
    documents: list[DocumentIn] = Field(default_factory=list)


class ResumeRequest(BaseModel):
    extra_documents: list[DocumentIn] = Field(default_factory=list)


class DecisionRequest(BaseModel):
    decision: str
    notes: str = ""
