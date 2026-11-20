from typing import List, Literal, Optional

from pydantic import BaseModel

Category = Literal[
    "non_disclosure_preexisting",
    "waiting_period",
    "document_deficiency",
    "exclusion",
    "policy_lapse_cancellation",
    "room_rent_deduction",
    "not_medically_necessary",
    "other",
]

CATEGORY_LABELS = {
    "non_disclosure_preexisting": "Non-disclosure / pre-existing condition",
    "waiting_period": "Waiting period",
    "document_deficiency": "Missing documents",
    "exclusion": "Policy exclusion",
    "policy_lapse_cancellation": "Policy lapsed or cancelled",
    "room_rent_deduction": "Room-rent deduction",
    "not_medically_necessary": "Not medically necessary",
    "other": "Unclear reason",
}


class AnalysisOut(BaseModel):
    """Schema sent to the model. No defaults: keeps structured output simple."""

    insurer: Optional[str]
    claim_amount_inr: Optional[int]
    rejection_category: Category
    clause_cited: Optional[str]
    policy_cancelled_by_insurer: bool
    plain_explanation: str
    missing_info: List[str]
    confidence: float
    needs_human_review: bool


class DraftOut(BaseModel):
    grievance_subject: str
    grievance_body: str
    ombudsman_complaint: str
    checklist: List[str]


class Details(BaseModel):
    name: str = ""
    patient: str = ""
    policy_no: str = ""
    claim_no: str = ""
    hospital: str = ""
    rejection_date: str = ""  # YYYY-MM-DD
    grievance_date: str = ""  # YYYY-MM-DD
    contact: str = ""
    notes: str = ""  # anything the person wants the draft to mention


class ChatIn(BaseModel):
    question: str
    lang: str = "en"


class ReviewIn(BaseModel):
    action: Literal["approve", "changes"]
    grievance_body: Optional[str] = None
    ombudsman_complaint: Optional[str] = None
    note: str = ""
