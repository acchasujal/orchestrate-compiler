"""
orchestrate_compiler.ir
========================
The Intermediate Representation (IR) for the Orchestrate Compiler.

This is the ONLY contract between the frontend (semantic analysis of a novel
problem statement -- requires judgment, done via a structured prompt) and the
backend (code generation -- pure, deterministic, no judgment required).

Analogy: this plays the role of an AST in a real compiler. The frontend's job
is to produce a valid instance of ProblemIR. Once that instance exists, every
backend generator is a pure function: ProblemIR -> files on disk. No backend
generator ever re-reads the raw problem statement.

Every field here maps directly onto a module or decision in the Orchestrate
Operating System (orchestrate_operating_system.md). This file is the formal,
executable version of that document's Section 11 (PROBLEM_ADAPTER.md).
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional
import json


class FieldSource(str, Enum):
    """Trust-boundary classification for one output field. See theory doc §1.1 —
    this enum is the formalization of 'explicit trust boundaries.'"""
    MODEL_SOURCED = "model_sourced"      # perception-derived, uncertain, must pass a typed seam
    CODE_DECIDED = "code_decided"        # binding, pure function of typed inputs only


class ConflictResolution(str, Enum):
    """How the aggregation module resolves multiple evidence pieces disagreeing.
    Must be decided at IR-build time, not discovered during implementation --
    this is the formalization of the compound-claim gap found in the June audit."""
    MOST_CONSERVATIVE = "most_conservative"     # any contradiction -> whole record contradicted
    HIGHEST_CONFIDENCE = "highest_confidence"   # pick the observation with highest stated confidence
    PRIMARY_WINS = "primary_wins"               # a designated primary target overrides secondaries
    FLAG_FOR_REVIEW = "flag_for_review"          # unresolved conflicts route to manual review, never silently pick one


@dataclass
class OutputField:
    name: str
    type: str                      # e.g. "enum[supported,contradicted,not_enough_information]", "str", "list[str]"
    source: FieldSource
    invariant: Optional[str] = None  # e.g. "requires evidence_standard_met == True"


@dataclass
class AdversarialCase:
    """One entry in the 0:45-hour threat catalog from the Master Playbook,
    formalized so the backend can turn it directly into a test."""
    name: str
    description: str
    example_snippet: str = ""


@dataclass
class EvidenceSource:
    """One kind of raw evidence the perception module must interpret."""
    name: str                       # e.g. "claim_photo", "support_ticket_text"
    modality: str                   # "image" | "text" | "document" | "audio"
    observation_fields: list[str] = field(default_factory=list)  # what perception must extract


@dataclass
class ReferenceSource:
    """One kind of non-evidence external signal (history, rules, requirements)."""
    name: str
    lookup_key: str                 # e.g. "user_id"
    firewalled: bool = True         # must never be able to see evidence/claim text


@dataclass
class DecisionGate:
    """One gate in the decision module's rule chain."""
    name: str
    condition: str                  # human-readable rule, becomes a docstring + a test name
    on_pass: str
    on_fail: str


@dataclass
class ProblemIR:
    """The complete, compiled representation of one Orchestrate problem.
    A valid instance of this class is the ONLY input every backend generator needs."""

    problem_name: str
    one_line_success_criterion: str

    output_schema: list[OutputField] = field(default_factory=list)
    evidence_sources: list[EvidenceSource] = field(default_factory=list)
    reference_sources: list[ReferenceSource] = field(default_factory=list)
    conflict_resolution: ConflictResolution = ConflictResolution.MOST_CONSERVATIVE
    decision_gates: list[DecisionGate] = field(default_factory=list)
    adversarial_cases: list[AdversarialCase] = field(default_factory=list)

    uses_narration_llm: bool = False    # False = deterministic templates, True = LLM writer + mandatory audit
    needs_multi_step_agentic_loop: bool = False  # deviation from default single-pass; must be justified

    architecture_deviation_reason: Optional[str] = None  # REQUIRED if needs_multi_step_agentic_loop is True

    # --- competition logistics, pulled straight from the submission rules doc ---
    rubric_weights: dict = field(default_factory=lambda: {
        "code": 0.30, "output": 0.30, "interview": 0.30, "transcript": 0.10
    })
    output_csv_columns: list[str] = field(default_factory=list)  # exact order, byte-for-byte

    def validate(self) -> list[str]:
        """Structural checks a real compiler's semantic-analysis pass would run.
        Returns a list of errors; empty list = IR is well-formed and safe to compile."""
        errors = []
        if not self.output_schema:
            errors.append("output_schema is empty -- cannot generate schemas.py or Output Engine")
        if not self.decision_gates:
            errors.append("decision_gates is empty -- decision module would have no rules to encode")
        if self.needs_multi_step_agentic_loop and not self.architecture_deviation_reason:
            errors.append(
                "needs_multi_step_agentic_loop=True requires architecture_deviation_reason "
                "(per Architecture Loop exit condition: must name the specific case that requires it)"
            )
        code_decided_fields = [f for f in self.output_schema if f.source == FieldSource.CODE_DECIDED]
        if not code_decided_fields:
            errors.append(
                "No output field is classified CODE_DECIDED -- every field is model-sourced, "
                "meaning there is no binding decision boundary at all. This almost certainly "
                "means the trust-boundary map (Step 1) was skipped."
            )
        if not self.output_csv_columns:
            errors.append("output_csv_columns is empty -- Output Engine cannot validate header order")
        return errors

    def to_json(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2, default=str)

    @staticmethod
    def from_json(path: str) -> "ProblemIR":
        with open(path) as f:
            data = json.load(f)
        # reconstruct enums and nested dataclasses
        data["output_schema"] = [
            OutputField(**{**of, "source": FieldSource(of["source"])}) for of in data["output_schema"]
        ]
        data["evidence_sources"] = [EvidenceSource(**e) for e in data["evidence_sources"]]
        data["reference_sources"] = [ReferenceSource(**r) for r in data["reference_sources"]]
        data["decision_gates"] = [DecisionGate(**d) for d in data["decision_gates"]]
        data["adversarial_cases"] = [AdversarialCase(**a) for a in data["adversarial_cases"]]
        data["conflict_resolution"] = ConflictResolution(data["conflict_resolution"])
        return ProblemIR(**data)
