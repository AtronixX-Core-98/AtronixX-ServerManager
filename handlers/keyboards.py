"""
keyboards.py - inline keyboards

Buttons use the coloured style from Bot API 9.4 (style = primary / success / danger).
Older Telegram clients show them uncoloured; everything still works.
"""

from __future__ import annotations

from typing import Iterable, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import credits
from config import settings
from core.jdate import fmt_num
from locales.strings import t

PRIMARY, SUCCESS, DANGER = "primary", "success", "danger"


def btn(text: str, data: Optional[str] = None, style: Optional[str] = None, url: Optional[str] = None):
    kw = {"url": url} if url else {"callback_data": data}
    if style:
        try:
            return InlineKeyboardButton(text, style=style, **kw)
        except TypeError:  # older library version
            return InlineKeyboardButton(text, api_kwargs={"style": style}, **kw)
    return InlineKeyboardButton(text, **kw)


def kb(rows: Iterable[list]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([list(r) for r in rows if r])


def back_kb(lang: str, target: str = "menu:home") -> InlineKeyboardMarkup:
    return kb([[btn(t("b_back", lang), target)]])


def contact_kb(lang: str, back: str = "menu:home") -> InlineKeyboardMarkup:
    """Back button plus a support button (only when SUPPORT_USERNAME is configured)."""
    rows = []
    if settings.support_url:
        rows.append([btn(t("b_support", lang), url=settings.support_url)])
    rows.append([btn(t("b_back", lang), back)])
    return kb(rows)


def confirm_kb(lang: str, yes: str, no: str, yes_label: Optional[str] = None) -> InlineKeyboardMarkup:
    return kb([[btn(yes_label or t("b_yes", lang), yes, SUCCESS), btn(t("b_cancel", lang), no, DANGER)]])


def danger_confirm_kb(lang: str, yes: str, no: str, yes_label: Optional[str] = None) -> InlineKeyboardMarkup:
    return kb([[btn(yes_label or t("b_yes", lang), yes, DANGER), btn(t("b_cancel", lang), no)]])


# ------------------------------------------------------------------ main menu
def main_menu_kb(lang: str, admin: bool, local_host: bool = False) -> InlineKeyboardMarkup:
    rows = []
    if local_host:
        rows.append([btn(t("b_this_server", lang), "h:view:0", PRIMARY)])
    rows += [
        [btn(t("b_hosts", lang), "menu:hosts", PRIMARY), btn(t("b_add", lang), "hosts:add", SUCCESS)],
        [btn(t("b_snip", lang), "snip:list"), btn(t("b_groups", lang), "grp:list")],
        [btn(t("b_account", lang), "me:home"), btn(t("b_lang", lang), "lang:toggle")],
    ]
    if settings.support_url:
        rows.append([btn(t("b_support", lang), url=settings.support_url)])
    if admin:
        rows.append([btn(t("b_admin", lang), "adm:home", PRIMARY)])
    rows.append([btn(t("b_credit", lang), url=credits.CHANNEL_URL)])
    return kb(rows)


def gate_kb(lang: str, extra: Optional[list] = None) -> InlineKeyboardMarkup:
    rows = list(extra or [])
    last = []
    if settings.support_url:
        last.append(btn(t("b_support", lang), url=settings.support_url))
    last.append(btn(t("b_lang", lang), "lang:toggle"))
    rows.append(last)
    return kb(rows)


# ------------------------------------------------------------------ servers
def hosts_list_kb(lang: str, groups: list, hosts: list, gid: int, page: int, pages: int, local_host: bool = False) -> InlineKeyboardMarkup:
    rows: list[list] = []
    if local_host and gid == 0 and page == 0:
        rows.append([btn(t("b_this_server", lang), "h:view:0", PRIMARY)])
    if gid == 0 and page == 0:
        gbtns = [btn(f"🗂 {g['name']} ({fmt_num(g['n'], lang)})", f"hl:{g['id']}:0") for g in groups[:12]]
        rows += [gbtns[i : i + 2] for i in range(0, len(gbtns), 2)]
    for h in hosts:
        icon = "⭐" if h["favorite"] else "🖥"
        mark = {1: " 🟢", 0: " 🔴"}.get(h.get("status"), "") if h.get("watch") else ""
        rows.append([btn(f"{icon} {h['label']}{mark}", f"h:view:{h['id']}")])
    if pages > 1:
        nav = []
        if page > 0:
            nav.append(btn("◀️", f"hl:{gid}:{page - 1}"))
        nav.append(btn(f"{fmt_num(page + 1, lang)}/{fmt_num(pages, lang)}", "noop"))
        if page < pages - 1:
            nav.append(btn("▶️", f"hl:{gid}:{page + 1}"))
        rows.append(nav)
    rows.append([btn(t("b_add", lang), "hosts:add", SUCCESS), btn(t("b_back", lang), "menu:home" if gid == 0 else "hl:0:0")])
    return kb(rows)


def host_detail_kb(lang: str, host: dict) -> InlineKeyboardMarkup:
    hid = host["id"]
    if host.get("local"):   # "This server": no edit / delete / group / watch
        return kb(
            [
                [btn(t("b_connect", lang), f"h:conn:{hid}", SUCCESS)],
                [btn(t("b_files", lang), f"h:sftp:{hid}", PRIMARY), btn(t("b_monitor", lang), f"h:mon:{hid}", PRIMARY)],
                [btn(t("b_toolbox", lang), f"h:tb:{hid}", PRIMARY), btn(t("b_test", lang), f"h:test:{hid}")],
                [btn(t("b_back", lang), "menu:home")],
            ]
        )
    fav = t("b_unfav", lang) if host["favorite"] else t("b_fav", lang)
    watch = t("b_watch_off", lang) if host.get("watch") else t("b_watch_on", lang)
    back = f"hl:{host['group_id'] or 0}:0"
    return kb(
        [
            [btn(t("b_connect", lang), f"h:conn:{hid}", SUCCESS)],
            [btn(t("b_files", lang), f"h:sftp:{hid}", PRIMARY), btn(t("b_monitor", lang), f"h:mon:{hid}", PRIMARY)],
            [btn(t("b_toolbox", lang), f"h:tb:{hid}", PRIMARY), btn(watch, f"h:watch:{hid}")],
            [btn(t("b_test", lang), f"h:test:{hid}"), btn(fav, f"h:fav:{hid}")],
            [btn(t("b_move", lang), f"h:grp:{hid}"), btn(t("b_edit", lang), f"h:edit:{hid}")],
            [btn(t("b_delete", lang), f"h:del:{hid}", DANGER), btn(t("b_back", lang), back)],
        ]
    )


def edit_fields_kb(lang: str, host: dict) -> InlineKeyboardMarkup:
    hid = host["id"]
    rows = [
        [btn(t("f_label", lang), f"h:ef:{hid}:label"), btn(t("f_addr", lang), f"h:ef:{hid}:ip")],
        [btn(t("f_port", lang), f"h:ef:{hid}:port"), btn(t("f_user", lang), f"h:ef:{hid}:username")],
    ]
    if host["auth_type"] == "password":
        rows.append([btn(t("f_password", lang), f"h:ef:{hid}:secret")])
    rows.append([btn(t("b_back", lang), f"h:view:{hid}")])
    return kb(rows)


def group_pick_kb(lang: str, hid: int, groups: list) -> InlineKeyboardMarkup:
    rows = [[btn(f"🗂 {g['name']}", f"h:setgrp:{hid}:{g['id']}")] for g in groups]
    rows.append([btn(t("b_nogroup", lang), f"h:setgrp:{hid}:0")])
    rows.append([btn(t("b_back", lang), f"h:view:{hid}")])
    return kb(rows)


def trust_kb(lang: str) -> InlineKeyboardMarkup:
    return kb([[btn(t("b_trust", lang), "trust:yes", SUCCESS), btn(t("b_cancel", lang), "trust:no", DANGER)]])


def connecting_kb(lang: str) -> InlineKeyboardMarkup:
    return kb([[btn(t("b_cancel", lang), "conn:cancel", DANGER)]])


# ------------------------------------------------------------------ add-server wizard
def wizard_kb(lang: str, step: str, home: str) -> InlineKeyboardMarkup:
    rows: list[list] = []
    if step == "port":
        rows.append([btn(t("b_port22", lang), "wz:port22", PRIMARY)])
    elif step == "user":
        rows.append([btn(t("b_user_root", lang), "wz:userroot", PRIMARY)])
    elif step == "auth":
        rows.append([btn(t("b_auth_pw", lang), "wz:auth:password", PRIMARY), btn(t("b_auth_key", lang), "wz:auth:key", PRIMARY)])
    elif step == "confirm":
        rows.append([btn(t("b_save", lang), "wz:save", SUCCESS), btn(t("b_test", lang), "wz:test")])
    rows.append([btn(t("b_back", lang), "wz:back"), btn(t("b_cancel", lang), home, DANGER)])
    return kb(rows)


# ------------------------------------------------------------------ terminal
def terminal_kb(lang: str, page: int = 0) -> InlineKeyboardMarkup:
    if page == 1:   # second page of the control pad: editor / readline keys
        return kb(
            [
                [btn("Ctrl+X", "term:k:ctrl_x"), btn("Ctrl+O", "term:k:ctrl_o"), btn("Ctrl+A", "term:k:ctrl_a"), btn("Ctrl+E", "term:k:ctrl_e")],
                [btn("Ctrl+R", "term:k:ctrl_r"), btn("Ctrl+U", "term:k:ctrl_u"), btn("Ctrl+W", "term:k:ctrl_w"), btn("Ctrl+K", "term:k:ctrl_k")],
                [btn("Home", "term:k:home"), btn("End", "term:k:end"), btn("PgUp", "term:k:pgup"), btn("PgDn", "term:k:pgdn")],
                [btn("Ctrl+Z", "term:k:ctrl_z"), btn("Ctrl+L", "term:k:ctrl_l")],
                [btn(t("b_keys_back", lang), "term:page:0", PRIMARY), btn(t("b_exit", lang), "term:exit", DANGER)],
            ]
        )
    return kb(
        [
            [btn("Ctrl+C", "term:ctrlc", DANGER), btn("Ctrl+D", "term:ctrld"), btn("Tab", "term:tab"), btn("Esc", "term:esc")],
            [btn("◀️", "term:left"), btn("🔼", "term:up"), btn("🔽", "term:down"), btn("▶️", "term:right")],
            [btn(t("b_enter", lang), "term:enter", SUCCESS), btn(t("b_more_keys", lang), "term:page:1")],
            [btn(t("b_clear", lang), "term:clear"), btn(t("b_log", lang), "term:log"), btn(t("b_snip", lang), "term:snip")],
            [btn(t("b_exit", lang), "term:exit", DANGER)],
        ]
    )


# ------------------------------------------------------------------ toolbox
def toolbox_kb(lang: str, hid: int, tools: list[str]) -> InlineKeyboardMarkup:
    rows = []
    items = [btn(t("tb_" + key, lang), f"h:tr:{hid}:{key}") for key in tools]
    rows += [items[i : i + 2] for i in range(0, len(items), 2)]
    rows.append([btn(t("tb_reboot", lang), f"h:rb:{hid}", DANGER)])
    rows.append([btn(t("b_back", lang), f"h:view:{hid}")])
    return kb(rows)


# ------------------------------------------------------------------ files (SFTP)
def sftp_kb(lang: str, entries: list, page: int, pages: int, per_page: int, at_root: bool, mode: str) -> InlineKeyboardMarkup:
    rows: list[list] = []
    start = page * per_page
    for i, e in enumerate(entries[start : start + per_page], start=start):
        if e["is_dir"]:
            label = f"🗑 📁 {e['name']}" if mode == "delete" else f"📁 {e['name']}"
        else:
            label = f"🗑 📄 {e['name']}" if mode == "delete" else f"📄 {e['name']}"
        rows.append([btn(label[:60], f"sf:{'del' if mode == 'delete' else ('cd' if e['is_dir'] else 'dl')}:{i}", DANGER if mode == "delete" else None)])
    if pages > 1:
        nav = []
        if page > 0:
            nav.append(btn("◀️", f"sf:pg:{page - 1}"))
        nav.append(btn(f"{fmt_num(page + 1, lang)}/{fmt_num(pages, lang)}", "noop"))
        if page < pages - 1:
            nav.append(btn("▶️", f"sf:pg:{page + 1}"))
        rows.append(nav)
    tools = []
    if not at_root:
        tools.append(btn(t("b_up", lang), "sf:up", PRIMARY))
    tools += [btn(t("b_refresh", lang), "sf:rf"), btn(t("b_upload", lang), "sf:uph", SUCCESS)]
    rows.append(tools)
    rows.append(
        [
            btn(t("b_mkdir", lang), "sf:md"),
            btn(t("b_delmode_off", lang) if mode == "delete" else t("b_delmode", lang), "sf:dm", DANGER if mode != "delete" else None),
        ]
    )
    rows.append([btn(t("b_exit", lang), "sf:exit", DANGER)])
    return kb(rows)
