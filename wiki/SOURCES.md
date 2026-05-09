# `sources/` contract

Raw research artefacts that wiki pages cite — web fetches, transcripts, benchmark CSVs, model cards, RFC excerpts, vendor docs.

## Why have it

Wiki pages compress and editorialize. Months later, a future Claude often needs the original verbatim text — to re-quote it, to spot what was paraphrased away, to grep for a specific error string the wiki didn't preserve. `sources/` is that backing store.

## File naming

```
sources/YYYY-MM-DD-slug.md
```

- `YYYY-MM-DD` = date the source was fetched (not the source's publication date)
- `slug` = lowercase, hyphenated, descriptive (not the URL slug — make it readable)

Example: `sources/2026-05-09-redhat-llama-stack-responses-api-deep-dive.md`

## Required frontmatter

```markdown
---
fetched: 2026-05-09T01:22:00Z
url: https://example.com/article
fetcher: claude-code
sha256: abc123def456...
---
```

| Field | Required | Notes |
|-------|----------|-------|
| `fetched` | yes | ISO 8601 UTC timestamp |
| `url` | yes | Source URL. For non-URL sources (transcripts, screenshots), use `local:<path>` or `human:<name>` |
| `fetcher` | yes | `claude-code`, `claude-research`, `human`, or a specific tool name |
| `sha256` | yes | SHA-256 of the body (everything after the closing `---`) |

The lint script enforces these four fields. Optional fields (`title`, `author`, `accessed_via`, `license`) are fine; lint ignores them.

## Computing sha256

```bash
# Body only — strip the frontmatter first
awk '/^---$/{n++; next} n>=2' wiki/sources/2026-05-09-foo.md \
  | shasum -a 256 | awk '{print $1}'
```

Update the frontmatter with the result. The lint script recomputes and warns if it doesn't match.

## Immutability

**Sources are write-once.** Once committed, do not edit the body or the frontmatter `url`/`fetched`/`sha256`.

If the source is wrong, superseded, or has been corrected:

1. Add a sibling file `sources/YYYY-MM-DD-slug.notes.md` (no frontmatter required) with your corrections.
2. From the original source, the `notes.md` is discoverable by name; from a topic page that cites the source, link to both.

This preserves provenance. The wiki's audit trail depends on `sources/` not being rewritten.

## When to add a source

Whenever a wiki page makes a claim that derives from outside the codebase. Examples:

- Quoting a Red Hat docs page → fetch and store.
- Citing a vendor benchmark → store the raw numbers.
- Pointing at a HuggingFace model card → store the readme.
- Capturing an X/Twitter thread or a GitHub issue → store the dump.

Inline code in this repo does NOT need a source — `git blame` and the commit message are the authoritative record.

## When NOT to add a source

- A Stack Overflow answer that informed your debugging — usually not worth it; just put the takeaway in `findings.md` with a date.
- The repo's own commit history — `git log` is canonical.
- A claude-mem observation — it has its own ID and lifecycle; reference the ID in `log.md` instead.

## Discovering sources

Currently: `ls wiki/sources/`. Index pages may grow if `sources/` exceeds 50 files; until then, the directory is small enough to scan.
