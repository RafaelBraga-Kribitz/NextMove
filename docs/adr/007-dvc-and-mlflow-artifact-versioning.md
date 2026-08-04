# ADR 007: DVC for Data/Artifacts, MLflow for Runs/Models

## Status

Accepted — 2026-07-25 (ratifies OD-7, per D-09). This ADR closes the open marker inside locked
decision AD-18 (`docs/ARCHITECTURAL_DIRECTION.md` §8, "MLOps Expectations": "data & artifacts (DVC
or content-hashed artifact store `[Open: OD-7]`)"). AD-18 explicitly deferred this choice rather
than asserting one; this ADR is the genuine deliberation that resolves it.

## Context

OD-7 asked how NextMove versions its data and model artifacts: DVC, a well-known open-source tool
purpose-built for versioning large files alongside git, or a custom content-hashed artifact store
paired with MLflow's own artifact-tracking feature. AD-18 deliberately left this open rather than
guessing — the source text annotates it `[Open: OD-7]` precisely because the two options trade off
along a dimension the architecture-writing pass could not resolve without more context: recognized
tooling versus custom-built lightness.

Both options can technically do the job. A content-hashed store is lighter to build (no external
dependency, tuned exactly to this project's file layout) but is, by definition, custom — a reviewer
encountering it has to read code to understand what it does and why it is trustworthy. DVC is a
standard tool with a large user base; a reviewer who has used it before (or has simply heard of it)
recognizes what it does on sight, without reading a line of this project's code.

## Decision

Adopt DVC for data and artifact versioning, plus MLflow for experiment runs and model registry —
the combination explicitly recommended by OPEN_DECISIONS.md OD-7 and now ratified rather than merely
recommended. The deciding factor is reviewer recognizability: a hiring manager or technical reviewer
who has never seen this codebase before knows what DVC does the moment they see a `.dvc` file or a
`dvc.yaml` pipeline stage, whereas a custom hash-store requires reading the implementation and
trusting an unfamiliar guarantee. For a portfolio artifact — one whose purpose partly is to be
evaluated quickly by someone who did not write it — that legibility outweighs the marginal
elegance of a bespoke, more tightly-scoped alternative.

The rejected alternative is a content-hashed artifact store paired with MLflow's built-in artifact
logging: technically viable, lighter-weight, but unfamiliar to a reviewer and requiring custom code
this project would then have to justify and maintain instead of leaning on a widely adopted tool.

## Consequences

The accepted costs, named explicitly rather than glossed over: some workflow friction (DVC adds a
`dvc add` / `dvc push` step to the data pipeline that a purely git-native or hash-store approach
would not need) and a second tool to install and configure alongside MLflow, increasing the
project's dependency surface by one.

This ADR also creates a concrete Phase 1 obligation: per D-18, canonical event and feature Parquet
tables are DVC-tracked. This pairing is not incidental — DVC versions immutable, content-addressable
files, which is exactly what it is built for, rather than trying to version a mutable multi-gigabyte
`.duckdb` database blob (which would defeat DVC's diffing and storage-efficiency model entirely).
This choice is also what keeps DATA-04's per-table content hashes meaningful: because each Parquet
table is an immutable file DVC tracks by content hash, a table's content hash is a stable, auditable
fact about that exact version of the data, not a moving target inside a larger mutable store.

## Alternatives Considered

- **Content-hashed artifact store + MLflow artifacts** was rejected: technically lighter and fully
  custom-fitted to this project's needs, but illegible to a reviewer at a glance and would require
  this project to build and justify tooling that DVC already provides, tested, and widely recognized.
