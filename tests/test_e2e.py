"""End-to-end flows through the real handlers with a fake Telegram (no network, no SSH)."""

import asyncio

import pytest
from telegram.ext import Application

import main as m
from config import settings
from database.db import db
from tests.fake_telegram import FakeRequest, callback_update, message_update

ADMIN = settings.admin_id
USER = 77


@pytest.fixture
async def env():
    req = FakeRequest()
    app = (Application.builder().token("123456789:AAH" + "x" * 32).request(req).get_updates_request(FakeRequest())
           .concurrent_updates(m.OrderedProcessor(4)).build())
    m.register(app)
    m.register_actions()
    await db.open()
    await db.set_mode("free")
    await app.initialize()
    yield app, req
    await app.shutdown()
    await db.close()


async def say(app, req, uid, text):
    await app.process_update(message_update(app.bot, uid, text))


async def tap(app, req, uid, data, mid=777):
    await app.process_update(callback_update(app.bot, uid, data, mid))


async def test_admin_start_shows_branded_menu_without_old_branding(env):
    app, req = env
    await say(app, req, ADMIN, "/start")
    text = req.last_text()
    assert "TestBrand" in text
    cbs = req.callbacks()
    assert "menu:hosts" in cbs and "hosts:add" in cbs and "adm:home" in cbs
    assert "h:view:0" not in cbs                 # host access is off by default
    urls = [b["url"] for b in req.buttons() if "url" in b]
    assert urls == ["https://t.me/AtronixX_Core"]       # only the project credit; no support button without SUPPORT_USERNAME
    await say(app, req, ADMIN, "/help")
    assert "AtronixX-Core" in req.last_text() and "@AtronixX_Support" in req.last_text()


async def test_new_user_terms_then_menu_and_id_command(env):
    app, req = env
    await say(app, req, USER, "/start")
    assert "terms:accept" in req.callbacks()
    await tap(app, req, USER, "terms:accept")
    assert "menu:hosts" in req.callbacks()
    await say(app, req, USER, "/id")
    assert str(USER) in req.last_text()
    await say(app, req, USER, "/help")
    assert "/cancel" in req.last_text()


async def test_language_toggle_switches_texts(env):
    app, req = env
    await tap(app, req, USER, "lang:toggle")
    assert "Hi" in req.last_text() or "Terminal" in req.last_text()
    await tap(app, req, USER, "lang:toggle")
    assert "سلام" in req.last_text()


async def test_add_server_wizard_validation_and_save_and_watch(env):
    app, req = env
    await db.ensure_user(USER, "u", "User")
    await db.accept_terms(USER)
    await tap(app, req, USER, "hosts:add")
    await say(app, req, USER, "web1")                       # name
    await say(app, req, USER, "localhost")                  # not a valid address
    assert "❗" in req.last_text()
    await say(app, req, USER, "10.1.2.3")                   # private -> blocked
    assert "⛔" in req.last_text()
    await say(app, req, USER, "8.8.8.8")
    await tap(app, req, USER, "wz:port22")
    await say(app, req, USER, "root")
    await tap(app, req, USER, "wz:auth:password")
    req.clear()
    await say(app, req, USER, "p@ss<word>&")                # secret: message must be deleted immediately
    assert req.api_called("deleteMessage")
    assert "p@ss" not in req.texts()
    await tap(app, req, USER, "wz:save")
    hosts = await db.list_hosts(USER)
    assert len(hosts) == 1 and hosts[0]["ip"] == "8.8.8.8"
    hid = hosts[0]["id"]
    assert (await db.get_host_decrypted(hid, USER))["secret"] == "p@ss<word>&"
    await tap(app, req, USER, f"h:watch:{hid}")
    assert (await db.get_host(hid, USER))["watch"] == 1
    await tap(app, req, USER, f"h:view:{hid}")
    assert "🔔" in req.last_text()
    await tap(app, req, USER, f"h:watch:{hid}")
    assert (await db.get_host(hid, USER))["watch"] == 0
    await tap(app, req, USER, "h:view:0")                    # a normal user must not reach "This server"
    assert "h:conn:0" not in req.callbacks()
    for key in ("h:tb:%d" % hid, "menu:hosts", "me:home", "snip:list", "grp:list"):
        await tap(app, req, USER, key)                       # every menu renders valid HTML in this language


async def test_admin_panel_screens_and_grant_flow(env):
    app, req = env
    await db.ensure_user(ADMIN, "admin", "Admin")
    for data in ("adm:home", "adm:st", "adm:users:all:0", "adm:set", "adm:log", "adm:bk", "adm:mode", "adm:ss", "adm:ch", "adm:bc"):
        await tap(app, req, ADMIN, data)
    await tap(app, req, ADMIN, "adm:set")
    assert "🏠" in req.last_text()                           # settings mention "This server" access
    await tap(app, req, ADMIN, "adm:grantnew")
    await say(app, req, ADMIN, "88")
    await say(app, req, ADMIN, "30")
    await say(app, req, ADMIN, "5")
    u = await db.get_user(88)
    assert u and u["sub_max_hosts"] == 5
    req.clear()
    await tap(app, req, ADMIN, "adm:bknow")
    for _ in range(40):                                      # the backup runs in a background task
        if req.api_called("sendDocument"):
            break
        await asyncio.sleep(0.1)
    assert req.api_called("sendDocument")
    doc = [p for a, p in req.calls if a == "sendDocument"][0]
    assert "TestBrand" in doc["caption"]


async def test_paid_mode_blocks_without_plan_and_hides_support_button(env):
    app, req = env
    await db.set_mode("paid")
    await say(app, req, 4321, "/start")
    await tap(app, req, 4321, "terms:accept") if "terms:accept" in req.callbacks() else None
    text = req.texts()
    assert "4321" in text                                    # shows the ID to give to the admin
    assert not any("url" in b and "Support" in b["url"] for b in req.buttons())


async def test_unrouted_text_and_cancel(env):
    app, req = env
    await say(app, req, USER, "hello there")
    assert req.sent()
    await say(app, req, USER, "/cancel")
    assert "menu:hosts" in req.callbacks()
