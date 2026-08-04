"""Structural floor for every ratified ADR (DOC-01).

Guards D-10 (individually-written ADRs with genuine Context/Decision/Consequences prose, not
batch rubber-stamping) and the "one ADR per OD, never merged" invariant. A stub ADR — one with
an empty section, a missing heading, or fewer than 25 non-blank lines — fails this suite.
"""

from pathlib import Path

import pytest

ADR_DIR = Path(__file__).resolve().parents[2] / "docs" / "adr"

# The ten open decisions ratified by this phase (DOC-01).
ADR_NUMBERS = [f"{n:03d}" for n in range(1, 11)]

REQUIRED_HEADINGS = ["## Status", "## Context", "## Decision", "## Consequences"]

MIN_NON_BLANK_LINES = 25


def _resolve_adr_file(number: str) -> Path:
    """Resolve exactly one docs/adr/{number}-*.md file for the given zero-padded number.

    Asserting exactly one match is what enforces one-ADR-per-OD: zero matches means the OD was
    never ratified, and more than one match means two ODs were merged into a single numbered
    slot or a duplicate file was left behind.
    """
    matches = sorted(ADR_DIR.glob(f"{number}-*.md"))
    assert len(matches) == 1, (
        f"expected exactly one ADR file for number {number!r}, found {len(matches)}: {matches}"
    )
    return matches[0]


def _non_blank_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip()]


def _section_bodies(text: str) -> dict[str, list[str]]:
    """Split the file into heading -> body-lines-until-next-heading.

    A "heading" here is any line starting with "## " (the ADR's own five top-level sections).
    The body of a heading is every non-blank line strictly between it and the next such heading
    (or end of file), excluding the heading line itself.
    """
    lines = text.splitlines()
    heading_indices = [i for i, line in enumerate(lines) if line.startswith("## ")]
    bodies: dict[str, list[str]] = {}
    for idx, start in enumerate(heading_indices):
        heading = lines[start].strip()
        end = heading_indices[idx + 1] if idx + 1 < len(heading_indices) else len(lines)
        body_lines = [
            line for line in lines[start + 1 : end] if line.strip() and not line.startswith("## ")
        ]
        bodies[heading] = body_lines
    return bodies


@pytest.mark.parametrize("number", ADR_NUMBERS)
def test_adr_file_exists_exactly_once(number: str) -> None:
    """Every OD number 001..010 resolves to exactly one ADR file (no gaps, no merges)."""
    _resolve_adr_file(number)


@pytest.mark.parametrize("number", ADR_NUMBERS)
def test_adr_has_required_headings(number: str) -> None:
    adr_file = _resolve_adr_file(number)
    text = adr_file.read_text(encoding="utf-8")
    for heading in REQUIRED_HEADINGS:
        assert heading in text, f"{adr_file.name} is missing required heading {heading!r}"


@pytest.mark.parametrize("number", ADR_NUMBERS)
def test_adr_section_bodies_are_non_empty(number: str) -> None:
    """Each required section must contain real prose, not just a bare heading.

    This is what catches a stub ADR that only restates the recommendation sentence: an ADR with
    an empty `## Consequences` section (heading present, zero body lines before the next
    heading) fails here even though test_adr_has_required_headings would pass.
    """
    adr_file = _resolve_adr_file(number)
    text = adr_file.read_text(encoding="utf-8")
    bodies = _section_bodies(text)
    for heading in REQUIRED_HEADINGS:
        assert heading in bodies, f"{adr_file.name} heading {heading!r} not found during body scan"
        assert len(bodies[heading]) >= 1, (
            f"{adr_file.name} section {heading!r} has no non-blank content before the next heading"
        )


@pytest.mark.parametrize("number", ADR_NUMBERS)
def test_adr_meets_minimum_length_floor(number: str) -> None:
    adr_file = _resolve_adr_file(number)
    text = adr_file.read_text(encoding="utf-8")
    non_blank = _non_blank_lines(text)
    assert len(non_blank) >= MIN_NON_BLANK_LINES, (
        f"{adr_file.name} has only {len(non_blank)} non-blank lines "
        f"(minimum {MIN_NON_BLANK_LINES}) — looks like a stub"
    )


def test_adr_filenames_sort_lexicographically_in_decision_order() -> None:
    """Zero-padded ADR filenames must sort the same way lexicographically and numerically.

    This is what the zero-padding (001..010, not 1..10) guarantees: a plain `ls docs/adr/`
    directory listing shows the ADRs in decision order without any numeric-aware sort.
    """
    files = sorted(ADR_DIR.glob("[0-9][0-9][0-9]-*.md"))
    assert len(files) == 10, f"expected 10 ADR files, found {len(files)}: {files}"

    lexicographic_order = [f.name for f in sorted(files, key=lambda p: p.name)]
    numeric_order = [f.name for f in sorted(files, key=lambda p: int(p.name.split("-", 1)[0]))]

    assert lexicographic_order == numeric_order, (
        "ADR filenames do not sort identically by lexicographic and numeric order — "
        "zero-padding is broken somewhere in docs/adr/"
    )
