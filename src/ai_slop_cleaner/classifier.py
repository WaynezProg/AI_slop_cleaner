from __future__ import annotations

from collections import defaultdict

from ai_slop_cleaner.models import ClassificationResult, DocumentRecord


CANONICAL_FILENAME_HINTS = ("final", "current", "latest")
NON_CANONICAL_FILENAME_HINTS = ("copy", "draft", "old")


def classify_records(records: list[DocumentRecord]) -> list[ClassificationResult]:
    results_by_path: dict[str, ClassificationResult] = {}
    hash_groups: dict[str, list[DocumentRecord]] = defaultdict(list)

    for record in records:
        if record.errors:
            results_by_path[record.relative_path] = ClassificationResult(
                path=record.relative_path,
                category="needs_review",
                confidence=1.0,
                signals=[{"name": "scanner_error", "errors": list(record.errors)}],
                reason="Scanner reported errors for this file.",
                errors=list(record.errors),
            )
            continue
        if record.hash is not None:
            hash_groups[record.hash].append(record)

    for group in hash_groups.values():
        if len(group) < 2:
            continue

        canonical = _choose_exact_hash_canonical(group)
        duplicate_paths = sorted(record.relative_path for record in group if record != canonical)
        results_by_path[canonical.relative_path] = ClassificationResult(
            path=canonical.relative_path,
            category="canonical",
            confidence=0.6,
            signals=[{"name": "default_canonical"}],
            reason="Selected as canonical representative for an exact hash group.",
            related_files=duplicate_paths,
        )

        for duplicate in group:
            if duplicate == canonical:
                continue
            results_by_path[duplicate.relative_path] = ClassificationResult(
                path=duplicate.relative_path,
                category="duplicate",
                confidence=0.99,
                signals=[
                    {
                        "name": "exact_hash_duplicate",
                        "canonical_path": canonical.relative_path,
                        "hash": duplicate.hash,
                    }
                ],
                reason=f"Exact content hash matches {canonical.relative_path}.",
                related_files=[canonical.relative_path],
            )

    for record in records:
        if record.relative_path in results_by_path:
            continue
        results_by_path[record.relative_path] = ClassificationResult(
            path=record.relative_path,
            category="canonical",
            confidence=0.6,
            signals=[{"name": "default_canonical"}],
            reason="No duplicate or review signals matched.",
        )

    return [results_by_path[path] for path in sorted(results_by_path)]


def _choose_exact_hash_canonical(records: list[DocumentRecord]) -> DocumentRecord:
    return min(records, key=_canonical_sort_key)


def _canonical_sort_key(record: DocumentRecord) -> tuple[int, int, float, int, str]:
    return (
        -_frontmatter_canonical_score(record),
        -_filename_hint_score(record),
        -record.mtime,
        -len(record.references),
        record.relative_path,
    )


def _frontmatter_canonical_score(record: DocumentRecord) -> int:
    frontmatter = {
        key.lower(): value.lower()
        for key, value in record.frontmatter.items()
    }
    score = 0
    if frontmatter.get("status") in {"canonical", "current", "final"}:
        score += 3
    if frontmatter.get("canonical") in {
        "true",
        "yes",
        "1",
        "canonical",
        "current",
        "final",
    }:
        score += 4
    return score


def _filename_hint_score(record: DocumentRecord) -> int:
    name = record.relative_path.rsplit("/", maxsplit=1)[-1].lower()
    score = 0
    if any(hint in name for hint in CANONICAL_FILENAME_HINTS):
        score += 1
    if any(hint in name for hint in NON_CANONICAL_FILENAME_HINTS):
        score -= 1
    return score
