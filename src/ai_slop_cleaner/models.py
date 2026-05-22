from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Category = Literal["canonical", "duplicate", "stale", "conflict", "low_value", "needs_review"]

CATEGORIES: tuple[Category, ...] = (
    "canonical",
    "duplicate",
    "stale",
    "conflict",
    "low_value",
    "needs_review",
)

MOVABLE_CATEGORIES: frozenset[Category] = frozenset({"duplicate", "stale", "low_value"})
MANIFEST_NAME = "ai-slop-manifest.json"


@dataclass(frozen=True)
class DocumentRecord:
    relative_path: str
    absolute_path: str
    hash: str | None
    size: int
    mtime: float
    extension: str
    title: str | None
    frontmatter: dict[str, str]
    body_text: str
    normalized_text: str
    headings: list[str]
    references: list[str]
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ClassificationResult:
    path: str
    category: Category
    confidence: float
    signals: list[dict[str, Any]]
    reason: str
    related_files: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_manifest_entry(self, record: DocumentRecord) -> dict[str, Any]:
        entry = asdict(self)
        entry.update(
            {
                "hash": record.hash,
                "size": record.size,
                "mtime": record.mtime,
                "title": record.title,
                "extension": record.extension,
            }
        )
        return entry
