"""Offline, deliberately literal extraction of untrusted source text.

No source text is executed, interpreted as a prompt, or considered verified.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from .review import Assertion, Intake, SourceDocument, find_conflicts, validate_intake


FIELD_NAMES = {
    "employment date", "job title", "quantitative achievement", "project description",
    "attribution", "skill proficiency", "qualification", "credential",
}


def stable_id(prefix: str, value: bytes) -> str:
    return f"{prefix}-{hashlib.sha256(value).hexdigest()[:20]}"


def _paragraphs(path: Path) -> list[tuple[str, str]]:
    suffix = path.suffix.casefold()
    if suffix in {".txt", ".md"}:
        text = path.read_text(encoding="utf-8-sig")
        return [(f"line:{i}", line.strip()) for i, line in enumerate(text.splitlines(), 1) if line.strip()]
    if suffix == ".docx":
        try:
            with zipfile.ZipFile(path) as archive:
                xml = archive.read("word/document.xml")
            root = ElementTree.fromstring(xml)
            word_ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            if root.tag != f"{{{word_ns}}}document" or root.find(f"{{{word_ns}}}body") is None:
                raise ValueError("DOCX document XML lacks a Word document body")
        except (zipfile.BadZipFile, KeyError, RuntimeError, ElementTree.ParseError) as exc:
            raise ValueError("DOCX archive or document XML is invalid") from exc
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs = []
        for i, paragraph in enumerate(root.findall(".//w:body//w:p", ns), 1):
            value = "".join(node.text or "" for node in paragraph.findall(".//w:t", ns)).strip()
            if value:
                paragraphs.append((f"paragraph:{i}", value))
        return paragraphs
    if suffix == ".pdf":
        try:
            result = subprocess.run(
                ["pdftotext", "-layout", str(path), "-"],
                check=True, capture_output=True, text=True, timeout=30,
            )
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise ValueError(f"PDF text extraction failed: {exc}") from exc
        if not result.stdout.strip():
            raise ValueError("PDF has no extractable text; OCR is unsupported")
        return [
            (f"page:{page_no}/line:{line_no}", line.strip())
            for page_no, page in enumerate(result.stdout.split("\f"), 1)
            for line_no, line in enumerate(page.splitlines(), 1)
            if line.strip()
        ]
    raise ValueError(f"unsupported source format: {suffix}")


def _field(text: str) -> tuple[str | None, str | None]:
    # A label is a grouping hint for review, never a semantic truth judgement.
    match = re.fullmatch(r"\s*([^:]{1,80}):\s*(.+?)\s*", text)
    if match and match.group(1).strip().casefold() in FIELD_NAMES:
        return match.group(1).strip().casefold(), match.group(2).strip()
    return None, None


def ingest(paths: list[Path], *, supersedes: dict[str, str] | None = None) -> Intake:
    """Create a new unreviewed intake from local files, deduplicated by bytes."""
    sources: list[SourceDocument] = []
    assertions: list[Assertion] = []
    seen: set[str] = set()
    supersedes = supersedes or {}
    unknown_names = set(supersedes) - {path.name for path in paths}
    if unknown_names:
        raise ValueError(f"--supersedes refers to an input filename not provided: {', '.join(sorted(unknown_names))}")
    for path in paths:
        raw = path.read_bytes()
        source_id = stable_id("src", raw)
        if source_id in seen:
            continue
        seen.add(source_id)
        chunks = _paragraphs(path)
        sources.append(SourceDocument(
            source_id=source_id, title=path.name, locator=str(path.resolve()),
            sha256=hashlib.sha256(raw).hexdigest(),
            supersedes_source_id=supersedes.get(path.name),
        ))
        repeated: dict[str, int] = {}
        for location, content in chunks:
            normalized = " ".join(content.split())
            repeated[normalized] = repeated.get(normalized, 0) + 1
            sequence = repeated[normalized]
            assertion_id = stable_id("asrt", f"{source_id}\0{normalized}\0{sequence}".encode())
            field, value = _field(content)
            assertions.append(Assertion(
                assertion_id=assertion_id, source_id=source_id, location=location,
                text=content, field=field, value=value,
            ))
    intake = Intake(sources=sources, assertions=assertions, conflicts=find_conflicts(assertions))
    errors = validate_intake(intake)
    if errors:
        raise ValueError("; ".join(errors))
    return intake
