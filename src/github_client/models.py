"""Shared data models for GitHub client and CLI diff collection."""
from dataclasses import dataclass


@dataclass
class ChangedFile:
    """Represents a single file changed in a commit or pull request."""

    filename: str
    content: str
    patch: str
