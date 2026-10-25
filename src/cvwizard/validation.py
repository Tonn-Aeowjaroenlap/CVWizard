"""Offline structural and cross-record validation."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import yaml
from pydantic import ValidationError

from .models import (
    ApprovalStatus,
    CareerDataset,
    Confidentiality,
    VerificationStatus,
    UsagePermission,
)


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects keys PyYAML would otherwise overwrite."""


def _unique_mapping(loader: UniqueKeyLoader, node: yaml.MappingNode) -> dict:
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        try:
            hash(key)
        except TypeError as exc:
            raise yaml.constructor.ConstructorError(
                "mapping", node.start_mark, "YAML mapping key must be hashable", key_node.start_mark
            ) from exc
        if key in result:
            raise yaml.constructor.ConstructorError(
                "mapping", node.start_mark, f"duplicate YAML key {key!r}", key_node.start_mark
            )
        result[key] = loader.construct_object(value_node)
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def validate_path(path: Path) -> list[str]:
    """Return actionable errors; an empty list means the dataset is valid."""
    if path.is_dir():
        path = path / "dataset.yaml"
    try:
        with path.open(encoding="utf-8") as stream:
            raw = yaml.load(stream, Loader=UniqueKeyLoader)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        return [f"{path}: {exc}"]
    if not isinstance(raw, dict):
        return [f"{path}: expected a YAML mapping at the document root"]
    try:
        dataset = CareerDataset.model_validate(raw)
    except ValidationError as exc:
        return [f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}" for error in exc.errors()]
    return validate_dataset(dataset)


def validate_dataset(dataset: CareerDataset) -> list[str]:
    errors: list[str] = []
    for label, values in (
        ("source_id", [item.source_id for item in dataset.sources]),
        ("evidence_id", [item.evidence_id for item in dataset.evidence]),
        ("claim_id", [item.claim_id for item in dataset.claims]),
        ("metric_id", [metric.metric_id for item in dataset.evidence for metric in item.metrics]),
    ):
        errors.extend(f"duplicate {label}: {value}" for value, count in Counter(values).items() if count > 1)

    sources = {item.source_id: item for item in dataset.sources}
    evidence = {item.evidence_id: item for item in dataset.evidence}
    valid_statuses = {VerificationStatus.VERIFIED, VerificationStatus.VERIFIED_WITH_QUALIFICATION}

    for item in dataset.evidence:
        for source_id in item.source_ids:
            if source_id not in sources:
                errors.append(f"evidence {item.evidence_id}: missing source {source_id}")
        if item.verification_status == VerificationStatus.VERIFIED_WITH_QUALIFICATION and not item.qualifications:
            errors.append(f"evidence {item.evidence_id}: qualified verification requires qualifications")
        for metric in item.metrics:
            if metric.scope != item.contribution_scope:
                errors.append(f"metric {metric.metric_id}: scope differs from evidence {item.evidence_id}")
            for source_id in metric.source_ids:
                if source_id not in sources:
                    errors.append(f"metric {metric.metric_id}: missing source {source_id}")
                elif source_id not in item.source_ids:
                    errors.append(f"metric {metric.metric_id}: source {source_id} is not cited by evidence {item.evidence_id}")

    for claim in dataset.claims:
        support = []
        for evidence_id in claim.supporting_evidence_ids:
            item = evidence.get(evidence_id)
            if item is None:
                errors.append(f"claim {claim.claim_id}: missing evidence {evidence_id}")
            else:
                support.append(item)
                if item.contribution_scope != claim.contribution_scope:
                    errors.append(
                        f"claim {claim.claim_id}: {evidence_id} has {item.contribution_scope} scope, "
                        f"not {claim.contribution_scope}"
                    )
        if claim.verification_status == VerificationStatus.VERIFIED_WITH_QUALIFICATION and not claim.required_qualifications:
            errors.append(f"claim {claim.claim_id}: qualified verification requires required_qualifications")
        if claim.approval_status != ApprovalStatus.APPROVED:
            if claim.approved_statement or claim.approved_by or claim.approved_on:
                errors.append(f"claim {claim.claim_id}: approval fields require APPROVED status")
            continue
        if claim.verification_status not in valid_statuses:
            errors.append(f"claim {claim.claim_id}: {claim.verification_status} claim cannot be approved")
        if claim.usage_permission != UsagePermission.GRANTED:
            errors.append(f"claim {claim.claim_id}: approval requires GRANTED usage_permission")
        if not (claim.approved_statement and claim.approved_by and claim.approved_on):
            errors.append(f"claim {claim.claim_id}: approval requires approved_statement, approved_by and approved_on")
        required = list(claim.required_qualifications)
        for item in support:
            if item.verification_status not in valid_statuses:
                errors.append(f"claim {claim.claim_id}: supporting evidence {item.evidence_id} is not verified")
            if item.confidentiality == Confidentiality.PROHIBITED_PUBLICATION:
                errors.append(f"claim {claim.claim_id}: evidence {item.evidence_id} prohibits publication")
            required.extend(item.qualifications)
            for source_id in item.source_ids:
                source = sources.get(source_id)
                if source is None:
                    continue
                if source.verification_status not in valid_statuses:
                    errors.append(f"claim {claim.claim_id}: source {source_id} is not verified")
                if source.confidentiality == Confidentiality.PROHIBITED_PUBLICATION:
                    errors.append(f"claim {claim.claim_id}: source {source_id} prohibits publication")
                required.extend(source.qualifications)
        if required and not claim.required_qualifications:
            errors.append(f"claim {claim.claim_id}: approved claim is missing mandatory qualifications")
        for qualification in required:
            if qualification not in claim.required_qualifications:
                errors.append(f"claim {claim.claim_id}: required_qualifications omits {qualification!r}")
        for qualification in required:
            if claim.approved_statement and qualification.casefold() not in claim.approved_statement.casefold():
                errors.append(f"claim {claim.claim_id}: approved_statement omits qualification {qualification!r}")
    return errors
