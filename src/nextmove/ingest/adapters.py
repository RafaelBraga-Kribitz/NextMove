"""The inward-only adapter seam that keeps the canonical `Event` schema canonical (DATA-01).

`IngestAdapter` declares exactly one conversion direction: external records in, canonical
`Event` objects out. It declares no inverse method and no serializer that turns an `Event`
back into an external shape — that absence is the enforcement mechanism for DATA-01's "adapters
map external shapes inward to this schema, never the reverse." A future contributor who wants
to emit an external shape (GA4, a public dataset, v2 per D-13) has to add a new interface and
justify it, rather than finding a convenient outward converter already sitting here.
"""

from collections.abc import Iterable, Mapping
from typing import Any, Protocol, runtime_checkable

from nextmove.ingest.contracts import Event, sort_events

_ADAPTER_REGISTRY: dict[str, "type[IngestAdapter]"] = {}


@runtime_checkable
class IngestAdapter(Protocol):
    """One-directional conversion contract: external records in, canonical Events out."""

    name: str

    def to_canonical(self, records: Iterable[Mapping[str, Any]]) -> list[Event]:
        """Validate `records` into canonical `Event` objects. No inverse method exists."""
        ...


def register_adapter(cls: "type[IngestAdapter]") -> "type[IngestAdapter]":
    """Class decorator registering an adapter under its `name` attribute.

    Raises `ValueError` naming the duplicate rather than silently overwriting an existing
    registration — a second adapter claiming an already-used name is a bug worth surfacing
    loudly, not a convenience worth papering over.
    """
    name = cls.name
    if name in _ADAPTER_REGISTRY:
        raise ValueError(f"adapter name {name!r} is already registered")
    _ADAPTER_REGISTRY[name] = cls
    return cls


def get_adapter(name: str) -> "type[IngestAdapter]":
    """Look up a registered adapter by name.

    Raises `KeyError` naming the requested adapter and listing every registered name, so a
    typo'd adapter name fails with an actionable message instead of a bare lookup error.
    """
    if name not in _ADAPTER_REGISTRY:
        registered = sorted(_ADAPTER_REGISTRY)
        raise KeyError(
            f"no adapter registered under {name!r}; registered adapters: {registered}"
        )
    return _ADAPTER_REGISTRY[name]


@register_adapter
class SimulatorAdapter:
    """Validates simulator-native (already-canonical) records into `Event` objects.

    The simulator emits canonical shapes directly, so this adapter performs no field
    renaming — but it still validates every record through `Event.model_validate`, because
    DATA-02's quarantine gate must never be bypassable by an adapter that trusts its producer.
    """

    name = "simulator"

    def to_canonical(self, records: Iterable[Mapping[str, Any]]) -> list[Event]:
        events = [
            Event.model_validate({**dict(record), "source": "simulator"}) for record in records
        ]
        return sort_events(events)
