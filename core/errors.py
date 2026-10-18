"""core/errors.py - shared exceptions (kept separate to avoid circular imports)."""

from __future__ import annotations


class SSHConnectError(RuntimeError):
    """SSH connection / authentication failure.

    ``kind`` is a coarse category used to show a friendly message:
    auth | refused | timeout | dns | hostkey | key | network | other
    """

    def __init__(self, message: str = "", kind: str = "other"):
        super().__init__(message)
        self.kind = kind


class TargetBlocked(SSHConnectError):
    """The destination is internal/private/forbidden (protects the machine the bot runs on)."""

    def __init__(self, message: str = "blocked target"):
        super().__init__(message, "blocked")


class HostAccessError(SSHConnectError):
    """'This server' access is not enabled or not configured correctly."""

    def __init__(self, message: str = "host access is not available"):
        super().__init__(message, "hostaccess")


class HostKeyMismatch(SSHConnectError):
    """The server key differs from the pinned fingerprint. Never offered for confirmation."""

    def __init__(self, message: str = "host key does not match the pinned fingerprint"):
        super().__init__(message, "hostkey")


class HostKeyUntrusted(Exception):
    """The host key is new or has changed. The connection is kept open until the user decides."""

    def __init__(self, connection, fingerprint: str, stored: str | None):
        super().__init__("host key not trusted")
        self.connection = connection
        self.fingerprint = fingerprint
        self.stored = stored
