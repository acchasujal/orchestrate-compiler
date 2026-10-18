import re


HIGH_RISK_KEYWORDS = [
    "billing",
    "refund",
    "charge",
    "chargeback",
    "fraud",
    "unauthorized",
    "account recovery",
    "password",
    "token",
    "api key",
    "pii",
    "personal data",
    "suspend",
    "ban",
    "identity theft",
    "stolen card",
    "lost card",
    "data deletion",
    "gdpr",
    "legal",
]

MEDIUM_RISK_KEYWORDS = [
    "cannot access",
    "locked out",
    "not working",
    "error code",
    "can't login",
    "can't log in",
    "access denied",
    "account blocked",
]

LOW_RISK_KEYWORDS = [
    r"how (to|do|can|does)",
    r"what is",
    r"where can",
    r"does .* support",
    "explain",
    "documentation",
    "guide",
    "tutorial",
]

DEFAULT_RISK = 0.4


def assess_risk(ticket: dict) -> float:
    if ticket.get("injection_detected"):
        return 1.0

    issue = ticket.get("issue", "").lower()

    for kw in HIGH_RISK_KEYWORDS:
        if kw in issue:
            return 1.0

    for kw in MEDIUM_RISK_KEYWORDS:
        if kw in issue:
            return 0.6

    for pattern in LOW_RISK_KEYWORDS:
        if re.search(pattern, issue, re.IGNORECASE):
            return 0.2

    return DEFAULT_RISK
