from __future__ import annotations

import hashlib
from pathlib import Path

from ai_slop_cleaner.models import MANIFEST_NAME, DocumentRecord
from ai_slop_cleaner.text_utils import (
    extract_headings,
    extract_references,
    extract_title,
    is_binary_bytes,
    normalize_text,
    split_frontmatter,
    strip_fenced_code_blocks,
)

IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".ai-slop",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}
DOCUMENT_EXTENSIONS = {
    ".adoc",
    ".asciidoc",
    ".doc",
    ".docx",
    ".md",
    ".markdown",
    ".mdx",
    ".odt",
    ".org",
    ".pdf",
    ".rst",
    ".txt",
}


def scan_documents(target: str | Path, *, max_bytes: int = 1_000_000) -> list[DocumentRecord]:
    root = Path(target).resolve()
    records: list[DocumentRecord] = []

    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        if _is_ignored(path, root):
            continue
        records.append(_scan_file(path, root, max_bytes=max_bytes))

    return records


def _is_ignored(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if path.name == MANIFEST_NAME:
        return True
    if any(part in IGNORE_DIRS for part in relative.parts):
        return True
    return path.suffix.lower() not in DOCUMENT_EXTENSIONS


def _scan_file(path: Path, root: Path, *, max_bytes: int) -> DocumentRecord:
    try:
        stat = path.stat()
    except OSError:
        return _error_record(path, root, None, 0, 0.0, path.suffix.lower(), "read_error")

    relative_path = path.relative_to(root).as_posix()
    extension = path.suffix.lower()

    if stat.st_size > max_bytes:
        return DocumentRecord(
            relative_path=relative_path,
            absolute_path=str(path),
            hash=None,
            size=stat.st_size,
            mtime=stat.st_mtime,
            extension=extension,
            title=None,
            frontmatter={},
            body_text="",
            normalized_text="",
            headings=[],
            references=[],
            errors=["oversized_file"],
        )

    file_hash = _hash_file(path)

    try:
        raw = path.read_bytes()
    except OSError:
        return _error_record(path, root, file_hash, stat.st_size, stat.st_mtime, extension, "read_error")

    if is_binary_bytes(raw):
        return _error_record(path, root, file_hash, stat.st_size, stat.st_mtime, extension, "binary_file")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return _error_record(path, root, file_hash, stat.st_size, stat.st_mtime, extension, "decode_error")

    frontmatter, body = split_frontmatter(text)
    fact_body = strip_fenced_code_blocks(body)
    return DocumentRecord(
        relative_path=relative_path,
        absolute_path=str(path),
        hash=file_hash,
        size=stat.st_size,
        mtime=stat.st_mtime,
        extension=extension,
        title=extract_title(frontmatter, fact_body),
        frontmatter=frontmatter,
        body_text=fact_body,
        normalized_text=normalize_text(body),
        headings=extract_headings(fact_body),
        references=extract_references(fact_body),
        errors=[],
    )


def _error_record(
    path: Path,
    root: Path,
    file_hash: str | None,
    size: int,
    mtime: float,
    extension: str,
    error: str,
) -> DocumentRecord:
    return DocumentRecord(
        relative_path=path.relative_to(root).as_posix(),
        absolute_path=str(path),
        hash=file_hash,
        size=size,
        mtime=mtime,
        extension=extension,
        title=None,
        frontmatter={},
        body_text="",
        normalized_text="",
        headings=[],
        references=[],
        errors=[error],
    )


def _hash_file(path: Path) -> str | None:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()
