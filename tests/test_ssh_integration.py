"""
Integration tests against a REAL sshd on 127.0.0.1 (skipped when openssh-server is not installed).

They exercise the code paths that unit tests can't: "This server" access, host-key pinning/TOFU,
the PTY terminal and its message rendering, SFTP, the monitor script and every toolbox command.
"""

import asyncio
import dataclasses
import os
import shutil
import socket
import subprocess
import time

import pytest

SSHD = shutil.which("sshd") or "/usr/sbin/sshd"
pytestmark = pytest.mark.skipif(not os.path.exists(SSHD) or not shutil.which("ssh-keygen"), reason="sshd not available")

import core.hostaccess as hostaccess  # noqa: E402
from config import settings  # noqa: E402
from core.errors import HostKeyMismatch, HostKeyUntrusted, SSHConnectError, TargetBlocked  # noqa: E402
from core.ssh_manager import SFTPBrowser, TerminalSession, open_trusted, run_command  # noqa: E402
from core.ssh_manager import test_connection as probe_connection  # noqa: E402
from database.db import db  # noqa: E402
from handlers import terminal, toolbox, tools  # noqa: E402

PORT = 2222


@pytest.fixture(scope="module", autouse=True)
def _db():
    asyncio.run(db.open())
    yield
    asyncio.run(db.close())


async def _local_host():
    host = await db.get_host_decrypted(0, settings.admin_id)
    assert host is not None
    return host


# ------------------------------------------------------------------ "This server"
async def test_local_host_only_for_admin(local_access):
    assert await db.get_host(0, 4242) is None
    assert await db.get_host_decrypted(0, 4242) is None
    row = await db.get_host(0, settings.admin_id)
    assert row["local"] and "secret" not in row


async def test_local_host_connects_and_runs_commands(local_access):
    conn = await open_trusted(await _local_host())
    status, out = await run_command(conn, "echo hello-$((6*7))")
    conn.close()
    assert status == 0 and out.strip() == "hello-42"


async def test_pinned_fingerprint_mismatch_is_refused_not_offered(sshd, local_access, monkeypatch):
    bad = "SHA256:" + "A" * 43
    monkeypatch.setattr(hostaccess, "settings", dataclasses.replace(local_access, host_fingerprints=(bad,)))
    with pytest.raises(HostKeyMismatch):
        await open_trusted(await _local_host())


async def test_unpinned_local_host_uses_tofu_and_remembers(sshd, local_access, monkeypatch):
    monkeypatch.setattr(hostaccess, "settings", dataclasses.replace(local_access, host_fingerprints=()))
    host = await _local_host()
    with pytest.raises(HostKeyUntrusted) as exc:
        await open_trusted(host)
    assert exc.value.fingerprint == sshd["fp"]
    exc.value.connection.close()
    await db.set_host_fingerprint(0, exc.value.fingerprint)
    conn = await open_trusted(await _local_host())   # now trusted silently
    conn.close()


async def test_normal_hosts_cannot_reach_loopback(sshd):
    host = {"id": 9, "ip": "127.0.0.1", "port": PORT, "username": "root", "auth_type": "password", "secret": "x"}
    with pytest.raises(TargetBlocked):
        await open_trusted(host)


# ------------------------------------------------------------------ friendly error kinds
async def test_error_kinds(sshd, local_access):
    base = dict(await _local_host())
    refused = await probe_connection({**base, "port": 2299})
    assert refused[0] is False and refused[3] == "refused"
    wrong = await probe_connection({**base, "auth_type": "password", "secret": "definitely-wrong"})
    assert wrong[0] is False and wrong[3] == "auth"
    ok = await probe_connection(base)
    assert ok[0] is True and ok[1] is not None


# ------------------------------------------------------------------ terminal
async def _wait_for(session, needle, timeout=8.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if needle in session.render():
            return True
        await asyncio.sleep(0.1)
    return False


async def test_terminal_session_types_and_renders(local_access):
    host = await _local_host()
    conn = await open_trusted(host)
    session = await TerminalSession.open(host, conn)
    try:
        await session.send_text("echo marker-$((20+22))")
        assert await _wait_for(session, "marker-42"), session.render()
        await session.send_text("sleep 30")
        await asyncio.sleep(0.3)
        await session.send_key("ctrl_c")
        await session.send_text("echo after-ctrl-c")
        assert await _wait_for(session, "after-ctrl-c"), session.render()
    finally:
        await session.close()


async def test_live_message_never_exceeds_telegram_limit_with_html_heavy_output(local_access):
    """Regression: output full of < > & used to blow past 4096 chars once escaped and break the live view."""
    host = await _local_host()
    conn = await open_trusted(host)
    session = await TerminalSession.open(host, conn)
    try:
        await session.send_text("for i in $(seq 1 40); do printf '<&>&&<<>>&&&&<&>&&<<>>&&&&<&>&&<<>>&&&&\\n'; done; echo done-marker")
        assert await _wait_for(session, "done-marker")
        text = terminal._compose(session, "web <b>&</b>", "fa")
        assert len(text) <= 4096, len(text)
        assert "&amp;" in text and "<b>&</b>" not in text   # label and output are escaped
    finally:
        await session.close()


# ------------------------------------------------------------------ SFTP
async def test_sftp_browser_symlinks_upload_download_delete(local_access, tmp_path):
    host = await _local_host()
    conn = await open_trusted(host)
    browser = await SFTPBrowser(conn).start()
    try:
        root = tmp_path / "remote"
        (root / "dir").mkdir(parents=True)
        (root / "file.txt").write_text("hello")
        (root / "dirlink").symlink_to(root / "dir")
        (root / "filelink").symlink_to(root / "file.txt")
        (root / "broken").symlink_to(root / "nope")
        entries = {e["name"]: e for e in await browser.listdir(str(root))}
        assert entries["dir"]["is_dir"] and entries["dirlink"]["is_dir"]          # link to a folder behaves as a folder
        assert not entries["filelink"]["is_dir"] and entries["filelink"]["size"] == 5   # link to a file stays a file
        assert not entries["broken"]["is_dir"]
        names = list(entries)
        assert names.index("dir") < names.index("file.txt")                        # folders first

        await browser.mkdir(str(root / "new"))
        local = tmp_path / "up.bin"
        local.write_bytes(b"x" * 1000)
        assert not await browser.exists(str(root / "new" / "up.bin"))
        await browser.upload(str(local), str(root / "new" / "up.bin"))
        assert await browser.exists(str(root / "new" / "up.bin"))
        back = tmp_path / "down.bin"
        await browser.download(str(root / "new" / "up.bin"), str(back))
        assert back.read_bytes() == b"x" * 1000
        await browser.remove(str(root / "new"), True)
        assert not (root / "new").exists()
        await browser.remove(str(root / "dirlink"), False)   # removing a link must not touch its target
        assert (root / "dir").exists()
    finally:
        await browser.close()


# ------------------------------------------------------------------ monitor and toolbox
async def test_monitor_script_and_formatting(local_access):
    conn = await open_trusted(await _local_host())
    res = await asyncio.wait_for(conn.run(tools._MON_CMD, check=False), 25)
    conn.close()
    data = tools.parse_monitor(res.stdout)
    assert data["cpu"].isdigit() and data["cores"].isdigit() and data["mem"].split()[0].isdigit()
    for lang in ("fa", "en"):
        text = tools.format_monitor(res.stdout, lang)
        assert "CPU" in text and "RAM" in text and "Disk" in text
        assert len(text) < 3000


@pytest.mark.parametrize("key", list(toolbox.TOOLS))
async def test_every_toolbox_command_runs_cleanly(local_access, key):
    import shlex

    conn = await open_trusted(await _local_host())
    status, out = await run_command(conn, "sh -c " + shlex.quote(toolbox.TOOLS[key]), timeout=30)
    conn.close()
    assert status is not None
    body, _ = toolbox.clean_output(out)
    assert len(body) <= toolbox.MAX_OUTPUT
    assert "\x1b" not in body


# ------------------------------------------------------------------ the authorized_keys line written by the installer
async def test_installer_authorized_keys_line_works_and_is_network_restricted(sshd, local_access):
    """`from="<subnet>",restrict,pty` must still allow PTY, exec and SFTP — and refuse other source networks."""
    pub = (sshd["dir"] / "client.pub").read_text().strip()
    ak = sshd["dir"] / "authorized_keys"
    original = ak.read_text()
    try:
        ak.write_text(f'from="127.0.0.0/8",restrict,pty {pub}\n')
        host = await _local_host()
        conn = await open_trusted(host)
        status, out = await run_command(conn, "echo exec-ok")
        assert (status, out.strip()) == (0, "exec-ok")
        browser = await SFTPBrowser(conn).start()
        assert await browser.listdir("/tmp") is not None
        await browser.close()
        conn = await open_trusted(host)
        session = await TerminalSession.open(host, conn)
        await session.send_text("echo pty-ok")
        assert await _wait_for(session, "pty-ok")
        await session.close()

        ak.write_text(f'from="10.99.0.0/16",restrict,pty {pub}\n')      # the bot's network is not 10.99.x → refused
        ok, _, _, kind = await probe_connection(await _local_host())
        assert not ok and kind == "auth"
    finally:
        ak.write_text(original)


# ------------------------------------------------------------------ scripts/hostcheck.py (what `servermanager host-access test` runs)
def test_hostcheck_script_end_to_end(sshd):
    import sys

    env = {**os.environ, "HOST_ACCESS": "1", "HOST_SSH_ADDR": "127.0.0.1", "HOST_SSH_PORT": str(PORT), "HOST_SSH_USER": "root",
           "HOST_SSH_KEY": sshd["key"], "HOST_SSH_FINGERPRINT": sshd["fp"]}
    script = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "hostcheck.py")
    ok = subprocess.run([sys.executable, script], env=env, capture_output=True, text=True, cwd="/")   # cwd=/ : must not rely on it
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "matches the pinned fingerprint" in ok.stdout

    wrong = subprocess.run([sys.executable, script], env={**env, "HOST_SSH_FINGERPRINT": "SHA256:" + "B" * 43},
                           capture_output=True, text=True, cwd="/")
    assert wrong.returncode == 1 and "pinned list" in wrong.stdout
