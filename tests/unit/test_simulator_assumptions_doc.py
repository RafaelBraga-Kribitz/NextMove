"""Structural floor check for `docs/SIMULATOR_ASSUMPTIONS.md` (SIM-03).

Does not judge prose quality -- only the properties that keep the document from silently going
stale: every required heading is present in the declared order, every section has real body
content, the file is substantial, it names every top-level `simulator:` config key, it mentions
the phrase "in simulation", it names the fatigue loophole, and `## Known Limitations` states the
`uplift_snapshot_every_ticks` sampling cadence explicitly (MEDIUM-4).
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = REPO_ROOT / "docs" / "SIMULATOR_ASSUMPTIONS.md"
SIMULATOR_CONFIG_PATH = REPO_ROOT / "config" / "simulator.yaml"

REQUIRED_HEADINGS = [
    "World Structure",
    "Latent Traits",
    "Seasonality",
    "Inventory",
    "Campaigns",
    "Organic Behaviour",
    "Micro-Conversion Events",
    "Action Response",
    "The Fatigue Loophole",
    "Determinism",
    "Known Limitations",
]


def _doc_text() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def _heading_line_numbers(text: str) -> list[tuple[str, int]]:
    matches = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        m = re.match(r"^## (.+)$", line)
        if m:
            matches.append((m.group(1).strip(), lineno))
    return matches


def _sections(text: str) -> dict[str, list[str]]:
    """Map each required heading to the list of non-blank, non-heading lines in its body,
    up to (not including) the next `## ` heading."""
    lines = text.splitlines()
    heading_positions = [
        (m.group(1).strip(), i)
        for i, line in enumerate(lines)
        if (m := re.match(r"^## (.+)$", line))
    ]
    sections: dict[str, list[str]] = {}
    for idx, (name, start) in enumerate(heading_positions):
        end = heading_positions[idx + 1][1] if idx + 1 < len(heading_positions) else len(lines)
        body = [line for line in lines[start + 1 : end] if line.strip()]
        sections[name] = body
    return sections


def test_doc_exists():
    assert DOC_PATH.is_file()


def test_required_headings_present_in_declared_order():
    text = _doc_text()
    found = [name for name, _ in _heading_line_numbers(text)]
    # The declared headings must appear, in order, as a subsequence of the document's H2s.
    it = iter(found)
    for heading in REQUIRED_HEADINGS:
        assert heading in it, (
            f"heading {heading!r} missing or out of order; document headings were: {found}"
        )


def test_every_section_has_non_blank_body_content():
    sections = _sections(_doc_text())
    for heading in REQUIRED_HEADINGS:
        assert heading in sections, f"section {heading!r} not found"
        assert sections[heading], f"section {heading!r} has no body content"


def test_minimum_non_blank_line_count():
    text = _doc_text()
    non_blank = [line for line in text.splitlines() if line.strip()]
    assert len(non_blank) >= 120, f"expected >= 120 non-blank lines, got {len(non_blank)}"


def test_mentions_in_simulation_phrase():
    assert "in simulation" in _doc_text()


def test_names_every_top_level_simulator_config_key():
    config = yaml.safe_load(SIMULATOR_CONFIG_PATH.read_text())
    keys = list(config["simulator"].keys())
    assert keys, "config/simulator.yaml has no simulator: keys to check against"
    text = _doc_text()
    missing = [key for key in keys if key not in text]
    assert not missing, f"the following simulator.yaml keys are undocumented: {missing}"


def test_known_limitations_states_uplift_snapshot_cadence():
    sections = _sections(_doc_text())
    known_limitations_text = "\n".join(sections["Known Limitations"])
    assert "uplift_snapshot_every_ticks" in known_limitations_text


def test_mentions_fatigue_loophole_and_v2_probe():
    text = _doc_text()
    assert "loophole" in text.lower()
    assert "v2" in text.lower()


def test_states_phase_1_emits_raw_micro_events_only():
    text = _doc_text().lower()
    assert "raw micro-events only" in text or "raw micro-conversion events only" in text
    assert "micro-action-to-conversion weight" in text or "micro-conversion weight" in text
