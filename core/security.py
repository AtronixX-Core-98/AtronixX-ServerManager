"""
security.py

- The admin is identified only by the numeric id in .env.
- Every destination is resolved and checked *before* connecting (SSRF protection): only public
  addresses are allowed, plus any CIDRs the operator explicitly lists in ALLOWED_NETS.
  Loopback, link-local (cloud metadata), multicast and reserved ranges are never reachable.
- Connection rate limiting.
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
import time
from collections import deque

from config import settings
from core.errors import SSHConnectError, TargetBlocked

_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
_HOST_RE = re.compile(rf"^(?=.{{1,253}}$){_LABEL}(?:\.{_LABEL})+$")   # at least two dot-separated labels


def is_admin(uid: int | None) -> bool:
    return uid is not None and uid == settings.admin_id


def valid_address(text: str) -> bool:
    """A valid IP address or a domain name (with at least one dot)."""
    text = text.strip()
    try:
        ipaddress.ip_address(text)
        return True
    except ValueError:
        return bool(_HOST_RE.match(text))


def _check_ip(ip):
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    if str(ip) in settings.blocked_ips:
        raise TargetBlocked()
    if ip.is_loopback or ip.is_unspecified or ip.is_link_local or ip.is_multicast or ip.is_reserved:
        raise TargetBlocked()
    if ip.is_global:
        return ip
    for net in settings.allowed_nets:
        if net.version == ip.version and ip in net:
            return ip
    raise TargetBlocked()


async def resolve_public(target: str) -> str:
    """Resolve + validate a destination. The connection must use the returned IP
    (prevents DNS-rebinding between check and connect)."""
    try:
        return str(_check_ip(ipaddress.ip_address(target.strip())))
    except ValueError:
        pass
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(target, None, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise SSHConnectError(f"DNS: {exc}", "dns") from exc
    addrs = [_check_ip(ipaddress.ip_address(info[4][0].split("%")[0])) for info in infos]
    if not addrs:
        raise SSHConnectError("DNS: no address", "dns")
    addrs.sort(key=lambda a: a.version)  # prefer IPv4
    return str(addrs[0])


class RateLimiter:
    def __init__(self, limit: int, window: float, exempt_admin: bool = False):
        self.limit, self.window, self.exempt_admin = limit, window, exempt_admin
        self._hits: dict[int, deque] = {}

    def allow(self, key: int) -> bool:
        if self.exempt_admin and is_admin(key):
            return True
        now = time.monotonic()
        q = self._hits.setdefault(key, deque())
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True

    def retry_after(self, key: int) -> int:
        q = self._hits.get(key)
        if not q:
            return 0
        return max(1, int(self.window - (time.monotonic() - q[0])))


connect_limiter = RateLimiter(10, 60, exempt_admin=True)   # 10 connection attempts per minute per user (the admin is exempt)
