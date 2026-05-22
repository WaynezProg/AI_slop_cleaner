# AI Slop Cleaner

AI Slop Cleaner is a CLI-first context hygiene tool for coding agents.

It classifies project documents before an agent reads them, writes a traceable manifest, and can move safe cleanup candidates into quarantine. It never deletes files in v1.

V1 is a CLI scaffold, not a production-ready document parser.

## Install For Local Development

```bash
uv sync
```

## Commands

```bash
ai-slop classify <path>
ai-slop clean --plan <path>
ai-slop clean --apply <path>
ai-slop restore <quarantine-run-path>
```

## Agent Usage Timing

An agent should run:

```bash
ai-slop classify <project-path>
```

before building context from a project folder.

If any included file is added, removed, renamed, or modified after `ai-slop-manifest.json` was generated, the agent should rerun `classify`.

`clean --plan` and `clean --apply` refuse stale manifests unless `--rescan` is passed.

`clean --apply` rewrites `ai-slop-manifest.json` after files are moved, so the remaining project documents have a current manifest.

## Document Scope

Version 1 only considers document-like extensions:

```text
.adoc .asciidoc .doc .docx .md .markdown .mdx .odt .org .pdf .rst .txt
```

Content extraction is UTF-8 text only. Binary formats such as `.pdf`, `.docx`, `.doc`, and `.odt` are recognized by extension, but v1 does not parse their internal content. Files that are binary or cannot be decoded are marked `needs_review`.

Repository control files such as `.gitignore`, `.python-version`, lock files, config files, source files, dependency folders, build folders, and `.ai-slop` internals are outside the classification scope.

## Categories

Manifest categories:

```json
{
  "canonical": [],
  "duplicate": [],
  "stale": [],
  "conflict": [],
  "low_value": [],
  "needs_review": []
}
```

Agents should prefer `canonical`, avoid `duplicate`, `stale`, and `low_value`, and ask for human review before relying on `conflict` or `needs_review`.

## Cleanup

Preview cleanup:

```bash
ai-slop clean --plan <project-path>
```

Move safe candidates:

```bash
ai-slop clean --apply <project-path>
```

Eligible categories are `duplicate`, `stale`, and `low_value`.

Quarantined files move to:

```text
.ai-slop/quarantine/<timestamp>/<original-relative-path>
```

Restore one quarantine run:

```bash
ai-slop restore <project-path>/.ai-slop/quarantine/<timestamp>
```

Restore never overwrites an existing destination path.

## V1 Boundaries

Version 1 is deterministic and offline. It does not call external LLM APIs, does not call embedding providers, does not delete files, and does not include an IDE extension or MCP server implementation.

Not implemented in v1: native PDF parsing, native Word/OpenDocument parsing, OCR, semantic embeddings, and full multilingual requirement extraction.
