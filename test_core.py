"""Core logic without Telegram or SSH: crypto, database, plans, backup, Jalali dates, destination safety."""

import asyncio
import dataclasses
import io
import json
import os
import sqlite3
import time
import zipfile

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

import core.security as security
from config import settings
from core import crypto
from core.backup import build_backup, inspect_backup, restore_backup
from core.crypto import CryptoError, decrypt_backup, encrypt_backup, vault
from core.errors import TargetBlocked
from core.jdate import fmt_dt, gregorian_to_jalali
from core.security import RateLimiter, resolve_public, valid_address
from database.db import db

vault.load()


@pytest.fixture(autouse=True, scope="module")
def _db():
    asyncio.run(db.open())
    yield
    asyncio.run(db.close())


# ------------------------------------------------------------------ crypto
def test_field_encryption_roundtrip_and_aad():
    token = vault.encrypt("s3cret", "a")
    assert token.startswith("v2:") and "s3cret" not in token
    assert vault.decrypt(token, "a") == "s3cret"
    with pytest.raises(CryptoError):
        vault.decrypt(token, "b")


legacy_v1 = pytest.importorskip("core.legacy_v1")


def test_legacy_v1_tokens_still_decrypt():
    legacy = crypto._derive(vault.raw_key(), legacy_v1.FIELD_KDF_INFO)
    nonce = os.urandom(12)
    raw = nonce + legacy.encrypt(nonce, b"old-secret", b"host:1:secret")
    token = "v1:" + crypto._b64e(raw)
    assert vault.decrypt(token, "host:1:secret") == "old-secret"


def test_backup_crypto():
    blob = encrypt_backup(b"hello", "pw-12345678")
    assert decrypt_backup(blob, "pw-12345678") == b"hello"
    with pytest.raises(CryptoError):
        decrypt_backup(blob, "wrong-pass")
    bad = bytearray(blob)
    bad[-1] ^= 1
    with pytest.raises(CryptoError):
        decrypt_backup(bytes(bad), "pw-12345678")
    assert oct(os.stat(settings.key_path).st_mode & 0o777) == "0o600"


# ------------------------------------------------------------------ dates
def test_jalali():
    assert gregorian_to_jalali(2026, 9, 24) == (1405, 7, 2)
    assert gregorian_to_jalali(2025, 3, 21) == (1404, 1, 1)
    assert gregorian_to_jalali(2024, 3, 20) == (1403, 1, 1)
    assert fmt_dt(1790000000, "en").count("-") == 2


# ------------------------------------------------------------------ destination safety
def test_valid_address():
    for ok in ("1.2.3.4", "example.com", "a-b.example.org", "2001:db8::1"):
        assert valid_address(ok), ok
    for bad in ("", "localhost", "foo bar.com", "a..b", "-x.com", "http://x.com"):
        assert not valid_address(bad), bad


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.1.2.3", "192.168.1.1", "172.17.0.1", "169.254.169.254",
                                "0.0.0.0", "::1", "::ffff:127.0.0.1", "100.64.0.1", "224.0.0.1", "8.8.4.4"])
async def test_blocked_targets(ip):
    with pytest.raises(TargetBlocked):
        await resolve_public(ip)


async def test_public_target_allowed():
    assert await resolve_public("8.8.8.8") == "8.8.8.8"


async def test_allowed_nets_opens_private_ranges_but_never_loopback_or_metadata(monkeypatch):
    import ipaddress
    patched = dataclasses.replace(settings, allowed_nets=(ipaddress.ip_network("10.0.0.0/8"), ipaddress.ip_network("169.254.0.0/16")))
    monkeypatch.setattr(security, "settings", patched)
    assert await resolve_public("10.9.8.7") == "10.9.8.7"
    for ip in ("169.254.169.254", "127.0.0.1"):
        with pytest.raises(TargetBlocked):
            await resolve_public(ip)
    with pytest.raises(TargetBlocked):
        await resolve_public("192.168.0.1")


def test_rate_limiter():
    rl = RateLimiter(3, 60)
    assert [rl.allow(1) for _ in range(4)] == [True, True, True, False]
    assert rl.allow(2)
    assert rl.retry_after(1) >= 1


# ------------------------------------------------------------------ database
async def test_users_plans_and_hosts():
    user, created = await db.ensure_user(1000, "admin", "Admin")
    assert created
    _, created2 = await db.ensure_user(1000, "admin", "Admin")
    assert not created2

    await db.ensure_user(7, "bob", "Bob")
    await db.grant(7, 30, 3)
    u = await db.get_user(7)
    assert u["sub_max_hosts"] == 3 and u["sub_expires_at"] > time.time() + 29 * 86400
    await db.grant(7, 10, 3)   # extends
    assert (await db.get_user(7))["sub_expires_at"] > time.time() + 39 * 86400

    hid = await db.add_host(owner=7, label="web", ip="1.2.3.4", port=22, username="root", auth_type="password", secret="hunter2")
    host = await db.get_host_decrypted(hid, 7)
    assert host["secret"] == "hunter2"
    assert await db.get_host_decrypted(hid, 8) is None           # another user can't read it
    raw = await db.fetchone("SELECT secret FROM hosts WHERE id=?", (hid,))
    assert "hunter2" not in raw["secret"]
    assert (await db.get_host(hid, 7)).get("secret") is None     # public view has no secrets
    await db.update_host(hid, 7, secret="n3w")
    assert (await db.get_host_decrypted(hid, 7))["secret"] == "n3w"


async def test_watch_columns():
    hid = (await db.list_hosts(7))[0]["id"]
    await db.set_watch(hid, 7, True)
    assert await db.count_watched(7) == 1
    assert any(h["id"] == hid for h in await db.watched_hosts())
    await db.set_status(hid, 0, 123, 2)
    row = (await db.watched_hosts())[0]
    assert (row["status"], row["status_since"], row["fail_count"]) == (0, 123, 2)
    await db.set_watch(hid, 7, False)
    assert await db.count_watched(7) == 0


async def test_local_host_is_admin_only_and_disabled_by_default():
    assert await db.get_host(0, 1000) is None   # HOST_ACCESS=0 in the test environment
    assert await db.get_host(0, 7) is None


def test_old_schema_is_migrated(tmp_path):
    """A database from a pre-release build (no watch columns, old file name) opens cleanly and keeps its data."""
    from database import db as dbmod

    old = tmp_path / legacy_v1.DB_FILENAME
    conn = sqlite3.connect(old)
    conn.executescript(dbmod.SCHEMA.replace(
        ", watch INTEGER NOT NULL DEFAULT 0, status INTEGER, status_since INTEGER, fail_count INTEGER NOT NULL DEFAULT 0", ""))
    conn.execute("INSERT INTO users(id, first_name, language, created_at, last_seen) VALUES (5,'old','fa',1,1)")
    conn.commit()
    conn.close()
    new_path = str(tmp_path / "servermanager.db")
    dbmod._migrate_legacy_file(new_path)
    assert os.path.exists(new_path) and not old.exists()
    conn = sqlite3.connect(new_path)
    dbmod._migrate(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(hosts)")}
    assert {"watch", "status", "status_since", "fail_count"} <= cols
    assert conn.execute("SELECT first_name FROM users WHERE id=5").fetchone()[0] == "old"
    conn.close()


# ------------------------------------------------------------------ backup / restore
async def test_backup_roundtrip_and_failures():
    blob = await build_backup()
    meta = await inspect_backup(blob, settings.backup_passphrase)
    assert meta["format"] == 2 and meta["users"] >= 1
    with pytest.raises(CryptoError):
        await inspect_backup(blob, "not-the-password")
    before = await db.stats()
    await db.ensure_user(55, "x", "X")
    await restore_backup(blob, settings.backup_passphrase)
    assert (await db.stats())["users"] == before["users"]
    assert await db.get_user(55) is None


async def test_v1_backup_is_accepted():
    snap = await db.snapshot_bytes()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(legacy_v1.DB_FILENAME, snap)
        z.writestr("secret.key", vault.raw_key())
        z.writestr("meta.json", json.dumps({"format": 1, "created": 1, "users": 1, "hosts": 0}))
    salt, nonce = os.urandom(16), os.urandom(12)
    magic = legacy_v1.BACKUP_MAGIC
    blob = magic + salt + nonce + AESGCM(crypto._scrypt_key("legacy-pass-1", salt)).encrypt(nonce, buf.getvalue(), magic)
    meta = await inspect_backup(blob, "legacy-pass-1")
    assert meta["format"] == 1
