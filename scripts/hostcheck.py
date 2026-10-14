"""Diagnose "This server" access from inside the bot container (used by `servermanager host-access`)."""

import asyncio
import os
import socket
import sys

# `python scripts/hostcheck.py` puts scripts/ (not the app root) on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from core import hostaccess
from core.errors import HostKeyMismatch, HostKeyUntrusted, SSHConnectError
from core.ssh_manager import open_trusted, run_command

OK, BAD = "\033[32m✔\033[0m", "\033[31m✘\033[0m"


def line(ok: bool, text: str) -> None:
    print(f"  {OK if ok else BAD} {text}")


async def main() -> int:
    if not settings.host_access:
        line(False, "HOST_ACCESS is not enabled in .env")
        return 1
    line(True, f"target {settings.host_user}@{settings.host_addr}:{settings.host_port}")
    try:
        ip = await hostaccess.resolve_gateway()
        line(True, f"{settings.host_addr} resolves to {ip}")
    except SSHConnectError as exc:
        line(False, str(exc))
        return 1
    try:
        with socket.create_connection((ip, settings.host_port), timeout=5):
            line(True, f"TCP port {settings.host_port} is reachable")
    except OSError as exc:
        line(False, f"cannot reach port {settings.host_port}: {exc.strerror or exc} (firewall? sshd not listening on the Docker bridge?)")
        return 1
    try:
        host = hostaccess.full_row()
        line(True, f"private key readable ({settings.host_key_file})")
    except SSHConnectError as exc:
        line(False, str(exc))
        return 1
    try:
        conn = await open_trusted(host)
    except HostKeyUntrusted as exc:
        exc.connection.close()
        line(True, f"login works; host key {exc.fingerprint} is not pinned yet (the bot will ask you to confirm it)")
        return 0
    except HostKeyMismatch as exc:
        line(False, str(exc))
        return 1
    except SSHConnectError as exc:
        line(False, f"login failed ({exc.kind}): {exc}")
        return 1
    status, out = await run_command(conn, "id -un; hostname")
    conn.close()
    line(status == 0, "login OK, host key matches the pinned fingerprint: " + " @ ".join(out.split()))
    return 0 if status == 0 else 1


sys.exit(asyncio.run(main()))
