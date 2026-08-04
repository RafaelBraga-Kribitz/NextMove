"""Event ingestion: Pydantic contract validation, Pandera semantic checks, and
quarantine routing for contract violations.

Populated starting Phase 1.
"""

from nextmove.ingest.contracts import (
    CANONICAL_SORT_KEY,
    CONTRACT_VERSION,
    Event,
    EventPayload,
    EventType,
    derive_event_id,
    sort_events,
)

__all__: list[str] = [
    "CANONICAL_SORT_KEY",
    "CONTRACT_VERSION",
    "Event",
    "EventPayload",
    "EventType",
    "derive_event_id",
    "sort_events",
]
