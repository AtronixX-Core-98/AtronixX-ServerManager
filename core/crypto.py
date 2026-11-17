"""
crypto.py

- Sensitive fields (SSH passwords / keys): AES-256-GCM with a random nonce and AAD that binds each
  value to its owner and field.
- Master key: 32 random bytes in a separate file (secret.key, mode 600) - never inside the database.
- Backups: scrypt (N=2^15) key derivation + AES-256-GCM.

Backward compatibility: values written by pre-release builds ("v1:" tokens) and backups with their magic still
decrypt when core/legacy_v1.py is present; everything new is written with the current format.
"""

from __future__ import annotations

import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from config import settings

try:   # only present to upgrade pre-release installations; safe to delete
    from core import legacy_v1
except ImportError:  # pragma: no cover
    legacy_v1 = None

BACKUP_MAGIC = b"SMBAK2\x00"
LEGACY_BACKUP_MAGICS = (legacy_v1.BACKUP_MAGIC,) if legacy_v1 else ()
BACKUP_MAGICS = (BACKUP_MAGIC,) + LEGACY_BACKUP_MAGICS

_INFO_CURRENT = b"servermanager/fields/v2"


class CryptoError(Exception):
    pass


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text.encode("ascii"))


def _derive(raw: bytes, info: bytes) -> AESGCM:
    return AESGCM(HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info).derive(raw))


class Vault:
    def __init__(self, key_path: str):
        self.key_path = key_path
        self._aes: AESGCM | None = None
        self._legacy: AESGCM | None = None

    def load(self) -> None:
        """Read the master key; create it on first run."""
        os.makedirs(os.path.dirname(self.key_path), exist_ok=True)
        if not os.path.exists(self.key_path):
            fd = os.open(self.key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as fh:
                fh.write(os.urandom(32))
        with open(self.key_path, "rb") as fh:
            raw = fh.read()
        if len(raw) != 32:
            raise CryptoError("secret.key is corrupted")
        self._aes = _derive(raw, _INFO_CURRENT)
        self._legacy = _derive(raw, legacy_v1.FIELD_KDF_INFO) if legacy_v1 else None

    def raw_key(self) -> bytes:
        with open(self.key_path, "rb") as fh:
            return fh.read()

    def install_raw_key(self, raw: bytes) -> None:
        """Replace the master key (backup restore). Atomic, mode 600."""
        if len(raw) != 32:
            raise CryptoError("invalid key size")
        tmp = self.key_path + ".new"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(raw)
        os.replace(tmp, self.key_path)
        self.load()

    def encrypt(self, plaintext: str, aad: str) -> str:
        if self._aes is None:
            raise CryptoError("vault not loaded")
        nonce = os.urandom(12)
        ct = self._aes.encrypt(nonce, plaintext.encode("utf-8"), aad.encode("utf-8"))
        return "v2:" + _b64e(nonce + ct)

    def decrypt(self, token: str, aad: str) -> str:
        if self._aes is None:
            raise CryptoError("vault not loaded")
        if not token or token[:3] not in ("v1:", "v2:"):
            raise CryptoError("unknown token format")
        aes = self._aes if token.startswith("v2:") else self._legacy
        if aes is None:
            raise CryptoError("data from a pre-release installation needs core/legacy_v1.py")
        try:
            raw = _b64d(token[3:])
            return aes.decrypt(raw[:12], raw[12:], aad.encode("utf-8")).decode("utf-8")
        except (InvalidTag, ValueError) as exc:
            raise CryptoError("decryption failed (wrong key or tampered data)") from exc


vault = Vault(settings.key_path)


def _scrypt_key(passphrase: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(passphrase.encode("utf-8"))


def backup_magic_of(blob: bytes) -> bytes | None:
    for magic in BACKUP_MAGICS:
        if blob.startswith(magic):
            return magic
    return None


def encrypt_backup(payload: bytes, passphrase: str) -> bytes:
    salt, nonce = os.urandom(16), os.urandom(12)
    ct = AESGCM(_scrypt_key(passphrase, salt)).encrypt(nonce, payload, BACKUP_MAGIC)
    return BACKUP_MAGIC + salt + nonce + ct


def decrypt_backup(blob: bytes, passphrase: str) -> bytes:
    magic = backup_magic_of(blob)
    if magic is None:
        raise CryptoError("this is not a backup file made by this application")
    head = len(magic)
    if len(blob) < head + 28 + 16:
        raise CryptoError("backup file is truncated")
    salt, nonce, ct = blob[head : head + 16], blob[head + 16 : head + 28], blob[head + 28 :]
    try:
        return AESGCM(_scrypt_key(passphrase, salt)).decrypt(nonce, ct, magic)
    except InvalidTag as exc:
        raise CryptoError("wrong password or corrupted file") from exc
