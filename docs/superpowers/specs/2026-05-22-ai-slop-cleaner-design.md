# AI Slop Cleaner Design

Date: 2026-05-22
Status: Draft for user review

## Goal

AI Slop Cleaner gives coding agents a deterministic gate before they read a project folder. It scans documents, classifies stale or low-value material, writes a traceable manifest, and can move safe cleanup candidates into quarantine.

The goal is not to build a knowledge base. The goal is to stop Codex, Claude, Qwen, or another agent from treating old drafts, duplicates, generated summaries, and conflicting specs as equally trustworthy context.

## Product Scope

Version 1 is CLI-first. MCP is intentionally delayed until the core contract is stable, but the core API must be written so an MCP `classify_documents` tool can wrap it later without reimplementing classification.

Version 1 supports:

- `classify`: scan a folder and write `ai-slop-manifest.json`
- `clean --plan`: show which files would be moved
- `clean --apply`: move safe candidates into quarantine
- `restore`: move quarantined files back to their original paths

Version 1 does not delete files, call external LLM APIs, call embedding providers, or make IDE-specific assumptions.

## Usage Timing Contract

Agents must run `classify` before building context from a project folder. The tool is a pre-read gate, not an afterthought once the agent has already consumed the folder.

Agents must rerun `classify` when any included document is added, removed, renamed, or modified after the manifest timestamp. If the manifest is missing or older than the scanned files, agents must treat it as stale and regenerate it before deciding which files to read.

`clean --plan` and `clean --apply` must use a current manifest. If the manifest is stale, the CLI should fail with a clear error unless the user passes an explicit rescan option.

Automatic filesystem watch mode is not part of v1. The v1 contract is command-triggered: agents call it at the required moments, and later integrations can add watch or scheduled rerun behavior on top.

## Architecture

The project is a Python package managed by `uv`.

Core modules:

- `scanner`: walks a target directory and extracts file facts
- `classifier`: assigns categories using deterministic signals
- `manifest_writer`: writes the context contract
- `quarantine`: plans, applies, and restores file moves
- `cli`: exposes commands for humans and agents

The CLI calls the same core functions that a later MCP server will call. The core must not depend on terminal output, interactive prompts, or MCP transport.

## Data Flow

`scanner` receives a target directory and returns document records. Each record includes path, hash, size, mtime, extension, title, frontmatter, normalized text fingerprint, headings, outbound local references, and scan errors.

`classifier` receives document records and returns classification results. It groups exact duplicates by hash, near duplicates by normalized text similarity, stale candidates by filename/version/date/mtime signals, and conflict candidates by deterministic contradiction patterns.

`manifest_writer` writes a JSON manifest with one entry per scanned file plus category buckets.

`quarantine` reads a manifest, chooses safe movable categories, and writes a move log under `.ai-slop/quarantine/<timestamp>/`.

## Categories

The manifest uses fixed categories:

- `canonical`
- `duplicate`
- `stale`
- `conflict`
- `low_value`
- `needs_review`

Only `duplicate`, `stale`, and `low_value` are movable by default. `canonical`, `conflict`, and `needs_review` are never moved automatically.

## Classification Signals

Version 1 is deterministic-first and offline.

Signals include:

- exact content hash
- normalized text similarity
- filename hints such as `old`, `draft`, `copy`, `v1`, `v2`, `final`, dates, and language variants
- mtime and size
- Markdown or YAML frontmatter such as `title`, `source`, `status`, and `canonical`
- heading/title match
- local reference authority, where files referenced by many others are less likely to be stale
- generated-noise patterns such as generic AI summary titles, empty boilerplate, or low-information files
- contradiction patterns for direct conflicts, such as opposite requirement statements in files with similar titles

LLM judging and embedding providers are not part of v1. The code should leave a clean extension point, but the default system must work offline.

## Manifest Contract

The default manifest path is `<target>/ai-slop-manifest.json`.

The manifest includes:

- schema version
- target path
- generated timestamp
- scanner configuration
- category buckets
- per-file entries

Each file entry includes:

- path
- category
- confidence
- signals
- reason
- hash
- size
- mtime
- related files
- errors, if any

The manifest is an agent contract. An agent should prefer `canonical`, avoid `duplicate`, `stale`, and `low_value`, and ask the user before relying on `conflict` or `needs_review`.

## Quarantine Contract

`clean --plan` prints and writes a cleanup plan without moving files.

`clean --apply` moves eligible files to:

`.ai-slop/quarantine/<timestamp>/<original-relative-path>`

It also writes:

- `move-log.json`: original path, quarantine path, category, reason, confidence, timestamp
- `manifest.json`: the manifest used for the move

`restore` reads `move-log.json` and moves files back to their original paths. If a destination already exists, restore must stop for that file and mark it as `needs_review` instead of overwriting.

## Error Handling

The scanner must continue when one file fails. Binary, unreadable, oversized, unsupported, or decode-failed files become `needs_review` with an error signal.

Classification confidence must be explicit. Low-confidence stale or duplicate decisions become `needs_review` instead of being moved.

Quarantine operations must be reversible and conservative. The tool must never delete files in v1.

## Testing Strategy

Tests focus on external behavior and contract stability.

Required tests:

- same content with different filenames becomes `duplicate`
- newer spec supersedes older spec and older file becomes `stale`
- conflicting requirement documents become `conflict` or `needs_review`
- generated summary or boilerplate becomes `low_value`
- unreadable, binary, or oversized files become `needs_review`
- `clean --plan` does not move files
- `clean --apply` moves only eligible categories
- `restore` restores files without overwriting existing paths

Tests should use pytest fixtures with real temporary directories and real files. Prompt internals are out of scope because v1 does not use prompts.

## Implementation Notes

The CLI should be stable before MCP is added.

Initial commands:

```bash
ai-slop classify <path>
ai-slop clean --plan <path>
ai-slop clean --apply <path>
ai-slop restore <quarantine-run-path>
```

The later MCP tool should expose:

```text
classify_documents(path, write_manifest=true)
```

It should return the same manifest structure as the CLI.

## Out of Scope

Version 1 excludes:

- automatic deletion
- full IDE extension
- external LLM or embedding API dependency
- global knowledge base
- automatic merge or rewrite of conflicting documents
- hidden cleanup decisions without manifest evidence
