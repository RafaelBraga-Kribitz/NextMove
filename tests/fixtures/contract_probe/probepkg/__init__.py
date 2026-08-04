"""Root package for the import-linter non-vacuity probe fixture.

This package is deliberately never installed and lives outside `src/nextmove/`
so the test that exercises it can never mutate production source. Its only
purpose is to be a known-violating package: `probepkg.models` imports
`probepkg.simulator` at module level, mirroring the shape of production
contract one (SIM-02) so a red result against this fixture proves a forbidden
contract of that exact shape is capable of catching a real violation.
"""
