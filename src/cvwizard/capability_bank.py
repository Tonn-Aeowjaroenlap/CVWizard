"""Private, CV-derived capability catalogue with explicit source provenance.

The seed is editorial input. This module never verifies a CV statement or grants
permission to use a proposed description in an application.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .ingestion import ingest
from .review import Intake, SourceDocument, load_intake


CATEGORIES = (
    "Chemical and process engineering", "Process modelling, simulation and optimisation",
    "Data science and machine learning", "Industrial AI and digitalisation",
    "Technical project delivery and leadership", "Research and scientific communication",
    "Teaching and knowledge transfer", "Stakeholder engagement and collaboration",
    "Software, programming and technical tools", "Qualifications and professional development",
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceRef(StrictModel):
    source_id: str
    location: str


class SourceStatement(SourceRef):
    assertion_id: str
    text: str


class ProposedDescription(StrictModel):
    application: str
    wording: str
    basis: list[SourceRef] = Field(min_length=1)
    label: Literal["PROPOSED_WORDING"] = "PROPOSED_WORDING"


class CapabilitySeed(StrictModel):
    competency_id: str
    canonical: str
    category: str
    subcategory: str
    aliases: list[str] = Field(default_factory=list)
    related_terms: list[str] = Field(default_factory=list)
    skills_knowledge_methods: list[str] = Field(default_factory=list)
    tools_technologies: list[str] = Field(default_factory=list)
    industries_domains: list[str] = Field(default_factory=list)
    contexts: list[str] = Field(default_factory=list)
    described_contribution: str | None = None
    quantitative_achievements: list[str] = Field(default_factory=list)
    source_refs: list[SourceRef] = Field(min_length=1)
    alternative_cv_wording: list[ProposedDescription] = Field(default_factory=list)
    transferable_applications: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    explicit_vs_interpreted: Literal["EXPLICIT", "INTERPRETED"]
    interpretation_note: str | None = None
    status: Literal["CV_DERIVED", "CANDIDATE_REVIEWED", "EVIDENCE_VERIFIED"] = "CV_DERIVED"

    @model_validator(mode="after")
    def require_interpretation_note(self) -> "CapabilitySeed":
        if self.explicit_vs_interpreted == "INTERPRETED" and not self.interpretation_note:
            raise ValueError("interpreted competency requires interpretation_note")
        return self


class BankSeed(StrictModel):
    schema_version: Literal["0c-seed-1"] = "0c-seed-1"
    collection_note: str
    missing_versions: list[str] = Field(default_factory=list)
    application_targets: dict[str, str] = Field(default_factory=dict)
    additional_categories: list[str] = Field(default_factory=list)
    competencies: list[CapabilitySeed]


class BankEntry(CapabilitySeed):
    source_statements: list[SourceStatement] = Field(min_length=1)


class MasterBank(StrictModel):
    schema_version: Literal["0c-bank-1"] = "0c-bank-1"
    collection_note: str
    missing_versions: list[str]
    application_targets: dict[str, str]
    taxonomy: list[str]
    sources: list[SourceDocument]
    competencies: list[BankEntry]


def _refs(intake: Intake) -> dict[tuple[str, str], SourceStatement]:
    return {(a.source_id, a.location): SourceStatement(
        source_id=a.source_id, location=a.location, assertion_id=a.assertion_id, text=a.text,
    ) for a in intake.assertions}


def build_bank(seed: BankSeed, intake: Intake) -> dict:
    ids = [item.competency_id for item in seed.competencies]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate competency ID")
    refs = _refs(intake)
    if any(source_id not in {s.source_id for s in intake.sources} for source_id in seed.application_targets):
        raise ValueError("application target cites unknown source")
    competencies = []
    for item in seed.competencies:
        if item.status != "CV_DERIVED":
            raise ValueError("build cannot grant review or verification status")
        if not item.competency_id.startswith("cap-"):
            raise ValueError("competency ID must begin cap-")
        if item.category not in (*CATEGORIES, *seed.additional_categories):
            raise ValueError(f"unknown category: {item.category}")
        if len(item.source_refs) != len({(r.source_id, r.location) for r in item.source_refs}):
            raise ValueError(f"duplicate source reference: {item.competency_id}")
        statement_refs = {(r.source_id, r.location) for r in item.source_refs}
        for ref in item.source_refs:
            if (ref.source_id, ref.location) not in refs:
                raise ValueError(f"unknown source reference: {item.competency_id} {ref.source_id} {ref.location}")
        for description in item.alternative_cv_wording:
            if any((r.source_id, r.location) not in statement_refs for r in description.basis):
                raise ValueError(f"proposed wording lacks competency source: {item.competency_id}")
        record = item.model_dump(mode="json")
        record["source_statements"] = [refs[(r.source_id, r.location)].model_dump() for r in item.source_refs]
        competencies.append(record)
    bank = {
        "schema_version": "0c-bank-1", "collection_note": seed.collection_note,
        "missing_versions": seed.missing_versions,
        "application_targets": seed.application_targets,
        "taxonomy": list(CATEGORIES) + [c for c in seed.additional_categories if c not in CATEGORIES],
        "sources": [s.model_dump(mode="json") for s in intake.sources],
        "competencies": competencies,
    }
    return MasterBank.model_validate(bank).model_dump(mode="json")


def migration_map(old: Intake, new: Intake) -> list[dict[str, str]]:
    current = {(a.source_id, a.location): a for a in new.assertions}
    result = []
    for assertion in old.assertions:
        replacement = current.get((assertion.source_id, assertion.location))
        result.append({
            "source_id": assertion.source_id, "location": assertion.location,
            "old_assertion_id": assertion.assertion_id,
            "new_assertion_id": replacement.assertion_id if replacement else "MISSING",
            "changed": str(bool(replacement and replacement.assertion_id != assertion.assertion_id)).lower(),
        })
    return result


def reports(bank: dict, intake: Intake, migration: list[dict[str, str]]) -> dict[str, str]:
    sources = intake.sources
    hash_counts = Counter(s.sha256 for s in sources)
    statements_by_source = {s.source_id: {" ".join(a.text.split()) for a in intake.assertions if a.source_id == s.source_id}
                            for s in sources}
    shared_texts = set.intersection(*statements_by_source.values()) if len(statements_by_source) > 1 else set()
    inventory = ["# CV source inventory", "", bank["collection_note"], "",
                 "| Source ID | Filename | Format | SHA-256 | Bytes | Application target |",
                 "|---|---|---|---|---:|---|"]
    for source in sources:
        path = Path(source.locator)
        target = bank["application_targets"].get(source.source_id, "Unknown")
        inventory.append(f"| {source.source_id} | {source.title} | {path.suffix.lower().lstrip('.')} | {source.sha256} | {path.stat().st_size} | {target} |")
    inventory += ["", f"Identical-byte groups: {sum(n > 1 for n in hash_counts.values())}. "
                  f"Exact paragraph texts shared by every inventoried version: {len(shared_texts)}.",
                  "Distinct SHA-256 hashes indicate different files. Shared wording is not independent corroboration.",
                  "The two named documents are tailored CV versions; their chronology and completeness need candidate confirmation.",
                  "", "## Missing or inaccessible previously created versions", ""]
    inventory += [f"- {x}" for x in bank["missing_versions"]] or ["- None known from the authorised collection and prior inventory."]

    catalogue = ["# Master capability catalogue", "", "All records are CV-derived and await candidate review. Proposed wording has no usage approval.", ""]
    mapping = ["# Semantic deduplication and source mapping", "",
               "Each row is one competency. Repeated CV statements are grouped as wording variants, not independent evidence.", "",
               "| Competency | Category | Source locations | Distinct CVs |", "|---|---|---|---:|"]
    review = ["# Ambiguity and candidate-review queue", "",
              "CV-derived statements are unverified. No candidate review, evidence verification or disclosure permission is implied.", ""]
    counts = Counter()
    mapped_locations = set()
    for item in bank["competencies"]:
        counts[item["category"]] += 1
        refs = item["source_statements"]
        mapped_locations.update((s["source_id"], s["location"]) for s in refs)
        catalogue += [f"## {item['competency_id']} — {item['canonical']}", "",
                      f"Category: {item['category']} / {item['subcategory']}. Status: {item['status']}. "
                      f"Basis: {item['explicit_vs_interpreted']}.", "",
                      f"Described contribution: {item['described_contribution'] or 'Not specified in the cited statements.'}", ""]
        if item["interpretation_note"]:
            catalogue += [f"Interpretation: {item['interpretation_note']}", ""]
        for field, label in (("skills_knowledge_methods", "Skills, knowledge and methods"),
                             ("tools_technologies", "Tools"), ("industries_domains", "Domains"),
                             ("quantitative_achievements", "Quantitative statements"),
                             ("transferable_applications", "Transferable applications")):
            if item[field]:
                catalogue += [f"{label}: {', '.join(item[field])}", ""]
        catalogue += ["Source statements:", ""]
        catalogue += [f"- {s['source_id']} {s['location']} ({s['assertion_id']}): {s['text']}" for s in refs]
        catalogue.append("")
        for d in item["alternative_cv_wording"]:
            catalogue += [f"Proposed wording for {d['application']}: {d['wording']}", ""]
        locations = ", ".join(f"{s['source_id']} {s['location']}" for s in refs)
        mapping.append(f"| {item['competency_id']} — {item['canonical']} | {item['category']} | {locations} | {len({s['source_id'] for s in refs})} |")
        for ambiguity in item["ambiguities"]:
            review += [f"- **{item['competency_id']}**: {ambiguity}"]
    coverage = ["# Coverage by career category", "", "Counts are curated competencies, not proficiency or verification scores.", "",
                "| Category | Competencies |", "|---|---:|"]
    coverage += [f"| {c} | {counts[c]} |" for c in bank["taxonomy"]]
    coverage += ["", f"Total: {len(bank['competencies'])} competencies across {len(sources)} distinct CV files."]
    mapping += ["", f"Mapped {len(mapped_locations)} distinct source paragraphs from {len(intake.assertions)} extracted assertions "
                f"into {len(bank['competencies'])} competencies. Other paragraphs include headings, identity, role context, "
                "references and statements already represented by more specific anchors; the original intake remains preserved.",
                "", "## Assertion ID migration", "",
                "DOCX internal separators can change normalized text and thus Phase 0B1 assertion IDs. Source IDs and paragraph locations are unchanged.", "",
                "| Source | Paragraph | Old ID | New ID | Changed |", "|---|---|---|---|---|"]
    mapping += [f"| {m['source_id']} | {m['location']} | {m['old_assertion_id']} | {m['new_assertion_id']} | {m['changed']} |" for m in migration]
    return {
        "01_source_inventory.md": "\n".join(inventory) + "\n",
        "03_capability_catalogue.md": "\n".join(catalogue) + "\n",
        "04_semantic_mapping.md": "\n".join(mapping) + "\n",
        "05_coverage_summary.md": "\n".join(coverage) + "\n",
        "06_candidate_review_queue.md": "\n".join(review) + "\n",
    }


def create_outputs(paths: list[Path], seed_path: Path, output_dir: Path, old_intake_path: Path | None = None) -> list[Path]:
    seed = BankSeed.model_validate_json(seed_path.read_text(encoding="utf-8"))
    intake = ingest(paths)
    old = None
    if old_intake_path:
        old, errors = load_intake(old_intake_path)
        if errors:
            raise ValueError("invalid prior intake: " + "; ".join(errors))
    bank = build_bank(seed, intake)
    migration = migration_map(old, intake) if old else []
    files = reports(bank, intake, migration)
    files["02_master_capability_bank.json"] = json.dumps(bank, indent=2, ensure_ascii=False) + "\n"
    files["assertion_id_migration.json"] = json.dumps(migration, indent=2) + "\n"
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("output directory must be empty; existing private work is preserved")
    output_dir.mkdir(parents=True, exist_ok=True)
    created = []
    for name, content in files.items():
        target = output_dir / name
        target.write_text(content, encoding="utf-8")
        created.append(target)
    return created
