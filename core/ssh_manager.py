"""
ssh_manager.py - SSH/PTY and SFTP engine

- fingerprint_of(): SHA-256 host-key fingerprint (same format as ``ssh-keygen -lf``)
- open_trusted(): connect + verify the stored fingerprint (TOFU). A new/changed key raises
  HostKeyUntrusted and keeps the connection open until the user decides. A *pinned* key
  (host access) that does not match raises HostKeyMismatch and is never offered for confirmation.
- TerminalSession: a live PTY session + a virtual screen (pyte) that turns ANSI output into text
- SFTPBrowser: browse / upload / download / delete over one kept-open connection
- run_command(): one-shot non-interactive command (used by the monitor and the toolbox)

Security: before every connection the destination is resolved and only public addresses are
accepted (core.security.resolve_public); the connection then uses exactly that IP.
The single exception is "This server" (core.hostaccess), which only the admin can reach.
"""

from __future__ import annotations

import asyncio
import base64
import errno
import hashlib
import logging
import posixpath
import re
import stat
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import asyncssh
import pyte

from core import hostaccess
from core.errors import (  # noqa: F401  (re-exported)
    HostAccessError,
    HostKeyMismatch,
    HostKeyUntrusted,
    SSHConnectError,
    TargetBlocked,
)
from core.security import resolve_public

logger = logging.getLogger("servermanager.ssh")

TERM_COLS = 56
TERM_ROWS = 26
SCROLLBACK_LINES = 1500   # kept small for low-RAM servers
CONNECT_TIMEOUT = 12
PROBE_TIMEOUT = 6      # per step of the post-timeout diagnosis (TCP connect, SSH banner)

# Raw bytes for the on-screen control pad
KEYS: dict[str, bytes] = {
    "ctrl_c": b"\x03", "ctrl_d": b"\x04", "ctrl_z": b"\x1a", "ctrl_x": b"\x18", "ctrl_o": b"\x0f",
    "ctrl_a": b"\x01", "ctrl_e": b"\x05", "ctrl_r": b"\x12", "ctrl_u": b"\x15", "ctrl_w": b"\x17",
    "ctrl_k": b"\x0b", "ctrl_l": b"\x0c",
    "tab": b"\t", "esc": b"\x1b", "enter": b"\r",
    "up": b"\x1b[A", "down": b"\x1b[B", "right": b"\x1b[C", "left": b"\x1b[D",
    "home": b"\x1b[H", "end": b"\x1b[F", "pgup": b"\x1b[5~", "pgdn": b"\x1b[6~",
}


def fingerprint_of(key: asyncssh.SSHKey) -> str:
    """SHA-256 fingerprint in the standard format (like ``ssh-keygen -lf``)."""
    if hasattr(key, "public_data") and key.public_data:
        der = key.public_data
    else:
        der = key.export_public_key(format_name="der")
    digest = hashlib.sha256(der).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


def key_needs_passphrase(text: str) -> tuple[bool, bool]:
    """(is the key valid?, does it need a passphrase?)"""
    try:
        asyncssh.import_private_key(text)
        return True, False
    except asyncssh.KeyImportError as exc:
        if "passphrase" in str(exc).lower():
            return True, True
        return False, False
    except Exception:  # noqa: BLE001
        return False, False


def classify_error(exc: BaseException) -> str:
    """Map a low-level exception to a coarse category used for friendly messages."""
    if isinstance(exc, asyncssh.PermissionDenied):
        return "auth"
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return "timeout"
    if isinstance(exc, ConnectionRefusedError):
        return "refused"
    if isinstance(exc, OSError):
        if exc.errno in (errno.ETIMEDOUT, errno.EHOSTUNREACH, errno.ENETUNREACH):
            return "timeout"
        if exc.errno == errno.ECONNREFUSED:
            return "refused"
        return "network"
    if isinstance(exc, asyncssh.ConnectionLost):
        return "network"
    if isinstance(exc, asyncssh.DisconnectError):
        text = str(exc).lower()
        if "authentication" in text or "permission" in text:
            return "auth"
        return "other"
    return "other"


async def _diagnose_timeout(ip: str, port: int) -> tuple[str, str]:
    """A connection attempt timed out: find out *where* it got stuck so the user gets a useful hint.

    Returns (kind, detail): tcp_timeout (nothing answers on that port), refused, ssh_silent (TCP open but
    no SSH banner), ssh_slow (banner arrives, the login does not finish) or not_ssh (another protocol).
    """
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), PROBE_TIMEOUT)
    except ConnectionRefusedError:
        return "refused", f"{ip}:{port} refused the connection"
    except (asyncio.TimeoutError, TimeoutError):
        return "tcp_timeout", f"no TCP answer from {ip}:{port} within {PROBE_TIMEOUT}s"
    except OSError as exc:
        return "tcp_timeout", f"{ip}:{port}: {exc.strerror or exc}"
    try:
        banner = await asyncio.wait_for(reader.readline(), PROBE_TIMEOUT)
    except (asyncio.TimeoutError, TimeoutError):
        return "ssh_silent", f"TCP to {ip}:{port} is open but no SSH banner arrived within {PROBE_TIMEOUT}s"
    except OSError as exc:
        return "ssh_silent", f"{ip}:{port} closed the connection ({exc.strerror or exc})"
    finally:
        writer.close()
    if banner.startswith(b"SSH-"):
        return "ssh_slow", f"server banner {banner[:40].decode('ascii', 'replace').strip()!r} arrived, but the login did not finish in {CONNECT_TIMEOUT}s"
    return "not_ssh", f"{ip}:{port} answers but does not speak SSH ({banner[:30]!r})"


async def _open_connection(host: dict, connect_timeout: int | None = None) -> asyncssh.SSHClientConnection:
    connect_timeout = connect_timeout or CONNECT_TIMEOUT
    if host.get("local"):
        ip = await hostaccess.resolve_gateway()
    else:
        ip = await resolve_public(host["ip"])  # TargetBlocked / SSHConnectError
    kwargs: dict = dict(
        host=ip,
        port=host["port"],
        username=host["username"],
        known_hosts=None,          # host keys are verified by us (TOFU / pinning), not by asyncssh
        connect_timeout=connect_timeout,
        keepalive_interval=30,
        keepalive_count_max=3,
        agent_path=None,
    )
    if host["auth_type"] == "password":
        kwargs["password"] = host["secret"]
        kwargs["client_keys"] = ()          # () = no keys; None would load ~/.ssh defaults
        kwargs["preferred_auth"] = "password,keyboard-interactive"
    else:
        try:
            key = asyncssh.import_private_key(host["secret"], passphrase=host.get("passphrase") or None)
        except (ValueError, asyncssh.KeyImportError) as exc:
            raise SSHConnectError(f"invalid key: {exc}", "key") from exc
        kwargs["client_keys"] = [key]
        kwargs["password"] = None
        kwargs["preferred_auth"] = "publickey"
    try:
        return await asyncssh.connect(**kwargs)
    except asyncssh.Error as exc:
        raise SSHConnectError(str(exc), classify_error(exc)) from exc
    except (OSError, asyncio.TimeoutError) as exc:
        kind, detail = classify_error(exc), str(exc) or type(exc).__name__
        if kind == "timeout":
            kind, detail = await _diagnose_timeout(ip, host["port"])
        raise SSHConnectError(detail, kind) from exc


async def open_trusted(host: dict) -> asyncssh.SSHClientConnection:
    """Connect and verify the host key. Raises HostKeyUntrusted (connection stays open) when the key
    is new or changed, or HostKeyMismatch when a pinned fingerprint does not match."""
    conn = await _open_connection(host)
    key = conn.get_server_host_key()
    fp = fingerprint_of(key) if key else "unknown"
    pins = host.get("pinned_fps") or []
    if pins:
        if fp in pins:
            return conn
        conn.close()
        raise HostKeyMismatch(f"server key {fp} is not in the pinned list")
    stored = host.get("host_fingerprint")
    if stored and stored == fp:
        return conn
    raise HostKeyUntrusted(conn, fp, stored)


async def test_connection(host: dict) -> tuple[bool, float | None, str | None, str | None]:
    """Quick login test: (ok, latency ms, error text, error kind)."""
    start = time.monotonic()
    try:
        conn = await _open_connection(host, connect_timeout=8)
    except SSHConnectError as exc:
        return False, None, str(exc), exc.kind
    elapsed = (time.monotonic() - start) * 1000
    conn.close()
    try:
        await asyncio.wait_for(conn.wait_closed(), 5)
    except Exception:  # noqa: BLE001
        pass
    return True, round(elapsed, 1), None, None


async def run_command(conn: asyncssh.SSHClientConnection, command: str, timeout: float = 20) -> tuple[Optional[int], str]:
    """Run one non-interactive command; returns (exit status, combined output text)."""
    res = await asyncio.wait_for(conn.run(command, check=False, stderr=asyncssh.STDOUT), timeout)
    out = res.stdout if isinstance(res.stdout, str) else (res.stdout or b"").decode("utf-8", "replace")
    return res.exit_status, out


# Full-screen programs (htop, nano, vim, less) are detected from the escape sequences they send
_ALT_RE = re.compile(rb"\x1b\[\?(?:1049|1047|47)([hl])")
# If a chunk ends in the middle of an escape sequence, hold it until the next chunk arrives
_PARTIAL_RE = re.compile(rb"\x1b(?:\[(?:\?\d{0,4})?)?$")


class ScrollScreen(pyte.Screen):
    """pyte virtual screen with scrollback history."""

    def __init__(self, columns: int, lines: int, history: int = SCROLLBACK_LINES):
        self.scrollback: deque[str] = deque(maxlen=history)
        super().__init__(columns, lines)

    def _row_text(self, row) -> str:
        return "".join(row[x].data for x in range(self.columns)).rstrip()

    def index(self):  # noqa: D401
        top, bottom = self.margins or (0, self.lines - 1)
        if self.cursor.y == bottom:
            self.scrollback.append(self._row_text(self.buffer[top]))
        super().index()

    def erase_in_display(self, how=0, *args, **kwargs):
        if how in (2, 3):
            self.scrollback.clear()
        super().erase_in_display(how, *args, **kwargs)


@dataclass
class TerminalSession:
    host: dict
    connection: asyncssh.SSHClientConnection
    process: asyncssh.SSHClientProcess
    screen: ScrollScreen = field(init=False)
    stream: pyte.ByteStream = field(init=False)
    alt_screen: bool = field(default=False, init=False)
    started_at: float = field(default_factory=time.monotonic, init=False)
    last_input: float = field(default_factory=time.monotonic, init=False)
    last_output: float = field(default_factory=time.monotonic, init=False)
    idle_warned: bool = field(default=False, init=False)
    _carry: bytes = field(default=b"", init=False)
    _reader_task: Optional[asyncio.Task] = field(default=None, init=False)
    _closed: bool = field(default=False, init=False)
    _dirty: bool = field(default=True, init=False)

    def __post_init__(self):
        self.screen = ScrollScreen(TERM_COLS, TERM_ROWS)
        # ByteStream (not Stream): SSH output is raw bytes and must be UTF-8 decoded
        self.stream = pyte.ByteStream(self.screen)
        self._reader_task = asyncio.create_task(self._read_loop())

    # ------------------------------------------------------------ output
    async def _read_loop(self) -> None:
        try:
            while not self._closed:
                chunk = await self.process.stdout.read(4096)
                if not chunk:
                    break
                self._feed(chunk)
                self._dirty = True
                self.last_output = time.monotonic()
        except asyncio.CancelledError:
            pass
        except Exception:  # noqa: BLE001
            logger.debug("PTY read loop ended", exc_info=True)
        finally:
            self._closed = True
            self._dirty = True

    def _feed(self, chunk: bytes) -> None:
        data = self._carry + chunk
        self._carry = b""
        partial = _PARTIAL_RE.search(data)
        if partial:
            self._carry = data[partial.start():]
            data = data[: partial.start()]

        pos = 0
        for match in _ALT_RE.finditer(data):
            self.stream.feed(data[pos : match.start()])
            self._on_alt_screen(entering=(match.group(1) == b"h"))
            pos = match.end()
        self.stream.feed(data[pos:])

    def _on_alt_screen(self, entering: bool) -> None:
        """pyte has no alternate screen. Emulate it: entering pushes the current content into the
        history and clears the screen; leaving clears the screen so the history shows again."""
        if entering and not self.alt_screen:
            for line in self._screen_lines():
                self.screen.scrollback.append(line)
            self.screen.reset()
            self.alt_screen = True
        elif not entering and self.alt_screen:
            self.screen.reset()
            self.alt_screen = False

    def _screen_lines(self) -> list[str]:
        """Visible lines up to the last line that has text or the cursor."""
        display = [ln.rstrip() for ln in self.screen.display]
        last = self.screen.cursor.y
        for i in range(len(display) - 1, -1, -1):
            if display[i]:
                last = max(last, i)
                break
        return display[: last + 1]

    # ---------------------------------------------------------------- render
    def render(self) -> str:
        """Current terminal as plain text (last TERM_ROWS lines) with a █ cursor."""
        screen = self.screen
        lines = self._screen_lines()
        offset = 0
        if not self.alt_screen:
            need = TERM_ROWS - len(lines)
            if need > 0 and screen.scrollback:
                prefix = list(screen.scrollback)[-need:]
                offset = len(prefix)
                lines = prefix + lines
            idx = offset + screen.cursor.y
            if 0 <= idx < len(lines):
                ln = lines[idx].ljust(screen.cursor.x + 1)
                lines[idx] = ln[: screen.cursor.x] + "█" + ln[screen.cursor.x + 1 :]
        lines = lines[-TERM_ROWS:]
        return "\n".join(lines) if lines else " "

    def full_log(self) -> str:
        """Whole history + current screen (for exporting as a file)."""
        return "\n".join(list(self.screen.scrollback) + self._screen_lines())

    def consume_dirty(self) -> bool:
        was_dirty = self._dirty
        self._dirty = False
        return was_dirty

    def mark_dirty(self) -> None:
        self._dirty = True

    @property
    def is_closed(self) -> bool:
        return self._closed

    @classmethod
    async def open(cls, host: dict, connection: asyncssh.SSHClientConnection) -> "TerminalSession":
        process = await connection.create_process(
            term_type="xterm-256color",
            term_size=(TERM_COLS, TERM_ROWS),
            encoding=None,
        )
        return cls(host=host, connection=connection, process=process)

    # ---------------------------------------------------------------- input
    def _touch(self) -> None:
        self.last_input = time.monotonic()
        self.idle_warned = False

    async def send_text(self, text: str) -> None:
        """Text + Enter. Terminals understand Enter as CR (\\r), not LF."""
        if self._closed:
            return
        self._touch()
        self.process.stdin.write((text + "\r").encode("utf-8"))

    async def send_raw(self, data: bytes) -> None:
        if self._closed:
            return
        self._touch()
        self.process.stdin.write(data)

    async def send_key(self, name: str) -> None:
        await self.send_raw(KEYS[name])

    async def send_ctrl_c(self):
        await self.send_key("ctrl_c")

    async def send_ctrl_d(self):
        await self.send_key("ctrl_d")

    async def send_ctrl_z(self):
        await self.send_key("ctrl_z")

    async def send_tab(self):
        await self.send_key("tab")

    async def send_escape(self):
        await self.send_key("esc")

    async def send_arrow(self, direction: str):
        await self.send_key(direction)

    async def close(self) -> None:
        self._closed = True
        if self._reader_task:
            self._reader_task.cancel()
        try:
            self.process.terminate()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.connection.close()
            await asyncio.wait_for(self.connection.wait_closed(), 5)
        except Exception:  # noqa: BLE001
            pass


class SFTPBrowser:
    """Browse / upload / download / delete over one kept-open SFTP connection."""

    MAX_ENTRIES = 1000
    MAX_LINK_LOOKUPS = 100

    def __init__(self, conn: asyncssh.SSHClientConnection):
        self._conn = conn
        self._sftp: Optional[asyncssh.SFTPClient] = None

    async def start(self) -> "SFTPBrowser":
        self._sftp = await self._conn.start_sftp_client()
        return self

    async def close(self) -> None:
        try:
            if self._sftp:
                self._sftp.exit()
            self._conn.close()
            await asyncio.wait_for(self._conn.wait_closed(), 5)
        except Exception:  # noqa: BLE001
            pass

    async def realpath(self, path: str) -> str:
        return await self._sftp.realpath(path)

    async def _resolve_link(self, full: str) -> Optional[asyncssh.SFTPAttrs]:
        try:
            return await asyncio.wait_for(self._sftp.stat(full), 5)
        except Exception:  # noqa: BLE001
            return None   # dangling link or no permission

    async def listdir(self, path: str) -> list[dict]:
        entries: list[dict] = []
        links: list[tuple[dict, str]] = []
        for entry in await self._sftp.readdir(path):
            name = entry.filename
            if name in (".", ".."):
                continue
            perm = entry.attrs.permissions or 0
            item = {
                "name": name,
                "is_dir": stat.S_ISDIR(perm),
                "is_link": stat.S_ISLNK(perm),
                "size": entry.attrs.size or 0,
            }
            entries.append(item)
            if item["is_link"] and len(links) < self.MAX_LINK_LOOKUPS:
                links.append((item, posixpath.join(path, name)))
        # A symlink is shown as what it points to (folder or file); a broken link stays a plain file
        for (item, _), attrs in zip(links, await asyncio.gather(*(self._resolve_link(p) for _, p in links))):
            if attrs is not None:
                item["is_dir"] = stat.S_ISDIR(attrs.permissions or 0)
                item["size"] = attrs.size or 0
        entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
        return entries[: self.MAX_ENTRIES]

    async def download(self, remote_path: str, local_path: str) -> None:
        await self._sftp.get(remote_path, local_path)

    async def upload(self, local_path: str, remote_path: str) -> None:
        await self._sftp.put(local_path, remote_path)

    async def exists(self, path: str) -> bool:
        try:
            await self._sftp.lstat(path)
            return True
        except Exception:  # noqa: BLE001
            return False

    async def mkdir(self, path: str) -> None:
        await self._sftp.mkdir(path)

    async def remove(self, path: str, is_dir: bool) -> None:
        if is_dir:
            await self._sftp.rmtree(path)
        else:
            await self._sftp.remove(path)
