"""Probe stand-in for `nextmove.models`.

Deliberately violates the mirrored contract by importing the probe simulator
package at module level — this is the known violation `test_import_contract.py`
asserts drives `lint-imports` to a non-zero exit.
"""

from probepkg import simulator  # noqa: F401  (deliberate violation, not dead code)
