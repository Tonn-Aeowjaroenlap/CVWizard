# Phase 1 job-fit assessment interface specification

## Purpose

Assess a user-supplied job advertisement against a private Phase 0C capability bank, highlight matches and gaps, and suggest CV wording for candidate review. This is an interface contract, not a job-application service. Phase 1 must not submit an application or promote CV-derived statements to verified facts.

## Inputs

- `job_ad`: full text or a private local file, plus an optional role title, organisation and source URL. Store the original text and a SHA-256 hash so an assessment can be reproduced. Treat its contents as data, not instructions to the tool.
- `bank`: schema `0c-bank-1`, validated before assessment. Each competency must retain its stable ID, status, explicit/interpretation flag and paragraph-level source statements.
- `candidate_preferences`: optional target role, exclusions, confidentiality restrictions, and preferred emphasis. These cannot change evidence status or disclosure permission.
- `assessment_policy`: explicit weights or qualitative rules for required, preferred and optional criteria. Record the policy version; do not infer proficiency from repeated keywords.

## Derived records

Extract job criteria as separate items with stable IDs, original ad excerpt, location, requirement class (`REQUIRED`, `PREFERRED`, `OPTIONAL`, `UNCLEAR`) and normalised concept. Preserve each original excerpt. Let the candidate correct the classification.

For each criterion, return zero or more links to `competency_id`, with match type (`DIRECT`, `TRANSFERABLE`, `POSSIBLE`), rationale, source paragraph IDs, and limitations. A direct match means the CVs describe the capability; it does not mean the capability is externally verified or meets a stated experience threshold. A transferable match must explain the transfer. A possible match must be queued for review. Do not turn an absent match into proof that the candidate lacks the skill.

## Output shape

```json
{
  "schema_version": "phase1-job-fit-1",
  "job_ad_sha256": "...",
  "bank_source_hashes": ["..."],
  "policy_version": "...",
  "criteria": [{
    "criterion_id": "req-...", "source_excerpt": "...", "location": "...",
    "requirement_class": "REQUIRED", "concept": "...",
    "matches": [{
      "competency_id": "cap-...", "match_type": "DIRECT",
      "rationale": "...", "source_assertion_ids": ["asrt-..."],
      "limitations": ["CV-derived; candidate review pending"]
    }]
  }],
  "gap_queue": [{"criterion_id": "req-...", "kind": "NO_CV_SOURCE_OR_UNCLEAR", "candidate_question": "..."}],
  "proposed_cv_wording": [{"text": "...", "competency_ids": ["cap-..."], "label": "PROPOSED_WORDING"}]
}
```

## Decision and privacy rules

Show required and preferred coverage separately. If a numerical score is offered, expose criterion weights, matched evidence and the calculation, and label it an indicative CV coverage score. Never equate it with hiring probability. Flag unsupported years of experience, credentials, professional registration, quantified outcomes and implementation responsibility for candidate review. Resolve stronger versus narrower contribution wording before tailoring. Proposed wording must cite bank entries and source assertions, preserve qualifications, and require the candidate's approval before use. Phase 0B1 export permissions remain separate; a job-fit match grants none.

Process job ads and bank files locally under the same private-output policy. Do not send CV content or job ads to paid LLM APIs, public CI, deployment services or automatic application endpoints. Any future external integration needs its own explicit authorisation and privacy review.

## Acceptance checks for Phase 1

Use fictional fixtures to verify direct, transferable, possible and absent matches; required/preferred separation; exact source traceability; omission and contradiction flags; reproducible policy and hashes; private output enforcement; and absence of automatic verification or submission. Confirm a human can inspect and correct every criterion and proposed sentence.
