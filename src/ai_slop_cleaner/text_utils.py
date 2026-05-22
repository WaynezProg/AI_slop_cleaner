from __future__ import annotations

import re

FRONTMATTER_BOUNDARY = "---"


def normalize_text(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"```.*?```", " ", lowered, flags=re.DOTALL)
    lowered = re.sub(r"[^\w\s-]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def strip_fenced_code_blocks(text: str) -> str:
    return re.sub(r"```.*?```", " ", text, flags=re.DOTALL)


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_BOUNDARY:
        return {}, text

    frontmatter: dict[str, str] = {}
    body_start = 0
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == FRONTMATTER_BOUNDARY:
            body_start = index + 1
            break
        if ":" in line:
            key, value = line.split(":", 1)
            clean_key = key.strip()
            clean_value = value.strip().strip("\"'")
            if clean_key:
                frontmatter[clean_key] = clean_value

    if body_start == 0:
        return {}, text
    return frontmatter, "\n".join(lines[body_start:])


def extract_headings(text: str) -> list[str]:
    headings: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
        if match:
            headings.append(match.group(1).strip())
    return headings


def extract_title(frontmatter: dict[str, str], text: str) -> str | None:
    if frontmatter.get("title"):
        return frontmatter["title"]
    headings = extract_headings(text)
    if headings:
        return headings[0]
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:120]
    return None


def extract_references(text: str) -> list[str]:
    markdown_refs = re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
    wiki_refs = re.findall(r"\[\[([^\]]+)\]\]", text)
    refs = [ref.strip() for ref in markdown_refs + wiki_refs if ref.strip()]
    return sorted(set(refs))


def is_binary_bytes(raw: bytes) -> bool:
    return b"\x00" in raw
