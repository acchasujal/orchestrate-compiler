"""Typed loader failures and validation diagnostics."""

from __future__ import annotations


class LoaderError(ValueError):
    """Base class for invalid or unreadable participant datasets."""


class DatasetReadError(LoaderError):
    """A required dataset file cannot be read."""


class DatasetSchemaError(LoaderError):
    """A dataset file has invalid headers, keys, references, or values."""
