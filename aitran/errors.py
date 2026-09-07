"""Small public error surface used by the executable showcase."""

from __future__ import annotations


class ShowcaseError(Exception):
    """Base class for expected, user-actionable showcase failures."""


class SourceTextError(ShowcaseError):
    """The demonstration source or derived text is invalid."""


class WorkspaceConflictError(ShowcaseError):
    """A checkpoint workspace is busy, corrupted, or belongs to another run."""


class DemoInterrupted(ShowcaseError):
    """The tour stopped at a checkpoint boundary and can be resumed."""


class DemoAdapterError(ShowcaseError):
    """A synthetic adapter cannot handle the requested demonstration input."""
