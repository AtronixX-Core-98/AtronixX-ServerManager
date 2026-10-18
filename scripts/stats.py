"""Print one line of counters for the `servermanager` CLI dashboard: mode|users|subscribed|banned|hosts.

Reads the SQLite database directly in read-only mode, so it has no side effects and needs no bot config.
"""

import os
import sqlite3
import sys
import time

path = os.path.join(os.getenv("DATA_DIR", "/data"), "servermanager.db")
try:
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=3)
    mode = (db.execute("SELECT value FROM settings WHERE key='mode'").fetchone() or ["free"])[0]
    users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    subs = db.execute("SELECT COUNT(*) FROM users WHERE sub_expires_at > ?", (int(time.time()),)).fetchone()[0]
    banned = db.execute("SELECT COALESCE(SUM(is_banned),0) FROM users").fetchone()[0]
    hosts = db.execute("SELECT COUNT(*) FROM hosts").fetchone()[0]
    print(f"{mode}|{users}|{subs}|{banned}|{hosts}")
except Exception:  # noqa: BLE001
    sys.exit(1)
