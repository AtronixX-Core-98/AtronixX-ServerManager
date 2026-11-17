"""
watchdog.py - availability alerts

Hosts with the 🔔 watch switch on are checked with a plain TCP connect to their SSH port (no login,
no credentials involved). The owner is notified when a host stays unreachable for two consecutive
checks, and again when it comes back. The destination goes through the same SSRF checks as any
connection, so this cannot be used to probe internal networks.
"""

from __future__ import annotations

import asyncio
import logging
import time

from config import settings
from core.errors import SSHConnectError
from core.security import resolve_public
from database.db import db
from handlers import gate, ui
from locales.strings import t

logger = logging.getLogger("servermanager.watchdog")

CONNECT_TIMEOUT = 6
FAILS_BEFORE_DOWN = 2
MAX_PARALLEL = 10


async def tcp_reachable(target: str, port: int, timeout: float = CONNECT_TIMEOUT) -> bool:
    try:
        ip = await resolve_public(target)
        _, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout)
    except (SSHConnectError, OSError, asyncio.TimeoutError):
        return False
    writer.close()
    try:
        await asyncio.wait_for(writer.wait_closed(), 2)
    except Exception:  # noqa: BLE001
        pass
    return True


def _fmt_duration(seconds: float, lang: str) -> str:
    minutes = max(1, int(seconds // 60))
    days, rem = divmod(minutes, 1440)
    hours, mins = divmod(rem, 60)
    parts = []
    if lang == "fa":
        if days:
            parts.append(f"{days} روز")
        if hours:
            parts.append(f"{hours} ساعت")
        if mins or not parts:
            parts.append(f"{mins} دقیقه")
        return " و ".join(parts)
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins or not parts:
        parts.append(f"{mins}m")
    return " ".join(parts)


async def _check_one(bot, host: dict, sem: asyncio.Semaphore) -> None:
    async with sem:
        up = await tcp_reachable(host["ip"], host["port"])
    now = int(time.time())
    owner, status, fails = host["owner_id"], host["status"], host["fail_count"]
    user = await db.get_user(owner)
    if not user or not gate.has_access(user, await db.get_mode()):
        return
    lang = user["language"]
    if up:
        if status == 0:
            down_for = _fmt_duration(now - (host["status_since"] or now), lang)
            await ui.send(bot, owner, t("watch_up", lang, label=host["label"], downtime=down_for))
        if status != 1 or fails:
            await db.set_status(host["id"], 1, now if status != 1 else host["status_since"], 0)
        return
    fails += 1
    if status != 0 and fails >= FAILS_BEFORE_DOWN:
        await db.set_status(host["id"], 0, now, fails)
        await ui.send(bot, owner, t("watch_down", lang, label=host["label"], addr=f"{host['ip']}:{host['port']}"))
    else:
        await db.set_status(host["id"], status, host["status_since"], fails)


async def check_all(bot) -> None:
    hosts = await db.watched_hosts()
    if not hosts:
        return
    sem = asyncio.Semaphore(MAX_PARALLEL)
    results = await asyncio.gather(*(_check_one(bot, h, sem) for h in hosts), return_exceptions=True)
    for res in results:
        if isinstance(res, Exception):
            logger.warning("watch check failed: %s", res)
