"""config.py - settings loaded from environment variables (.env). No secrets live in the code."""

from __future__ import annotations

import ipaddress
import os
import re
import sys
from dataclasses import dataclass

from version import VERSION  # noqa: F401  (re-exported for convenience)

_TRUE = {"1", "true", "yes", "on", "y"}
_USERNAME_RE = re.compile(r"^@?[A-Za-z][A-Za-z0-9_]{4,31}$")
_FP_RE = re.compile(r"^SHA256:[A-Za-z0-9+/]{43}$")


def _int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _bool(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    return raw in _TRUE if raw else default


def _csv(name: str) -> list[str]:
    return [x.strip() for x in (os.getenv(name) or "").split(",") if x.strip()]


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_id: int
    support_username: str          # "" when not configured
    data_dir: str
    tz: str
    backup_passphrase: str
    backup_interval_hours: int
    default_max_live: int
    idle_timeout_min: int
    max_session_hours: int
    blocked_ips: frozenset
    allowed_nets: tuple            # extra CIDRs that may be reached (private LAN / VPN)
    brand: str                     # display name shown in the bot
    watch_interval_min: int
    max_watch_per_user: int
    # --- "this server" access (the machine the bot itself runs on) ---
    host_access: bool
    host_addr: str
    host_port: int
    host_user: str
    host_key_file: str
    host_fingerprints: tuple       # pinned SHA256 host-key fingerprints (optional)

    @property
    def db_path(self) -> str:
        return os.path.join(self.data_dir, "servermanager.db")

    @property
    def key_path(self) -> str:
        return os.path.join(self.data_dir, "secret.key")

    @property
    def tmp_dir(self) -> str:
        return os.path.join(self.data_dir, "tmp")

    @property
    def heartbeat_path(self) -> str:
        return "/tmp/servermanager.hb"

    @property
    def support_url(self) -> str:
        return "https://t.me/" + self.support_username.lstrip("@") if self.support_username else ""


def _clean_brand(raw: str) -> str:
    brand = re.sub(r"[<>&{}]", "", raw).strip()[:40]
    return brand or "ServerManager"


def load_settings() -> Settings:
    token = (os.getenv("BOT_TOKEN") or "").strip()
    if not re.fullmatch(r"\d{6,}:[\w-]{30,}", token):
        sys.exit("BOT_TOKEN is missing or invalid (check your .env file)")
    admin_id = _int("ADMIN_ID", 0)
    if admin_id <= 0:
        sys.exit("ADMIN_ID must be your numeric Telegram user id (check your .env file)")
    passphrase = (os.getenv("BACKUP_PASSPHRASE") or "").strip()
    if len(passphrase) < 8:
        sys.exit("BACKUP_PASSPHRASE must be at least 8 characters (check your .env file)")

    support = (os.getenv("SUPPORT_USERNAME") or "").strip()
    if support and not _USERNAME_RE.match(support):
        sys.exit("SUPPORT_USERNAME must look like @username (or be left empty)")
    support = "@" + support.lstrip("@") if support else ""

    nets = []
    for item in _csv("ALLOWED_NETS"):
        try:
            nets.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            sys.exit(f"ALLOWED_NETS contains an invalid CIDR: {item!r}")

    fps = tuple(_csv("HOST_SSH_FINGERPRINT"))
    for fp in fps:
        if not _FP_RE.match(fp):
            sys.exit(f"HOST_SSH_FINGERPRINT contains an invalid fingerprint: {fp!r}")

    data_dir = os.getenv("DATA_DIR", "/data")
    return Settings(
        bot_token=token,
        admin_id=admin_id,
        support_username=support,
        data_dir=data_dir,
        tz=os.getenv("TZ", "UTC"),
        backup_passphrase=passphrase,
        backup_interval_hours=max(1, _int("BACKUP_INTERVAL_HOURS", 24)),
        default_max_live=max(1, _int("MAX_LIVE_SESSIONS", 20)),
        idle_timeout_min=max(2, _int("IDLE_TIMEOUT_MIN", 10)),
        max_session_hours=max(1, _int("MAX_SESSION_HOURS", 2)),
        blocked_ips=frozenset(_csv("BLOCKED_IPS")),
        allowed_nets=tuple(nets),
        brand=_clean_brand(os.getenv("BOT_NAME") or ""),
        watch_interval_min=max(1, _int("WATCH_INTERVAL_MIN", 5)),
        max_watch_per_user=max(0, _int("MAX_WATCH_PER_USER", 10)),
        host_access=_bool("HOST_ACCESS", False),
        host_addr=(os.getenv("HOST_SSH_ADDR") or "host.docker.internal").strip(),
        host_port=min(65535, max(1, _int("HOST_SSH_PORT", 22))),
        host_user=(os.getenv("HOST_SSH_USER") or "root").strip(),
        host_key_file=(os.getenv("HOST_SSH_KEY") or os.path.join(data_dir, "host_key")).strip(),
        host_fingerprints=fps,
    )


settings = load_settings()
