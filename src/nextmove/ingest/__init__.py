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
from nextmove.ingest.pipeline import IngestResult, PipelineStage, RejectRecord, ingest_events
from nextmove.ingest.quality import RejectRateExceeded, evaluate_reject_rate, format_dq_summary
from nextmove.ingest.semantic import (
    SEMANTIC_GATES,
    CatalogIndex,
    GateResult,
    SessionMonotonicityTracker,
    build_catalog_index,
    run_semantic_gates,
)

__all__: list[str] = [
    "CANONICAL_SORT_KEY",
    "CONTRACT_VERSION",
    "SEMANTIC_GATES",
    "CatalogIndex",
    "Event",
    "EventPayload",
    "EventType",
    "GateResult",
    "IngestResult",
    "PipelineStage",
    "RejectRateExceeded",
    "RejectRecord",
    "SessionMonotonicityTracker",
    "build_catalog_index",
    "derive_event_id",
    "evaluate_reject_rate",
    "format_dq_summary",
    "ingest_events",
    "run_semantic_gates",
    "sort_events",
]
