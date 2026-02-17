"""Custom exceptions for clearer failure handling."""

from __future__ import annotations


class ViewerError(Exception):
    """Base error for the viewer app."""


class InvalidRequestError(ViewerError):
    """Raised for malformed client requests."""


class NotFoundError(ViewerError):
    """Raised when an expected resource does not exist."""


class NoActiveGameError(ViewerError):
    """Raised when an API requiring a selected game is called without one."""


class GameDataInvalidError(ViewerError):
    """Raised when a game data path is missing required files."""

