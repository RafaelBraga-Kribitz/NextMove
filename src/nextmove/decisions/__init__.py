"""Decision engine: emits the typed Decision contract, with none/wait always in the action
space and hard constraints that learning can never override.

Import-linter forbidden-source target (must never import nextmove.simulator).

Submodules are imported explicitly (`nextmove.decisions.contract`, `.context`, `.actions`,
`.engine`); this `__init__` stays import-free so `nextmove.rules` can depend on the shared
context and candidate types without a package-level import cycle.
"""

__all__: list[str] = []
