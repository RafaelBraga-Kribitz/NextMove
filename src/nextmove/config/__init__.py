"""Cross-cutting configuration infrastructure: layered YAML loading (base + profile
overlay), Pydantic validation of the merged result, and stable config hashing.

Infrastructure, not one of the eleven ENG-01 packages — sits below all of them in the
import graph so nothing creates a cycle. Populated by plan 01-03.
"""

__all__: list[str] = []
