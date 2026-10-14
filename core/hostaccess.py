"""
hostaccess.py - "This server": SSH access to the machine the bot itself runs on.

Disabled by default. The installer enables it (``servermanager host-access enable``) by creating a
dedicated ed25519 key, authorising it on the host (restricted to the bot's Docker subnet) and writing
HOST_ACCESS=1 to .env. Only the admin can ever use it, and it bypasses the normal "no internal
addresses" safety net for that single, operator-configured destination only.
"""

from __future__ import annotations

import asyncio
import os
import socket
import time

from config import settings
from core.errors import HostAccessError

LOCAL_HOST_ID = 0


def enabled() -> bool:
    return settings.host_access


def available_to(uid: int | None) -> bool:
    return settings.host_access and uid is not None and uid == settings.admin_id


def _read_key() -> str:
    path = settings.host_key_file
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except FileNotFoundError as exc:
        raise HostAccessError(f"private key not found at {path}") from exc
    except OSError as exc:
        raise HostAccessError(f"cannot read {path}: {exc.strerror}") from exc
    if "PRIVATE KEY" not in text:
        raise HostAccessError(f"{path} is not a private key")
    return text


def public_row(stored_fp: str | None = None) -> dict:
    """Host dict without secrets (what the UI is allowed to see)."""
    return {
        "id": LOCAL_HOST_ID,
        "owner_id": settings.admin_id,
        "label": "This server",
        "ip": settings.host_addr,
        "port": settings.host_port,
        "username": settings.host_user,
        "auth_type": "key",
        "host_fingerprint": stored_fp or (settings.host_fingerprints[0] if settings.host_fingerprints else None),
        "pinned_fps": list(settings.host_fingerprints),
        "group_id": None,
        "favorite": 0,
        "created_at": 0,
        "watch": 0,
        "status": None,
        "local": True,
    }


def full_row(stored_fp: str | None = None) -> dict:
    row = public_row(stored_fp)
    row["secret"] = _read_key()
    row["passphrase"] = None
    return row


async def resolve_gateway() -> str:
    """Resolve the configured host address (usually host.docker.internal → Docker host-gateway)."""
    addr = settings.host_addr
    try:
        socket.inet_pton(socket.AF_INET, addr)
        return addr
    except OSError:
        pass
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(addr, None, family=socket.AF_INET, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise HostAccessError(f"cannot resolve {addr}: {exc}") from exc
    if not infos:
        raise HostAccessError(f"cannot resolve {addr}")
    return infos[0][4][0]


def key_age_days() -> int | None:
    try:
        return int((time.time() - os.path.getmtime(settings.host_key_file)) / 86400)
    except OSError:
        return None
