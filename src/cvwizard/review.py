"""Private intake ledger, review audit and conservative export gates."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, ValidationError, model_validator

from .models import Confidentiality, Identifier, StrictModel, Text
from .validation import UniqueKeyLoader


class DecisionKind(StrEnum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    QUALIFY = "QUALIFY"
    NEEDS_EVIDENCE = "NEEDS_EVIDENCE"


class SourceDocument(StrictModel):
    source_id: Identifier
    title: Text
    locator: Text
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    confidentiality: Confidentiality = Confidentiality.PRIVATE
    supersedes_source_id: Identifier | None = None


class Assertion(StrictModel):
    assertion_id: Identifier
    source_id: Identifier
    location: Text
    text: Text
    field: Text | None = None
    value: Text | None = None
    verification_status: Literal["NEEDS_VERIFICATION"] = "NEEDS_VERIFICATION"


class PotentialConflict(StrictModel):
    field: Text
    assertion_ids: list[Identifier] = Field(min_length=2)


class ReviewDecision(StrictModel):
    decision_id: Identifier
    assertion_id: Identifier
    decision: DecisionKind
    reviewer: Text
    decided_at: datetime
    reason: Text
    evidence_source_ids: list[Identifier] = Field(default_factory=list)
    qualification: Text | None = None
    approved_wording: Text | None = None
    outstanding_evidence: Text | None = None
    personal_cv_permission: bool = False
    external_disclosure_permission: bool = False
    public_portfolio_permission: bool = False
    previous_decision_id: Identifier | None = None

    @model_validator(mode="after")
    def check_decision(self) -> ReviewDecision:
        if self.decided_at.tzinfo is None or self.decided_at.utcoffset() is None:
            raise ValueError("decision time must include a timezone")
        if self.decision in {DecisionKind.ACCEPT, DecisionKind.QUALIFY} and not self.evidence_source_ids:
            raise ValueError("acceptance requires cited evidence sources")
        if self.decision == DecisionKind.QUALIFY and not self.qualification:
            raise ValueError("qualified decision requires qualification")
        if self.decision == DecisionKind.QUALIFY and (
            self.personal_cv_permission or self.external_disclosure_permission or self.public_portfolio_permission
        ):
            if not self.approved_wording:
                raise ValueError("permitted qualified decision requires human-approved wording")
            if self.qualification and self.qualification.casefold() not in self.approved_wording.casefold():
                raise ValueError("approved wording must include the qualification")
        if self.decision == DecisionKind.NEEDS_EVIDENCE and not self.outstanding_evidence:
            raise ValueError("needs-evidence decision requires outstanding_evidence")
        if self.decision not in {DecisionKind.ACCEPT, DecisionKind.QUALIFY} and (
            self.personal_cv_permission or self.external_disclosure_permission or self.public_portfolio_permission
        ):
            raise ValueError("rejected or outstanding assertion cannot receive usage permission")
        if self.decision not in {DecisionKind.ACCEPT, DecisionKind.QUALIFY} and self.approved_wording:
            raise ValueError("rejected or outstanding assertion cannot have approved wording")
        if self.public_portfolio_permission and not self.external_disclosure_permission:
            raise ValueError("public permission requires external disclosure permission")
        return self


class Intake(StrictModel):
    schema_version: Literal["0b1"] = "0b1"
    sources: list[SourceDocument]
    assertions: list[Assertion]
    conflicts: list[PotentialConflict] = Field(default_factory=list)
    decisions: list[ReviewDecision] = Field(default_factory=list)


def find_conflicts(assertions: list[Assertion]) -> list[PotentialConflict]:
    grouped: dict[str, list[Assertion]] = {}
    for item in assertions:
        if item.field and item.value:
            grouped.setdefault(item.field, []).append(item)
    return [
        PotentialConflict(field=field, assertion_ids=[item.assertion_id for item in items])
        for field, items in sorted(grouped.items())
        if len({item.value.casefold() for item in items if item.value}) > 1
    ]


def validate_intake(intake: Intake) -> list[str]:
    errors: list[str] = []
    for label, ids in (
        ("source", [s.source_id for s in intake.sources]),
        ("assertion", [a.assertion_id for a in intake.assertions]),
        ("decision", [d.decision_id for d in intake.decisions]),
    ):
        errors.extend(f"duplicate {label} ID: {item}" for item, count in Counter(ids).items() if count > 1)
    sources = {s.source_id: s for s in intake.sources}
    assertions = {a.assertion_id: a for a in intake.assertions}
    decisions = {d.decision_id: d for d in intake.decisions}
    for source in intake.sources:
        if source.supersedes_source_id and source.supersedes_source_id not in sources:
            errors.append(f"source {source.source_id}: unknown superseded source")
        if source.supersedes_source_id == source.source_id:
            errors.append(f"source {source.source_id}: cannot supersede itself")
    visited: set[str] = set()
    for source_id in sources:
        if source_id in visited:
            continue
        trail: set[str] = set()
        current = source_id
        while current in sources and current not in visited:
            if current in trail:
                errors.append(f"source {current}: cyclic supersession")
                break
            trail.add(current)
            current = sources[current].supersedes_source_id or ""
        visited.update(trail)
    for assertion in intake.assertions:
        if assertion.source_id not in sources:
            errors.append(f"assertion {assertion.assertion_id}: missing source")
    expected = {c.field: set(c.assertion_ids) for c in find_conflicts(intake.assertions)}
    actual = {c.field: set(c.assertion_ids) for c in intake.conflicts}
    if actual != expected or len(actual) != len(intake.conflicts):
        errors.append("conflict report does not match competing labelled assertions")
    latest: dict[str, ReviewDecision] = {}
    for decision in intake.decisions:
        if decision.assertion_id not in assertions:
            errors.append(f"decision {decision.decision_id}: missing assertion")
        previous = latest.get(decision.assertion_id)
        if decision.previous_decision_id != (previous.decision_id if previous else None):
            errors.append(f"decision {decision.decision_id}: broken decision history")
        if previous and decision.decided_at < previous.decided_at:
            errors.append(f"decision {decision.decision_id}: date precedes previous decision")
        for source_id in decision.evidence_source_ids:
            if source_id not in sources:
                errors.append(f"decision {decision.decision_id}: missing evidence source {source_id}")
        if decision.decision in {DecisionKind.ACCEPT, DecisionKind.QUALIFY}:
            if assertions.get(decision.assertion_id) and assertions[decision.assertion_id].source_id not in decision.evidence_source_ids:
                errors.append(f"decision {decision.decision_id}: assertion source must be cited")
        latest[decision.assertion_id] = decision
    for decision in intake.decisions:
        if decision.previous_decision_id and decision.previous_decision_id not in decisions:
            errors.append(f"decision {decision.decision_id}: unknown previous decision")
    return errors


def load_intake(path: Path) -> tuple[Intake | None, list[str]]:
    try:
        raw = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
        intake = Intake.model_validate(raw)
    except (OSError, UnicodeError, yaml.YAMLError, ValidationError) as exc:
        return None, [str(exc)]
    errors = validate_intake(intake)
    return (intake if not errors else None), errors


def export_facts(intake: Intake, audience: Literal["personal_cv", "external", "public"]) -> list[dict[str, str]]:
    """Export reviewed facts only. This does not generate CV or portfolio wording."""
    errors = validate_intake(intake)
    if errors:
        raise ValueError("invalid intake: " + "; ".join(errors))
    latest = {d.assertion_id: d for d in intake.decisions}
    sources = {s.source_id: s for s in intake.sources}
    result: list[dict[str, str]] = []
    for assertion in intake.assertions:
        decision = latest.get(assertion.assertion_id)
        if not decision or decision.decision not in {DecisionKind.ACCEPT, DecisionKind.QUALIFY}:
            continue
        source = sources[assertion.source_id]
        if source.confidentiality == Confidentiality.PROHIBITED_PUBLICATION:
            continue
        allowed = {
            "personal_cv": decision.personal_cv_permission,
            "external": decision.external_disclosure_permission and source.confidentiality != Confidentiality.RESTRICTED,
            "public": decision.public_portfolio_permission and source.confidentiality == Confidentiality.PUBLIC,
        }[audience]
        if not allowed:
            continue
        wording = decision.approved_wording if decision.decision == DecisionKind.QUALIFY else (
            decision.approved_wording or assertion.text
        )
        if not wording:
            raise ValueError(f"qualified decision {decision.decision_id} has no approved wording")
        result.append({
            "assertion_id": assertion.assertion_id, "source_id": source.source_id,
            "location": assertion.location,
            "approved_wording": wording,
            "qualification": decision.qualification or "", "decision_id": decision.decision_id,
        })
    return result
