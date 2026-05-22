# AI Slop Cleaner

Minimal CLI scaffold for classifying, cleaning, and restoring generated-content cleanup work.

## Usage

```bash
ai-slop classify <path>
ai-slop clean --plan <path>
ai-slop clean --apply <path>
ai-slop restore <quarantine-run-path>
```

AI Slop Cleaner is deterministic, offline, and does not delete originals.

The `classify`, `clean`, and `restore` commands are implemented and print machine-readable JSON.
