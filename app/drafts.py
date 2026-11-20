"""Template drafts used in basic mode (no AI). They only cite rules from the verified library."""
from datetime import datetime

from .schemas import CATEGORY_LABELS


def _d(iso):
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d %B %Y").lstrip("0")
    except (ValueError, TypeError):
        return iso

ARGS = {
    "non_disclosure_preexisting": (
        "I dispute that any material fact was knowingly withheld. Please share the proposal form and the medical records you relied on, "
        "and explain how the condition you mention is related to the illness for which I claimed. Please also confirm how many months of "
        "continuous cover I have had: under the IRDAI Master Circular on Health Insurance Business (2024), after 60 months of continuous "
        "coverage a claim cannot be contested on grounds of non-disclosure except for established fraud."
    ),
    "waiting_period": (
        "Please confirm my policy start date, the exact waiting-period clause and the date the waiting period ends. Please also check whether "
        "waiting-period credits from my earlier continuous cover (renewal, migration or portability) were applied, as the IRDAI Master Circular "
        "requires accrued credits to carry over."
    ),
    "document_deficiency": (
        "I submitted the documents on [DATES] through [CHANNEL]. Please state in writing exactly which documents you say are missing and when each "
        "request was made. I enclose a dated index of everything I submitted and ask you to reopen and process the claim on that basis."
    ),
    "exclusion": (
        "Please share the exact exclusion clause and the page of the policy document where it appears. I submit that [EXPLAIN WHY YOUR TREATMENT "
        "DOES NOT FALL WITHIN THE WORDS OF THE CLAUSE, USING YOUR DOCTOR'S NOTES]. Please reconsider on this basis."
    ),
    "policy_lapse_cancellation": (
        "Please confirm the premium due date, the date my payment was received, and the grace period applied. Under the IRDAI Master Circular the "
        "grace period is 15 days for monthly instalments and 30 days for quarterly, half-yearly or annual premiums. Please check whether my policy "
        "was in force on the date of admission. If the policy was cancelled, please share the written cancellation notice, the evidence relied on "
        "and the approval for cancellation."
    ),
    "room_rent_deduction": (
        "Please share the exact clause that limits room rent and the clause that allows a proportionate deduction on other charges. Please give me "
        "a head-by-head calculation showing how the deducted amount was worked out."
    ),
    "not_medically_necessary": (
        "My treating doctor [DOCTOR NAME] advised admission on [DATE] because [REASON]. I enclose the doctor's certificate. Please share the clause "
        "and the medical opinion you relied on to say the admission was not necessary."
    ),
    "other": (
        "Your letter does not state a specific reason or policy clause. Please provide the specific clause and the reasons for the decision in writing."
    ),
}

CHECKLIST = {
    "non_disclosure_preexisting": ["Proposal form copy", "Medical records for the past illness the insurer mentions", "Doctor's note on whether it relates to this claim", "Proof of continuous cover (renewal receipts, months covered)"],
    "waiting_period": ["Policy schedule showing start date and waiting periods", "Earlier policy copies (if you ported or migrated)", "Doctor's note on when the illness was first diagnosed"],
    "document_deficiency": ["Dated index of every document sent", "Email or courier proof for each submission", "The insurer's document requests, in date order"],
    "exclusion": ["Policy wording with the exclusion clause marked", "Treating doctor's note on diagnosis and cause", "Hospital records for the treatment"],
    "policy_lapse_cancellation": ["Premium payment receipts with dates", "Policy schedule and renewal notices", "Cancellation notice (if any)"],
    "room_rent_deduction": ["Policy schedule showing the room-rent limit", "Hospital bill with room tariff", "Insurer's settlement calculation"],
    "not_medically_necessary": ["Treating doctor's signed certificate on need for admission", "Admission note and treatment chart", "Investigation reports"],
    "other": ["Everything the insurer has sent you, in date order"],
}
COMMON = [
    "Copy of the rejection letter",
    "Policy copy and schedule",
    "Discharge summary and hospital bills",
    "ID proof (KYC)",
    "Proof of when you sent your grievance to the insurer",
]


def make(analysis: dict, d: dict) -> dict:
    cat = analysis["rejection_category"]
    insurer = analysis.get("insurer") or "[INSURER NAME]"
    amount = f"Rs. {analysis['claim_amount_inr']:,}" if analysis.get("claim_amount_inr") else "[CLAIM AMOUNT]"
    name = d.get("name") or "[YOUR NAME]"
    patient = d.get("patient") or name
    policy = d.get("policy_no") or "[POLICY NUMBER]"
    claim = d.get("claim_no") or "[CLAIM NUMBER]"
    hospital = d.get("hospital") or "[HOSPITAL NAME]"
    rej = _d(d.get("rejection_date")) or "[DATE OF REJECTION LETTER]"
    gri = _d(d.get("grievance_date")) or "[DATE YOU SENT THE GRIEVANCE]"
    contact = d.get("contact") or "[PHONE / EMAIL]"
    clause = analysis.get("clause_cited")
    reason = f'The clause you relied on: "{clause}"' if clause else f"Reason given: {CATEGORY_LABELS[cat].lower()}."
    extra = f"\n\nAdditional information: {d['notes']}" if d.get("notes") else ""
    checklist = CHECKLIST.get(cat, []) + COMMON

    body = (
        f"To,\nThe Grievance Redressal Officer,\n{insurer}\n\nSubject: Request for reconsideration of rejected claim {claim} (Policy {policy})\n\n"
        f"Dear Sir/Madam,\n\nI am writing about claim {claim} under policy {policy} for the treatment of {patient} at {hospital}, "
        f"claim amount {amount}. Your letter dated {rej} rejected this claim. {reason}\n\n"
        f"{ARGS[cat]}\n\n"
        "I request that you:\n"
        "1. Give me, in writing, the exact policy clause and every document you relied on.\n"
        "2. Confirm that the rejection was approved by your Product Management Committee or Claims Review Committee, as the IRDAI Master Circular on Health Insurance Business (2024) requires.\n"
        "3. Reconsider the claim and pay the amount due.\n"
        "4. Reply in writing within one month.\n\n"
        "If I do not receive a satisfactory reply, I will approach the Insurance Ombudsman and IRDAI (Bima Bharosa)."
        f"{extra}\n\nEnclosures: see attached list.\n\nSincerely,\n{name}\nContact: {contact}"
    )
    omb = (
        "To,\nThe Insurance Ombudsman\n[OFFICE: find yours at cioins.co.in]\n\n"
        f"Subject: Complaint against {insurer} regarding rejected health-insurance claim {claim}\n\n"
        f"Complainant: {name}\nContact: {contact}\nInsurer: {insurer}\nPolicy number: {policy}\nClaim number: {claim}\nClaim amount: {amount}\n\n"
        "Facts:\n"
        f"1. I am insured under policy {policy}. {patient} was treated at {hospital}.\n"
        f"2. I claimed {amount}. The insurer rejected the claim by letter dated {rej}. {reason}\n"
        f"3. I sent a written grievance to the insurer on {gri}. [STATE WHETHER THE INSURER REPLIED, AND WHEN. IF NOT, STATE THAT ONE MONTH HAS PASSED WITHOUT A REPLY.]\n"
        f"4. My position: {ARGS[cat]}\n\n"
        f"Relief sought: payment of {amount} with such interest and expenses as the Ombudsman considers fit.\n\n"
        "Declaration: [CONFIRM THAT THIS MATTER IS NOT PENDING BEFORE ANY COURT, CONSUMER FORUM OR ARBITRATOR. CHECK THE CURRENT OMBUDSMAN RULES.]\n\n"
        "Documents attached: copy of my representation to the insurer; KYC; photograph; insurer's rejection letter; policy copy; other relevant documents.\n\n"
        f"Signature: {name}\nDate: [DATE]"
    )
    return {
        "grievance_subject": f"Request for reconsideration of rejected claim {claim} (Policy {policy})",
        "grievance_body": body,
        "ombudsman_complaint": omb,
        "checklist": checklist,
    }
