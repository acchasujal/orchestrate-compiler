import re


INJECTION_PATTERNS = [
    "ignore previous",
    "act as",
    "system override",
    "developer mode",
    "jailbreak",
    "disregard",
    "new instructions",
    "you are now",
    "forget everything",
    "bypass",
    "ignore all",
]

_COMPANY_MAP = {
    "hackerrank": "hackerrank",
    "HackerRank": "hackerrank",
    "claude": "claude",
    "Claude": "claude",
    "visa": "visa",
    "Visa": "visa",
    "": None,
    "none": None,
    "None": None,
}

_COMPANY_KEYWORDS = {
    "hackerrank": ["hackerrank", "hacker rank"],
    "claude": ["claude", "anthropic"],
    "visa": ["visa"],
}


def _normalize_company(company) -> "str | None":
    if company is None:
        return None
    if company in _COMPANY_MAP:
        return _COMPANY_MAP[company]
    lower = company.lower()
    for key, val in _COMPANY_MAP.items():
        if key.lower() == lower:
            return val
    return company


def _redact_injections(text: str) -> tuple[str, bool]:
    detected = False
    for pattern in INJECTION_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            detected = True
            text = re.sub(re.escape(pattern), "[REDACTED]", text, flags=re.IGNORECASE)
    return text, detected


def _detect_multi_intent(issue: str) -> list[str]:
    question_marks = issue.count("?")
    if question_marks >= 2:
        parts = [s.strip() for s in re.split(r"\?", issue) if s.strip()]
        if len(parts) >= 2:
            return [parts[0] + "?", parts[1] + ("?" if not parts[1].endswith("?") else "")]

    sentences = [s.strip() for s in issue.split(". ") if s.strip()]
    if len(sentences) >= 2:
        first = sentences[0].lower()
        last = sentences[-1].lower()
        first_companies = {
            co for co, kws in _COMPANY_KEYWORDS.items()
            if any(kw in first for kw in kws)
        }
        last_companies = {
            co for co, kws in _COMPANY_KEYWORDS.items()
            if any(kw in last for kw in kws)
        }
        if first_companies and last_companies and first_companies != last_companies:
            midpoint = len(sentences) // 2
            part1 = ". ".join(sentences[:midpoint])
            part2 = ". ".join(sentences[midpoint:])
            return [part1, part2]

    return [issue]


def clean_ticket(issue: str, subject: str, company: str) -> dict:
    issue = issue.strip()
    subject = subject.strip()

    company_normalized = _normalize_company(company.strip() if company else company)

    issue, inj_issue = _redact_injections(issue)
    subject, inj_subject = _redact_injections(subject)
    injection_detected = inj_issue or inj_subject

    if subject and subject not in issue:
        issue = f"Subject: {subject}. {issue}"

    intents = _detect_multi_intent(issue)

    return {
        "issue": issue,
        "subject": subject,
        "company": company_normalized,
        "injection_detected": injection_detected,
        "intents": intents,
    }
