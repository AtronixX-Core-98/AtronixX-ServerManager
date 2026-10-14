"""
backup.py - encrypted backup & restore

A backup file (.smbak) = AES-256-GCM( zip{ servermanager.db, secret.key, meta.json } ) with a key
derived from the backup password (scrypt). The master key is inside the backup so a restore on a new
server needs nothing but "one file + the password". Backups made by pre-release builds are still accepted (when core/legacy_v1.py is present).
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import sqlite3
import time
import zipfile

from config import settings
from core.crypto import CryptoError, decrypt_backup, encrypt_backup, vault
from database.db import db
from version import VERSION

FORMAT = 2
REQUIRED_TABLES = {"users", "hosts", "groups", "snippets", "settings", "channels"}
try:   # only present to upgrade pre-release installations; safe to delete
    from core import legacy_v1
except ImportError:  # pragma: no cover
    legacy_v1 = None

_DB_NAMES = ("servermanager.db",) + ((legacy_v1.DB_FILENAME,) if legacy_v1 else ())


async def build_backup(passphrase: str | None = None) -> bytes:
    passphrase = passphrase or settings.backup_passphrase
    snap = await db.snapshot_bytes()
    st = await db.stats()
    meta = {"format": FORMAT, "created": int(time.time()), "users": st["users"], "hosts": st["hosts"], "version": VERSION}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("servermanager.db", snap)
        z.writestr("secret.key", vault.raw_key())
        z.writestr("meta.json", json.dumps(meta))
    return await asyncio.to_thread(encrypt_backup, buf.getvalue(), passphrase)


def _validate_db(data: bytes) -> None:
    os.makedirs(settings.tmp_dir, exist_ok=True)
    path = os.path.join(settings.tmp_dir, f"validate_{time.time_ns()}.db")
    try:
        with open(path, "wb") as fh:
            fh.write(data)
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise CryptoError("the database inside the backup is corrupted")
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            conn.close()
        if not REQUIRED_TABLES <= tables:
            raise CryptoError("the backup does not contain a valid database")
    except sqlite3.DatabaseError as exc:
        raise CryptoError("the database inside the backup is invalid") from exc
    finally:
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(path + suffix)
            except FileNotFoundError:
                pass


def _open_payload(blob: bytes, passphrase: str) -> tuple[bytes, bytes, dict]:
    raw = decrypt_backup(blob, passphrase)
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names = set(z.namelist())
            db_name = next((n for n in _DB_NAMES if n in names), None)
            if db_name is None:
                raise KeyError("db")
            db_bytes = z.read(db_name)
            key = z.read("secret.key")
            meta = json.loads(z.read("meta.json"))
    except (zipfile.BadZipFile, KeyError, ValueError) as exc:
        raise CryptoError("the backup content is corrupted") from exc
    if len(key) != 32:
        raise CryptoError("the key inside the backup is invalid")
    _validate_db(db_bytes)
    return db_bytes, key, meta


async def inspect_backup(blob: bytes, passphrase: str) -> dict:
    """Validate and read metadata only (changes nothing). Raises CryptoError on a wrong password/file."""
    _, _, meta = await asyncio.to_thread(_open_payload, blob, passphrase)
    return meta


async def restore_backup(blob: bytes, passphrase: str) -> dict:
    """Replace the database and key. If anything fails the previous state is put back."""
    db_bytes, key, meta = await asyncio.to_thread(_open_payload, blob, passphrase)
    old_db = await db.snapshot_bytes()
    old_key = vault.raw_key()
    try:
        vault.install_raw_key(key)
        await db.replace_file(db_bytes)
    except Exception:
        vault.install_raw_key(old_key)
        await db.replace_file(old_db)
        raise
    return meta
