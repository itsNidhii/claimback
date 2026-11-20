"""Basic mode: keyword classifier used when no AI model is reachable (no key, quota used up,
network down). It keeps the app working, and labels itself as 'basic' in the UI."""
import re

EXPLAIN = {
    "non_disclosure_preexisting": {
        "en": "The insurer says a health condition or fact was not declared when the policy was bought, so it rejected the claim. You can ask for the proposal form and the records it relied on, and check whether the condition is related to this illness.",
        "hi": "बीमा कंपनी का कहना है कि पॉलिसी लेते समय किसी बीमारी या स्वास्थ्य जानकारी की घोषणा नहीं की गई, इसलिए दावा खारिज हुआ। आप प्रस्ताव फ़ॉर्म और उसके आधार वाले रिकॉर्ड माँग सकते हैं और देख सकते हैं कि वह बीमारी इस इलाज से जुड़ी है या नहीं।",
    },
    "waiting_period": {
        "en": "The insurer says the treatment happened during a waiting period, a time after buying the policy when certain illnesses are not covered. Check the exact waiting period in your policy and whether earlier continuous cover should count.",
        "hi": "बीमा कंपनी का कहना है कि इलाज वेटिंग पीरियड (प्रतीक्षा अवधि) में हुआ, जब कुछ बीमारियाँ कवर नहीं होतीं। अपनी पॉलिसी में सही अवधि देखें और यह भी कि पहले का लगातार कवर गिना जाना चाहिए या नहीं।",
    },
    "document_deficiency": {
        "en": "The insurer says documents are missing and has closed or stalled the claim. A dated list of everything you sent, with proof of how and when, is your strongest tool here.",
        "hi": "बीमा कंपनी का कहना है कि दस्तावेज़ नहीं मिले और दावा बंद या रुका हुआ है। आपने जो भेजा उसकी तारीख़ वाली सूची और भेजने का सबूत यहाँ सबसे काम की चीज़ है।",
    },
    "exclusion": {
        "en": "The insurer says this treatment falls under an exclusion in your policy, something the policy does not cover. Ask for the exact clause and compare its words with your medical records.",
        "hi": "बीमा कंपनी का कहना है कि यह इलाज आपकी पॉलिसी की बहिष्करण (exclusion) शर्त में आता है। सटीक शर्त माँगें और उसके शब्दों को अपने मेडिकल रिकॉर्ड से मिलाएँ।",
    },
    "policy_lapse_cancellation": {
        "en": "The insurer says your policy was not in force on the admission date, or has been cancelled. Check the premium dates and the grace period, and ask for the written notice if it was cancelled.",
        "hi": "बीमा कंपनी का कहना है कि भर्ती की तारीख़ पर आपकी पॉलिसी चालू नहीं थी या रद्द कर दी गई। प्रीमियम की तारीख़ें और ग्रेस पीरियड जाँचें, और रद्द होने पर लिखित नोटिस माँगें।",
    },
    "room_rent_deduction": {
        "en": "The insurer paid only part of the claim because your room cost more than your policy's room-rent limit, and it reduced other charges in proportion. Ask for the exact clause and a head-by-head calculation.",
        "hi": "आपका कमरा पॉलिसी की किराया सीमा से महँगा था, इसलिए बीमा कंपनी ने दावे का सिर्फ़ हिस्सा दिया और बाकी खर्च भी अनुपात में घटाए। सटीक शर्त और मद-वार हिसाब माँगें।",
    },
    "not_medically_necessary": {
        "en": "The insurer says the hospital stay was not medically necessary, for example admission only for tests. Your treating doctor's certificate explaining why admission was needed is the key document.",
        "hi": "बीमा कंपनी का कहना है कि अस्पताल में भर्ती चिकित्सकीय रूप से ज़रूरी नहीं थी, जैसे सिर्फ़ जाँच के लिए भर्ती। आपके डॉक्टर का प्रमाणपत्र कि भर्ती क्यों ज़रूरी थी, सबसे अहम दस्तावेज़ है।",
    },
    "other": {
        "en": "The letter does not give a clear reason or clause. Ask the insurer to state the specific reason and policy clause in writing.",
        "hi": "पत्र में कारण या शर्त साफ़ नहीं है। बीमा कंपनी से लिखित में सटीक कारण और पॉलिसी की शर्त बताने को कहें।",
    },
}

# (category, weighted phrases)
_KEYS = [
    ("non_disclosure_preexisting", [(r"non-?disclos", 3), (r"not (been )?(disclosed|declared)", 3), (r"suppress", 3), (r"misrepresent", 3), (r"pre-?existing", 2), (r"proposal form", 1), (r"material fact", 2)]),
    ("waiting_period", [(r"waiting period", 4), (r"within this period", 1), (r"initial period", 1)]),
    ("document_deficiency", [(r"not received", 2), (r"reminder", 2), (r"no documents", 3), (r"documents? (were|was|is|are) (not|still)", 2), (r"discharge summary", 1), (r"incomplete", 2), (r"deficien", 3), (r"resubmit", 2), (r"missing", 1)]),
    ("exclusion", [(r"exclusion", 4), (r"excluded", 3), (r"not covered", 3), (r"not payable", 1), (r"permanent exclusion", 2)]),
    ("policy_lapse_cancellation", [(r"lapse", 4), (r"grace period", 3), (r"renewal premium", 2), (r"not in force", 3), (r"no cover was in force", 3), (r"premium (was )?(not )?(received|paid)", 1)]),
    ("room_rent_deduction", [(r"room rent", 4), (r"proportionate", 4), (r"settled at", 2), (r"per day", 1)]),
    ("not_medically_necessary", [(r"not medically necessary", 5), (r"medically necessary", 2), (r"no active line of treatment", 5), (r"investigations? only", 4), (r"solely for diagnos", 4), (r"diagnostic", 2), (r"observation", 1)]),
]


def _amount(text):
    m = re.search(r"(?:rs\.?|inr|₹)\s*([\d,]{3,})", text, re.I)
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _clause(text):
    parts = re.split(r"(?<=[.;])\s+|\n+", text)
    for p in parts:
        if re.search(r"\b(clause|exclusion|section|para)\b\s*[\d.]+", p, re.I):
            return p.strip()
    return None


def _insurer(text):
    first = text.strip().split("\n")[0].strip()
    if 3 < len(first) < 70 and re.search(r"(insurance|assurance|health|general|co\.?)", first, re.I):
        return first
    m = re.search(r"([A-Z][A-Za-z&. ]{2,40}(?:Insurance|Assurance)(?: Co\.?| Company| Ltd\.?)?)", text)
    return m.group(1).strip() if m else None


def classify(text: str, lang: str = "en") -> dict:
    t = text.lower()
    scores = {}
    for cat, pats in _KEYS:
        scores[cat] = sum(w for p, w in pats if re.search(p, t))
    best = max(scores, key=scores.get)
    top = scores[best]
    ordered = sorted(scores.values(), reverse=True)
    margin = top - ordered[1]
    cancelled = bool(re.search(r"(policy|cover|coverage)[^.]{0,60}(cancel|terminat)|(cancel|terminat)[^.]{0,60}(policy|cover)", t))
    if top < 3:
        cat, conf = "other", 0.3
    else:
        cat = best
        conf = min(0.85, 0.5 + 0.05 * top + 0.05 * margin)
    clause = _clause(text)
    missing = []
    if not clause:
        missing.append("The exact policy clause the insurer relies on")
    if not re.search(r"\b(20\d\d|19\d\d)\b", text):
        missing.append("Dates (policy start, admission, rejection)")
    if cat == "other":
        missing.append("The specific reason for rejection")
    lang = "hi" if lang == "hi" else "en"
    return {
        "insurer": _insurer(text),
        "claim_amount_inr": _amount(text),
        "rejection_category": cat,
        "clause_cited": clause,
        "policy_cancelled_by_insurer": cancelled,
        "plain_explanation": EXPLAIN[cat][lang],
        "missing_info": missing,
        "confidence": round(conf, 2),
        "needs_human_review": conf < 0.6 or cat == "other",
    }
