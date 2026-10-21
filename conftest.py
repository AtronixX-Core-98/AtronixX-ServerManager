"""Test environment: must run before any application module is imported."""

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_TMP = tempfile.mkdtemp(prefix="sm_tests_")
os.environ.update(
    BOT_TOKEN="123456789:AAH" + "x" * 32,
    ADMIN_ID="1000",
    DATA_DIR=_TMP,
    BACKUP_PASSPHRASE="test-passphrase-123",
    BLOCKED_IPS="8.8.4.4",
    BOT_NAME="TestBrand",
    HOST_ACCESS="0",
)

from core.crypto import vault  # noqa: E402

vault.load()


# ---------------------------------------------------------------- real sshd for the integration / E2E tests
import dataclasses  # noqa: E402
import getpass  # noqa: E402
import shutil  # noqa: E402
import socket  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402

import pytest  # noqa: E402

import core.hostaccess as hostaccess  # noqa: E402
from config import settings  # noqa: E402

SSHD = shutil.which("sshd") or "/usr/sbin/sshd"
PORT = 2222


def _free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


@pytest.fixture(scope="module")
def sshd(tmp_path_factory):
    d = tmp_path_factory.mktemp("sshd")
    try:   # privilege-separation dir: needed (and creatable) only when running as root
        os.makedirs("/run/sshd", exist_ok=True)
    except PermissionError:
        pass
    for name in ("hostkey", "client"):
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(d / name)], check=True)
    os.chmod(d / "client", 0o600)
    shutil.copy(d / "client.pub", d / "authorized_keys")
    cfg = d / "sshd_config"
    cfg.write_text(
        f"Port {PORT}\nListenAddress 127.0.0.1\nHostKey {d}/hostkey\nAuthorizedKeysFile {d}/authorized_keys\n"
        f"PermitRootLogin yes\nPasswordAuthentication yes\nUsePAM no\nStrictModes no\nPidFile {d}/sshd.pid\n"
        "Subsystem sftp internal-sftp\nLogLevel ERROR\n"
    )
    assert _free(PORT), "port 2222 busy"
    proc = subprocess.Popen([SSHD, "-D", "-e", "-f", str(cfg)])
    for _ in range(50):
        if not _free(PORT):
            break
        time.sleep(0.1)
    else:
        proc.kill()
        pytest.skip("sshd did not start")
    fp = subprocess.run(["ssh-keygen", "-lf", str(d / "hostkey.pub")], capture_output=True, text=True, check=True).stdout.split()[1]
    # Some environments (containers, unprivileged sshd) cannot hand out a PTY; PTY tests are skipped there.
    probe = subprocess.run(
        ["ssh", "-tt", "-p", str(PORT), "-i", str(d / "client"), "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
         "-o", "BatchMode=yes", "-o", "LogLevel=ERROR", f"{getpass.getuser()}@127.0.0.1", "true"],
        capture_output=True, text=True, timeout=20,
    )
    pty_ok = probe.returncode == 0 and "PTY allocation" not in probe.stderr
    yield {"dir": d, "fp": fp, "key": str(d / "client"), "pty": pty_ok}
    proc.terminate()
    proc.wait(5)


@pytest.fixture
def pty_required(sshd):
    if not sshd["pty"]:
        pytest.skip("this sshd cannot allocate a PTY here (run the tests as root to cover it)")


@pytest.fixture
def local_access(sshd, monkeypatch):
    """Enable 'This server' access pointing at the test sshd, with the fingerprint pinned."""
    patched = dataclasses.replace(
        settings, host_access=True, host_addr="127.0.0.1", host_port=PORT, host_user=getpass.getuser(),
        host_key_file=sshd["key"], host_fingerprints=(sshd["fp"],),
    )
    monkeypatch.setattr(hostaccess, "settings", patched)
    return patched


