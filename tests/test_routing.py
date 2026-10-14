"""Every callback_data the UI can produce must be matched by a handler registered in main.register()."""

import re

from telegram import InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler

import main as m
from handlers import keyboards as K


def _patterns() -> list[re.Pattern]:
    app = Application.builder().token("123456789:AAH" + "x" * 32).build()
    m.register(app)
    out = []
    for group in app.handlers.values():
        for h in group:
            if isinstance(h, CallbackQueryHandler) and h.pattern is not None:
                out.append(h.pattern)
    return out


PATTERNS = _patterns()


def matches(data: str) -> bool:
    return any(p.match(data) for p in PATTERNS)


STATIC = [
    "menu:home", "noop", "lang:toggle", "terms:accept", "join:check", "me:home", "me:del", "me:delyes",
    "menu:hosts", "hl:3:1", "h:view:12", "h:view:0", "h:fav:12", "h:grp:12", "h:setgrp:12:3", "h:test:12", "h:test:0",
    "h:del:12", "h:delyes:12", "h:edit:12", "h:ef:12:label", "h:watch:12", "hosts:add",
    "wz:back", "wz:port22", "wz:auth:key", "wz:save", "wz:test",
    "h:conn:12", "h:connf:12", "h:sftp:12", "h:mon:12", "conn:cancel", "trust:yes", "trust:no",
    "h:tb:12", "h:tr:12:top", "h:tr:0:docker", "h:rb:12", "h:rbyes:12",
    "term:ctrlc", "term:up", "term:exit", "term:page:1", "term:page:0", "term:k:ctrl_x", "term:k:pgdn",
    "sf:rf", "sf:pg:1", "sf:up", "sf:dm", "sf:md", "sf:cd:0", "sf:dl:0", "sf:del:0", "sf:delyes:0", "sf:exit", "sf:uph",
    "snip:list", "snip:view:1", "snip:del:1", "snip:delyes:1", "snip:add", "snip:run:1", "snip:close",
    "grp:list", "grp:view:1", "grp:del:1", "grp:delyes:1", "grp:add",
    "adm:home", "adm:st", "adm:users:all:0", "adm:users:sub:2", "adm:u:5", "adm:ban:5", "adm:unban:5",
    "adm:revoke:5", "adm:revokeyes:5", "adm:del:5", "adm:delyes:5", "adm:grantnew", "adm:grant:5",
    "adm:find", "adm:msg:5", "adm:mode", "adm:modeyes:free", "adm:modeyes:paid",
    "adm:bc", "adm:bcaud:all", "adm:bcaud:subs", "af:bcgo",
    "adm:ch", "adm:chdel:1", "adm:chadd", "adm:bk", "adm:bknow", "adm:rs", "af:rsgo",
    "adm:ss", "adm:kill:5", "adm:set", "adm:live:1", "adm:live:-5", "adm:log",
]


def test_static_samples_are_routed():
    missing = [s for s in STATIC if not matches(s)]
    assert not missing, missing


def _buttons(markup: InlineKeyboardMarkup):
    for row in markup.inline_keyboard:
        for b in row:
            yield b


def test_every_button_built_by_the_keyboards_is_routed():
    """Build the real keyboards with sample data and check each callback_data (and its length)."""
    host = {"id": 12, "label": "web", "favorite": 0, "group_id": None, "watch": 1, "status": 1, "auth_type": "password"}
    local = {**host, "id": 0, "local": True}
    markups = [
        K.main_menu_kb("fa", True, True), K.main_menu_kb("en", False, False),
        K.gate_kb("fa"), K.contact_kb("fa"),
        K.hosts_list_kb("fa", [{"id": 3, "name": "g", "n": 2}], [host], 0, 0, 2, local_host=True),
        K.host_detail_kb("fa", host), K.host_detail_kb("fa", local), K.edit_fields_kb("fa", host),
        K.terminal_kb("fa", 0), K.terminal_kb("en", 1),
        K.toolbox_kb("fa", 12, ["top", "mem", "disk"]),
    ]
    seen = 0
    for mk in markups:
        for b in _buttons(mk):
            if b.callback_data is None:
                continue
            seen += 1
            assert len(b.callback_data.encode()) <= 64, b.callback_data
            assert matches(b.callback_data), f"unrouted callback: {b.callback_data}"
    assert seen > 40
