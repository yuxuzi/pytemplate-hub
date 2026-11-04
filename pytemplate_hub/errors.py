"""Errors raised by the hub; each message says what to change."""


class HubError(Exception):
    """Base class for an index or pack problem."""


class EntryError(HubError):
    """An index entry is malformed or inconsistent with its path."""


class FetchError(HubError):
    """A pack could not be fetched at the requested tag."""


class PackCheckError(HubError):
    """A pack failed the checks required to be listed."""
