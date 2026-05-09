#!/usr/bin/env python3
"""Mechanical integrity checks for wiki/.

Checks performed:
  1. Broken internal markdown links — `[text](path.md)` where path.md doesn't exist.
  2. Orphan pages — *.md on disk under wiki/ but not linked from wiki/README.md.
     (sources/ and entities/ files are exempt; they're discovered by directory listing.)
  3. Source frontmatter — every wiki/sources/*.md must have `fetched`, `url`,
     `fetcher`, `sha256` in YAML frontmatter.
  4. Source sha256 — recompute from body, warn if it doesn't match.
  5. log.md date monotonicity — `## YYYY-MM-DD` headers must be in non-increasing order.

Exit code:
  0 if no errors, 1 if any check failed. Warnings (e.g. mismatched sha256) do not
  fail the run.

No external dependencies — pure stdlib so it works on a fresh checkout.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WIKI = REPO_ROOT / "wiki"
README = WIKI / "README.md"
LOG = WIKI / "log.md"
SOURCES_DIR = WIKI / "sources"

# Pages exempt from the orphan check (they have a different lifecycle than topic pages)
EXEMPT_DIRS = {"sources", "entities", "handbooks"}
EXEMPT_FILES = {"README.md", "log.md", "SOURCES.md"}

LINK_RE = re.compile(r"\[(?P<text>[^\]]+)\]\((?P<href>[^)]+)\)")
DATE_HEADER_RE = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)", re.DOTALL)
REQUIRED_SOURCE_FIELDS = {"fetched", "url", "fetcher", "sha256"}


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def emit(self) -> int:
        for w in self.warnings:
            print(f"WARN: {w}")
        for e in self.errors:
            print(f"FAIL: {e}")
        if self.errors:
            print(f"\n{len(self.errors)} error(s), {len(self.warnings)} warning(s).")
            return 1
        print(f"OK ({len(self.warnings)} warning(s)).")
        return 0


def find_md_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.md") if p.is_file())


def check_broken_links(report: Report) -> None:
    for md in find_md_files(WIKI):
        text = md.read_text(encoding="utf-8")
        for m in LINK_RE.finditer(text):
            href = m.group("href").strip()
            # Skip external, anchor-only, mailto, and image-style links
            if href.startswith(("http://", "https://", "mailto:", "#")):
                continue
            # Strip anchor fragment
            target = href.split("#", 1)[0]
            if not target:
                continue
            # Resolve relative to the file's directory
            resolved = (md.parent / target).resolve()
            if not resolved.exists():
                report.err(
                    f"broken link in {md.relative_to(REPO_ROOT)}: "
                    f"`{href}` → {resolved.relative_to(REPO_ROOT) if resolved.is_relative_to(REPO_ROOT) else resolved}"
                )


def check_orphans_and_unindexed(report: Report) -> None:
    if not README.exists():
        report.err(f"{README.relative_to(REPO_ROOT)} is missing")
        return

    readme_text = README.read_text(encoding="utf-8")
    referenced: set[Path] = set()
    for m in LINK_RE.finditer(readme_text):
        href = m.group("href").strip()
        if href.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target = href.split("#", 1)[0]
        if not target:
            continue
        resolved = (README.parent / target).resolve()
        if resolved.suffix == ".md":
            referenced.add(resolved)
        # Directory references like `sources/` count as covering everything underneath
        if resolved.is_dir():
            for child in resolved.rglob("*.md"):
                referenced.add(child.resolve())

    on_disk = {p.resolve() for p in find_md_files(WIKI)}
    on_disk.discard(README.resolve())  # README references itself implicitly

    # Orphans: on disk but not referenced and not in an exempt location
    for path in sorted(on_disk):
        rel = path.relative_to(WIKI)
        parts = rel.parts
        if parts[0] in EXEMPT_DIRS:
            continue
        if path.name in EXEMPT_FILES:
            continue
        if path not in referenced:
            report.err(
                f"orphan page (on disk but not linked from README.md): "
                f"{path.relative_to(REPO_ROOT)}"
            )

    # Unindexed: referenced but not on disk
    for path in sorted(referenced):
        if path.suffix != ".md":
            continue
        if not path.exists():
            report.err(
                f"unindexed page (linked from README.md but missing on disk): "
                f"{path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path}"
            )


def parse_frontmatter(text: str) -> tuple[dict[str, str], str] | None:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    fm_text, body = m.group(1), m.group(2)
    fields: dict[str, str] = {}
    for line in fm_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        fields[k.strip()] = v.strip()
    return fields, body


def check_sources(report: Report) -> None:
    if not SOURCES_DIR.exists():
        return
    for src in sorted(SOURCES_DIR.glob("*.md")):
        if src.name.endswith(".notes.md"):
            continue  # notes files are exempt from frontmatter
        text = src.read_text(encoding="utf-8")
        parsed = parse_frontmatter(text)
        if parsed is None:
            report.err(
                f"missing YAML frontmatter in {src.relative_to(REPO_ROOT)}"
            )
            continue
        fields, body = parsed
        missing = REQUIRED_SOURCE_FIELDS - fields.keys()
        if missing:
            report.err(
                f"missing required frontmatter field(s) {sorted(missing)} in "
                f"{src.relative_to(REPO_ROOT)}"
            )
            continue
        # Verify sha256
        declared = fields["sha256"].strip().strip('"').strip("'")
        actual = hashlib.sha256(body.encode("utf-8")).hexdigest()
        if declared and declared != actual:
            report.warn(
                f"sha256 mismatch in {src.relative_to(REPO_ROOT)}: "
                f"declared={declared[:12]}... actual={actual[:12]}..."
            )


def check_log_monotonic(report: Report) -> None:
    if not LOG.exists():
        report.err(f"{LOG.relative_to(REPO_ROOT)} is missing")
        return
    dates: list[tuple[int, str]] = []
    for i, line in enumerate(LOG.read_text(encoding="utf-8").splitlines(), start=1):
        m = DATE_HEADER_RE.match(line)
        if m:
            dates.append((i, m.group(1)))
    # Newest first → dates should be non-increasing
    for (lineno_a, a), (lineno_b, b) in zip(dates, dates[1:]):
        if a < b:
            report.err(
                f"log.md dates out of order: {a} (line {lineno_a}) precedes "
                f"newer {b} (line {lineno_b}). Newest entries go on top."
            )


def main() -> int:
    if not WIKI.exists():
        print(f"FAIL: {WIKI.relative_to(REPO_ROOT)} does not exist")
        return 1
    report = Report()
    check_broken_links(report)
    check_orphans_and_unindexed(report)
    check_sources(report)
    check_log_monotonic(report)
    return report.emit()


if __name__ == "__main__":
    sys.exit(main())
