from typing import Literal
from pydantic import BaseModel, field_validator, model_validator
import re


_MARKDOWN_TOKENS = ["**", "##", "* ", "`", "\n"]


def _check_markdown(value: str, field_name: str) -> str:
    for token in _MARKDOWN_TOKENS:
        if token in value:
            raise ValueError(f"Markdown or newline detected in CSV field: {field_name}")
    return value


class TicketResponse(BaseModel):
    status: Literal["replied", "escalated"]
    product_area: str
    response: str
    justification: str
    request_type: Literal["product_issue", "feature_request", "bug", "invalid"]

    @model_validator(mode='after')
    def enforce_escalation_on_missing_context(self) -> "TicketResponse":
        justification = self.justification.lower()
        if "does not contain" in justification or "does not address" in justification:
            self.status = "escalated"
            self.response = "This requires specialist attention. Our team will follow up with you shortly."
        return self

    @field_validator("product_area")
    @classmethod
    def clean_product_area(cls, v: str) -> str:
        # Removes "HackerRank: ", "Claude - ", etc. 
        # and converts to lowercase to match taxonomy.md exactly
        clean = re.sub(r'^(HackerRank|Claude|Visa)[:\-\s]+', '', v, flags=re.IGNORECASE)
        return clean.strip().lower()

    @field_validator("response")
    @classmethod
    def validate_response(cls, v: str) -> str:
        return _check_markdown(v, "response")

    @field_validator("justification")
    @classmethod
    def validate_justification(cls, v: str) -> str:
        v = _check_markdown(v, "justification")
        word_count = len(v.split())
        if word_count < 20:
            raise ValueError(
                f"Justification too short: {word_count} words, minimum 20 required"
            )
        return v
