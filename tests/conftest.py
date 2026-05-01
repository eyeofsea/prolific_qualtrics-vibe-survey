"""Shared pytest fixtures.

The `templates/standard.qsf` file is kept in the repo as a schema reference
only — it is never loaded at runtime now that `lib.qsf_builder` constructs
QSF dicts from scratch. No fixtures load it.
"""
