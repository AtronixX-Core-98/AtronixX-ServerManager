"""Startup / shutdown path and the availability watchdog state machine."""

import logging

import pytest
from telegram.ext import Application

import main as m
from core import watchdog
from database.db import db
from tests.fake_telegram import FakeRequest

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def app_req():
    req = FakeRequest()
    app = Application.builder().token("123456789:AAH" + "x" * 32).request(req).get_updates_request(FakeRequest()).build()
    m.register(app)
    await app.initialize()
    yield app, req
    await app.shutdown()


async def test_post_init_announces_and_logs_the_line_the_installer_waits_for(app_req, caplog):
    app, req = app_req
    caplog.set_level(logging.INFO, logger="servermanager")
    await m.post_init(app)
    try:
        assert any("started as @" in r.getMessage() for r in caplog.records)       # `servermanager install` greps for this
        assert any(a == "setMyCommands" for a, _ in req.calls)
        assert "1.0.0" in req.texts() and "TestBrand" not in "x"                    # boot notice mentions the version
        assert {"terminal", "sftp", "monitor", "reboot", "tool_disk"} <= set(m.registry.actions)
    finally:
        await m.post_shutdown(app)


async def test_watchdog_alerts_after_two_failures_and_when_back(app_req, monkeypatch):
    app, req = app_req
    await db.open()
    try:
        await db.set_mode("free")
        await db.ensure_user(31, "w", "W")
        await db.accept_terms(31)
        hid = await db.add_host(owner=31, label="edge-1", ip="8.8.8.8", port=22, username="root", auth_type="password", secret="x")
        await db.set_watch(hid, 31, True)

        results = iter([False, False, False, True])

        async def fake_tcp(target, port, timeout=6):
            return next(results)

        monkeypatch.setattr(watchdog, "tcp_reachable", fake_tcp)

        await watchdog.check_all(app.bot)          # 1st failure: not yet an alert
        assert "edge-1" not in req.texts()
        await watchdog.check_all(app.bot)          # 2nd failure: down
        assert "🔴" in req.texts() and "edge-1" in req.texts()
        n = len(req.sent())
        await watchdog.check_all(app.bot)          # still down: no repeated alert
        assert len(req.sent()) == n
        await watchdog.check_all(app.bot)          # back up
        assert "🟢" in req.texts()
        row = (await db.watched_hosts())[0]
        assert row["status"] == 1 and row["fail_count"] == 0
    finally:
        await db.close()


async def test_tcp_reachable_refuses_internal_targets():
    assert await watchdog.tcp_reachable("127.0.0.1", 22) is False
    assert await watchdog.tcp_reachable("10.0.0.5", 22) is False
