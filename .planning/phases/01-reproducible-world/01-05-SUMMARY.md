---
phase: 01-reproducible-world
plan: 05
subsystem: data
tags: [pydantic, discriminated-union, event-schema, adapter-pattern, hypothesis]

# Dependency graph
requires:
  - phase: 01-reproducible-world (plan 01-01)
    provides: src/nextmove/ingest/ package boundary, uv-managed project, pytest/hypothesis dev deps
provides:
  - "Canonical Event(event_id, customer_id, session_id, ts, type, payload, source) contract (DATA-01)"
  - "13-member EventType StrEnum and one strict Pydantic payload model per event kind"
  - "derive_event_id: deterministic uuid5-based event identity, never random"
  - "sort_events / CANONICAL_SORT_KEY: total order with event_id as tiebreak"
  - "IngestAdapter Protocol + register_adapter/get_adapter registry, inward-only by construction"
  - "SimulatorAdapter: validates already-canonical records through Event.model_validate"
affects: [01-06 (storage), 01-07/01-08 (simulator event emission), 01-09 (quarantine/rejects table keyed off CONTRACT_VERSION)]

# Tech tracking
tech-stack:
  added: [hypothesis (already a dev dep, first real usage)]
  patterns:
    - "Discriminated union on a Literal `type` field per payload model, cross-checked against the top-level Event.type by an explicit model_validator (a directly-constructed mismatched instance bypasses the union discriminator, so the explicit check is load-bearing, not redundant)"
    - "Deterministic identity via uuid5 over an entity's own identifying tuple instead of uuid4, everywhere identity must survive a reseeded rerun"
    - "Adapter seam enforced one-directional by omission: the Protocol declares no inverse method, so reversing DATA-01's direction requires a contributor to add a new interface rather than finding one already there"

key-files:
  created:
    - src/nextmove/ingest/contracts.py
    - src/nextmove/ingest/adapters.py
    - tests/unit/test_event_contract.py
    - tests/unit/test_adapter_registry.py
  modified:
    - src/nextmove/ingest/__init__.py

key-decisions:
  - "SessionStartPayload/SessionEndPayload/CartRemovePayload/CartAbandonPayload field shapes were not specified in REQUIREMENTS.md or RESEARCH.md (only ProductView, AddToCart, OrderPlaced, CampaignExposure, ActionDelivered, Override, Scroll, FilterApply, Dwell were detailed); designed minimal plausible fields (device, duration_s, sku+quantity, cart_value_cents) consistent with the plan's strictness conventions (non-empty strings, integer cents, ge/gt constraints)"
  - "Event.ts is typed as plain `datetime` with an explicit field_validator (not AwareDatetime) so the naive-datetime rejection message names the field explicitly, per the plan's literal instruction, rather than relying on pydantic's built-in AwareDatetime error text"
  - "Payload `type` Literal fields have no default value — every payload dict must explicitly state its type, keeping the strict-validation philosophy (extra='forbid') consistent for the discriminant itself"
  - "EVENT_ID_NAMESPACE is a fixed, hardcoded uuid.UUID constant with no external meaning (not the DNS/URL namespace) — documented as never-to-be-regenerated, since regenerating it would change every previously-derived event id"

requirements-completed: [DATA-01]

coverage:
  - id: D1
    description: "Canonical Event schema with 13 typed payload variants, tz-aware ts (naive rejected, aware normalized to UTC), integer-cents-only money, and a cross-field payload.type/type consistency check"
    requirement: "DATA-01"
    verification:
      - kind: unit
        ref: "tests/unit/test_event_contract.py (35 tests, includes round-trip-per-type parametrization over all 13 EventType members)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Deterministic event_id derivation (uuid5 over the event's own identifying tuple) and a total sort order (customer_id, ts, event_id) with event_id as tiebreak"
    requirement: "DATA-01"
    verification:
      - kind: unit
        ref: "tests/unit/test_event_contract.py::test_derive_event_id_deterministic_across_processes, ::test_derive_event_id_differs_by_seq, ::test_adjacency_same_ts_distinct_seq_differ_and_stable_sort, ::test_ordering_is_deterministic_across_shuffles"
        status: pass
      - kind: unit
        ref: "tests/unit/test_event_contract.py::test_derive_event_id_is_deterministic_property, ::test_derive_event_id_differs_for_different_seq, ::test_derive_event_id_differs_for_different_customer (hypothesis property tests)"
        status: pass
    human_judgment: false
  - id: D3
    description: "IngestAdapter registry is one-directional by construction (no outward converter exists) with duplicate-name and unregistered-name errors, and SimulatorAdapter validates already-canonical records without bypassing validation"
    requirement: "DATA-01"
    verification:
      - kind: unit
        ref: "tests/unit/test_adapter_registry.py (8 tests)"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-08-04
status: complete
---

# Phase 01 Plan 05: Canonical Event Contract and Inward-Only Adapter Seam Summary

**Pydantic discriminated-union Event schema (13 typed event kinds) with uuid5-deterministic event identity and a structurally one-directional IngestAdapter registry**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-08-04T18:40:00+02:00 (approx.)
- **Completed:** 2026-08-04T18:47:23+02:00
- **Tasks:** 3
- **Files modified:** 5 (4 created, 1 modified)

## Accomplishments

- One canonical `Event(event_id, customer_id, session_id, ts, type, payload, source)` Pydantic
  model with a 13-member `EventType` StrEnum and a matching discriminated `EventPayload` union
  — every event the simulator will emit (sessions, browse/cart, orders, campaigns, actions,
  overrides, and the three SIM-04 micro-conversion events) has a strictly-typed payload
- Timestamp safety: naive `ts` is rejected with an explicit message naming the field; any
  timezone-aware `ts` is normalized to UTC
- Deterministic identity: `derive_event_id` is a `uuid5` hash over `(customer_id, session_id,
  ts, event_type, seq)` — never a random generator — so two seeded runs produce identical
  event ids; verified deterministic and per-component-sensitive with both example-based and
  `hypothesis` property tests
- Total ordering: `sort_events`/`CANONICAL_SORT_KEY` sort by `(customer_id, ts, event_id)`,
  so two events sharing a customer and timestamp always land in the same relative position
  regardless of input or shuffle order
- `IngestAdapter` Protocol declares exactly one conversion direction (`to_canonical`); the
  registry (`register_adapter`/`get_adapter`) rejects duplicate names and reports registered
  names on a lookup miss; `SimulatorAdapter` validates already-canonical records through
  `Event.model_validate` (forcing `source="simulator"`) rather than trusting its producer
- 116/116 unit tests pass; `ruff check`, `ruff format --check`, and `lint-imports` (both
  existing import-linter contracts from plan 01-04) all pass clean

## Task Commits

1. **Task 1: Define the canonical Event contract and typed payload union** - `e2af9d9` (feat)
2. **Task 2: Build the inward-only IngestAdapter registry** - `b2a05b8` (feat), `f50f9e4`
   (style — ruff format fixup on the same files)
3. **Task 3: Author the contract test suite** - `c7909ef` (test)

**Plan metadata:** _pending_ (docs: complete plan, appended after this Summary is written)

_Note: Task 1's own acceptance criteria explicitly defer authoring `test_event_contract.py`
to Task 3 ("test file authored in Task 3 of this plan"), so despite `tdd="true"` on Task 1
the RED/GREEN split for the contract lands as feat (Task 1/2) then test (Task 3), not
test-then-feat within Task 1 itself. The full test suite was written and run against the
implementation before any commit, so nothing here was ever actually red._

## Files Created/Modified

- `src/nextmove/ingest/contracts.py` - `Event`, `EventType`, `EventPayload` union, 13 payload
  models, `CONTRACT_VERSION`, `derive_event_id`, `sort_events`, `CANONICAL_SORT_KEY`
- `src/nextmove/ingest/adapters.py` - `IngestAdapter` Protocol, `register_adapter`/`get_adapter`
  registry, `SimulatorAdapter`
- `src/nextmove/ingest/__init__.py` - re-exports the public contract surface (`Event`,
  `EventType`, `EventPayload`, `CONTRACT_VERSION`, `derive_event_id`, `sort_events`,
  `CANONICAL_SORT_KEY`)
- `tests/unit/test_event_contract.py` - 35 tests covering Task 1's full behaviour block plus
  the adjacency/empty/ordering/precision edge predicates and hypothesis property tests
- `tests/unit/test_adapter_registry.py` - 8 tests covering the registry's full behaviour block

## Decisions Made

- Payload field shapes for `SessionStartPayload`, `SessionEndPayload`, `CartRemovePayload`,
  and `CartAbandonPayload` were not specified in the plan (only 9 of 13 payloads had field
  details in the `<action>` block). Designed minimal, plausible fields consistent with the
  plan's own strictness conventions: `device` (session_start), `duration_s` (session_end),
  `sku`+`quantity` (cart_remove), `cart_value_cents` (cart_abandon) — every string field
  non-empty, every monetary field an integer `ge=0`.
- `Event.ts` is typed as plain `datetime` with an explicit `field_validator` rather than
  pydantic's `AwareDatetime`, so the naive-datetime rejection raises with a message that
  names the field explicitly, matching the plan's literal instruction rather than relying on
  pydantic's built-in error text.
- Payload `type` Literal fields have no default — every payload dict must state its type
  explicitly, keeping `extra="forbid"`'s strictness philosophy consistent for the
  discriminant field itself, not just for unknown extra keys.
- `EVENT_ID_NAMESPACE` is a fixed, arbitrarily-generated `uuid.UUID` constant (not a
  well-known namespace like the DNS UUID) with a comment marking it as never-to-be-regenerated,
  since regenerating it would silently change every previously-derived event id.

## Deviations from Plan

None — plan executed exactly as written, with the two design gaps above filled per Rule 2
(auto-add missing critical functionality: the four unspecified payload shapes had to exist
for `EventType`'s 13 members to all validate) and documented as decisions rather than
deviations, since the plan explicitly left them open.

## Issues Encountered

- `ruff format --check .` failed on two manually-wrapped lines in `adapters.py` and
  `test_adapter_registry.py` (a `raise KeyError(...)` call and a `_canonical_record(...)`
  call each split across multiple lines where ruff's formatter prefers one line). Fixed with
  `ruff format .` and committed as a separate `style(01-05)` fixup on the same Task 2 files
  (Rule 1 — auto-fix; `just lint`/`just ci` must stay green per the plan's own instructions).

## Next Phase Readiness

- `Event`, `EventType`, `EventPayload`, `CONTRACT_VERSION="1.0.0"`, `derive_event_id`, and
  `sort_events`/`CANONICAL_SORT_KEY` are all importable from `nextmove.ingest` — plans 01-06
  (storage), 01-08/01-09 (simulator + quarantine) can build directly on this contract.
- `SimulatorAdapter` (registered under `"simulator"`) is ready for the simulator to route its
  emitted records through once plan 01-07/01-08 exists; `get_adapter("simulator")` is the
  integration point.
- No blockers. `just lint` and `just test` both exit 0 with 116 tests passing (was 73 before
  this plan).

---
*Phase: 01-reproducible-world*
*Completed: 2026-08-04*

## Self-Check: PASSED

All created files verified present on disk (`src/nextmove/ingest/contracts.py`,
`src/nextmove/ingest/adapters.py`, `src/nextmove/ingest/__init__.py`,
`tests/unit/test_event_contract.py`, `tests/unit/test_adapter_registry.py`, this SUMMARY).
All task commits (`e2af9d9`, `b2a05b8`, `f50f9e4`, `c7909ef`) and the SUMMARY commit
(`c7b1942`) verified present in `git log --oneline --all`.
