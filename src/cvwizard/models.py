"""Version 1 career evidence and claims models.

The YAML document is a transport format. These strict models define its semantics.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator


Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Identifier = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class VerificationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    VERIFIED_WITH_QUALIFICATION = "VERIFIED_WITH_QUALIFICATION"
    NEEDS_VERIFICATION = "NEEDS_VERIFICATION"
    CONFLICTING = "CONFLICTING"
    UNSUPPORTED = "UNSUPPORTED"
    PROHIBITED = "PROHIBITED"


class ContributionScope(StrEnum):
    INDIVIDUAL = "INDIVIDUAL"
    TEAM = "TEAM"
    PROGRAMME = "PROGRAMME"


class Confidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class Confidentiality(StrEnum):
    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"
    RESTRICTED = "RESTRICTED"
    PROHIBITED_PUBLICATION = "PROHIBITED_PUBLICATION"


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class UsagePermission(StrEnum):
    NOT_REQUESTED = "NOT_REQUESTED"
    GRANTED = "GRANTED"
    DENIED = "DENIED"


class CandidateProfile(StrictModel):
    candidate_id: Identifier
    display_name: Text
    headline: Text | None = None
    notes: Text | None = None


class EvidenceSource(StrictModel):
    source_id: Identifier
    kind: Literal["DOCUMENT", "RECORD", "INTERVIEW", "SELF_REPORT", "PUBLIC_LINK"]
    title: Text
    locator: Text
    provenance: Text
    verification_status: VerificationStatus
    confidentiality: Confidentiality
    captured_on: date | None = None
    qualifications: list[Text] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_qualification(self) -> EvidenceSource:
        if self.verification_status == VerificationStatus.VERIFIED_WITH_QUALIFICATION and not self.qualifications:
            raise ValueError("qualified source verification requires qualifications")
        return self


class Metric(StrictModel):
    metric_id: Identifier
    value: Decimal
    unit: Text
    scope: ContributionScope
    context: Text
    source_ids: list[Identifier] = Field(min_length=1)

    @field_validator("value")
    @classmethod
    def finite_value(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("metric value must be finite")
        return value


class EvidenceBase(StrictModel):
    evidence_id: Identifier
    description: Text
    context: Text
    start_date: date | None = None
    end_date: date | None = None
    contribution_scope: ContributionScope
    source_ids: list[Identifier] = Field(min_length=1)
    verification_status: VerificationStatus
    confidence: Confidence
    uncertainty: Text | None = None
    confidentiality: Confidentiality
    metrics: list[Metric] = Field(default_factory=list)
    notes: Text | None = None
    qualifications: list[Text] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_dates(self) -> EvidenceBase:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date precedes start_date")
        return self


class Education(EvidenceBase):
    category: Literal["EDUCATION"]
    institution: Text
    credential: Text
    field_of_study: Text | None = None


class EmploymentExperience(EvidenceBase):
    category: Literal["EMPLOYMENT"]
    employer: Text
    role: Text


class Project(EvidenceBase):
    category: Literal["PROJECT"]
    project_name: Text
    role: Text | None = None


class Skill(EvidenceBase):
    category: Literal["SKILL"]
    skill_name: Text


class Achievement(EvidenceBase):
    category: Literal["ACHIEVEMENT"]
    title: Text


class Publication(EvidenceBase):
    category: Literal["PUBLICATION"]
    title: Text
    publisher: Text | None = None


class Certification(EvidenceBase):
    category: Literal["CERTIFICATION"]
    title: Text
    issuer: Text


EvidenceRecord = Annotated[
    Union[Education, EmploymentExperience, Project, Skill, Achievement, Publication, Certification],
    Field(discriminator="category"),
]


class CareerClaim(StrictModel):
    claim_id: Identifier
    proposed_statement: Text
    approved_statement: Text | None = None
    supporting_evidence_ids: list[Identifier] = Field(min_length=1)
    contribution_scope: ContributionScope
    verification_status: VerificationStatus
    required_qualifications: list[Text] = Field(default_factory=list)
    approval_status: ApprovalStatus
    usage_permission: UsagePermission
    approved_by: Text | None = None
    approved_on: date | None = None
    reviewer_notes: Text | None = None


class CareerDataset(StrictModel):
    schema_version: Literal["1.0"]
    profile: CandidateProfile
    sources: list[EvidenceSource]
    evidence: list[EvidenceRecord]
    claims: list[CareerClaim]
