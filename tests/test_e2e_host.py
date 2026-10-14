"""End-to-end through the real handlers and a real sshd: 'This server' access, terminal, files, monitor, toolbox."""

import asyncio
import dataclasses
import os
import shutil
import time

import pytest
from telegram.ext import Application

import core.hostaccess as hostaccess
import main as m
from config import settings
from core import registry
from database.db import db
from tests.fake_telegram import FakeRequest, callback_update, message_update

pytestmark = pytest.mark.skipif(not os.path.exists(shutil.which("sshd") or "/usr/sbin/sshd"), reason="sshd not available")

ADMIN = settings.admin_id


@pytest.fixture
async def env(sshd, local_access):
    req = FakeRequest()
    app = (Application.builder().token("123456789:AAH" + "x" * 32).request(req).get_updates_request(FakeRequest())
           .concurrent_updates(m.OrderedProcessor(4)).build())
    m.register(app)
    m.register_actions()
    await db.open()
    await db.set_mode("free")
    await db.ensure_user(ADMIN, "admin", "Admin")
    await app.initialize()
    yield app, req
    await registry.close_all()
    await asyncio.sleep(0.1)
    await app.shutdown()
    await db.close()


async def tap(app, uid, data, mid=777):
    await app.process_update(callback_update(app.bot, uid, data, mid))


async def say(app, uid, text):
    await app.process_update(message_update(app.bot, uid, text))


async def wait_for(pred, timeout=10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        await asyncio.sleep(0.1)
    return False


async def test_menu_offers_this_server_to_the_admin_only(env):
    app, req = env
    await say(app, ADMIN, "/start")
    assert "h:view:0" in req.callbacks()
    await db.ensure_user(55, "u", "U")
    await db.accept_terms(55)
    req.clear()
    await say(app, 55, "/start")
    assert "h:view:0" not in req.callbacks()
    await tap(app, 55, "h:view:0")
    assert "h:conn:0" not in req.callbacks()
    await tap(app, 55, "h:conn:0")
    assert not registry.active_sessions and not registry.connecting


async def test_terminal_session_through_the_bot(env):
    app, req = env
    await tap(app, ADMIN, "h:view:0")
    assert {"h:conn:0", "h:sftp:0", "h:mon:0", "h:tb:0"} <= set(req.callbacks())
    assert "h:del:0" not in req.callbacks() and "h:edit:0" not in req.callbacks()
    await tap(app, ADMIN, "h:conn:0")
    assert await wait_for(lambda: ADMIN in registry.active_sessions), req.texts()
    assert await wait_for(lambda: any("<pre>" in p.get("text", "") for p in req.sent("editMessageText"))), req.texts()

    req.clear()
    await say(app, ADMIN, "echo e2e-$((1+2))")
    assert req.api_called("deleteMessage")                       # typed text never stays in the chat
    assert await wait_for(lambda: "e2e-3" in req.texts()), req.texts()

    await tap(app, ADMIN, "term:page:1")
    assert any("term:k:ctrl_x" in c for c in req.callbacks(req.sent("editMessageReplyMarkup")[-1] if req.sent("editMessageReplyMarkup") else None) or [])
    await tap(app, ADMIN, "term:k:ctrl_l")
    await tap(app, ADMIN, "term:page:0")
    await tap(app, ADMIN, "term:exit")
    assert ADMIN not in registry.active_sessions


async def test_unpinned_host_asks_for_fingerprint_confirmation(env, local_access, monkeypatch, sshd):
    app, req = env
    monkeypatch.setattr(hostaccess, "settings", dataclasses.replace(local_access, host_fingerprints=()))
    await db.set_setting("local_host_fp", "")
    await tap(app, ADMIN, "h:conn:0")
    assert await wait_for(lambda: "trust:yes" in req.callbacks()), req.texts()
    assert sshd["fp"] in req.texts()
    await tap(app, ADMIN, "trust:yes")
    assert await wait_for(lambda: ADMIN in registry.active_sessions), req.texts()
    assert await db.get_setting("local_host_fp") == sshd["fp"]


async def test_toolbox_monitor_and_files(env):
    app, req = env
    await tap(app, ADMIN, "h:tb:0")
    assert "h:tr:0:disk" in req.callbacks() and "h:rb:0" in req.callbacks()
    await tap(app, ADMIN, "h:tr:0:disk")
    assert await wait_for(lambda: "Filesystem" in req.texts()), req.texts()
    await tap(app, ADMIN, "h:tr:0:ports")
    assert await wait_for(lambda: "🔌 پورت‌های باز</b>" in req.texts()), req.texts()   # (ss may be missing on the box: empty output is handled)

    req.clear()
    await tap(app, ADMIN, "h:mon:0")
    assert await wait_for(lambda: "CPU" in req.texts() and "RAM" in req.texts()), req.texts()

    req.clear()
    await tap(app, ADMIN, "h:sftp:0")
    assert await wait_for(lambda: any("sf:" in c for c in req.callbacks())), req.texts()
    assert "📁" in req.texts()
    await tap(app, ADMIN, "sf:exit")
    assert ADMIN not in registry.sftp_state

    await tap(app, ADMIN, "h:rb:0")                              # confirmation only; the reboot itself is never run here
    assert "h:rbyes:0" in req.callbacks()


async def test_rate_limit_and_connect_errors_are_friendly(env, local_access, monkeypatch):
    app, req = env
    monkeypatch.setattr(hostaccess, "settings", dataclasses.replace(local_access, host_port=2299))
    await tap(app, ADMIN, "h:test:0")
    assert "🚪" in req.texts()                                   # refused -> friendly explanation, not a stack trace
