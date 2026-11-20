import calendar
from datetime import date, datetime


def _parse(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def add_months(d: date, n: int) -> date:
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def _status(d: date, today: date) -> str:
    if d < today:
        return "past"
    if (d - today).days <= 14:
        return "soon"
    return "upcoming"


def compute(rejection_date: str = "", grievance_date: str = "", today: date = None):
    """Milestones based on the Ombudsman rules (verified on cioins.co.in/Faqs):
    - complain to the insurer first;
    - go to the Ombudsman if no reply within 1 month, or if unhappy with the reply;
    - file with the Ombudsman within 1 year of the insurer's rejection of the complaint,
      or within 1 year after the 1-month wait if there is no reply.
    """
    today = today or date.today()
    rej = _parse(rejection_date)
    gri = _parse(grievance_date)
    items = []
    if rej:
        items.append({
            "label": "Claim rejection letter date",
            "date": rej.isoformat(),
            "note": "Your starting point.",
            "status": "past" if rej <= today else "upcoming",
        })
    if gri:
        wait_end = add_months(gri, 1)
        items.append({
            "label": "Grievance sent to insurer",
            "date": gri.isoformat(),
            "note": "Keep proof of sending.",
            "status": "past" if gri <= today else "upcoming",
        })
        items.append({
            "label": "Insurer's one-month reply window ends",
            "date": wait_end.isoformat(),
            "note": "No reply, or an unsatisfactory reply? You can approach the Ombudsman and IRDAI.",
            "status": _status(wait_end, today),
        })
        latest = add_months(wait_end, 12)
        items.append({
            "label": "Latest date to file with the Ombudsman (if no reply)",
            "date": latest.isoformat(),
            "note": "If the insurer replies and rejects your complaint, the 1 year runs from that reply instead.",
            "status": _status(latest, today),
        })
    else:
        items.append({
            "label": "Send your grievance to the insurer",
            "date": "",
            "note": "Do this first and note the date. Then enter it here to get your dates.",
            "status": "todo",
        })
    return items
