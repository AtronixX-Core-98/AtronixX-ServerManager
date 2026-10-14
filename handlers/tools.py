"""tools.py - saved commands (snippets), server groups and the server monitor"""

from __future__ import annotations

import asyncio
import logging
import shlex

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from core import registry
from core.jdate import fmt_num
from database.db import db
from handlers import keyboards as K
from handlers import ui
from locales.strings import Raw, t

logger = logging.getLogger("servermanager.tools")

MAX_SNIPPETS = 50
MAX_GROUPS = 30


# ================================================================== saved commands
async def cb_snip_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    uid, lang = update.effective_user.id, ui.lang_of(context)
    snippets = await db.list_snippets(uid)
    rows = [[K.btn(f"⚡ {s['name']}", f"snip:view:{s['id']}")] for s in snippets]
    rows.append([K.btn(t("b_add_snip", lang), "snip:add", K.SUCCESS), K.btn(t("b_back", lang), "menu:home")])
    text = t("snip_title", lang, count=fmt_num(len(snippets), lang)) if snippets else t("snip_empty", lang)
    await ui.show(update, context, text, K.kb(rows))


async def cb_snip_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    uid, lang = update.effective_user.id, ui.lang_of(context)
    s = await db.get_snippet(int(q.data.split(":")[2]), uid)
    if not s:
        return
    rows = [[K.btn(t("b_delete", lang), f"snip:del:{s['id']}", K.DANGER), K.btn(t("b_back", lang), "snip:list")]]
    await ui.show(update, context, t("snip_view", lang, name=s["name"], cmd=s["command"][:1500]), K.kb(rows))


async def cb_snip_del(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    lang, sid = ui.lang_of(context), int(q.data.split(":")[2])
    if q.data.startswith("snip:delyes"):
        await db.delete_snippet(sid, update.effective_user.id)
        await cb_snip_list(update, context)
        return
    await ui.show(update, context, t("snip_delete_confirm", lang), K.danger_confirm_kb(lang, f"snip:delyes:{sid}", f"snip:view:{sid}", t("b_delete_yes", lang)))


async def cb_snip_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    uid, lang = update.effective_user.id, ui.lang_of(context)
    if len(await db.list_snippets(uid)) >= MAX_SNIPPETS:
        await ui.show(update, context, t("snip_limit", lang), K.back_kb(lang, "snip:list"))
        return
    msg = await ui.show(update, context, t("snip_ask_name", lang), K.back_kb(lang, "snip:list"))
    context.user_data["flow"] = {"type": "snip_add", "step": "name", "mid": msg.message_id, "data": {}}


async def cb_snip_run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run a saved command inside the live session (from the picker message)."""
    q = update.callback_query
    uid, chat_id, lang = update.effective_user.id, update.effective_chat.id, ui.lang_of(context)
    session = registry.active_sessions.get(chat_id)
    if session is None or session.is_closed:
        await q.answer(t("no_session", lang), show_alert=True)
        return
    s = await db.get_snippet(int(q.data.split(":")[2]), uid)
    if not s:
        await q.answer()
        return
    await session.send_text(s["command"].replace("\r\n", "\n").replace("\n", "\r"))
    await q.answer(t("snip_sent", lang, name=s["name"]))


async def cb_snip_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    await ui.delete_message(update.callback_query.message)


# ================================================================== groups
async def cb_grp_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    uid, lang = update.effective_user.id, ui.lang_of(context)
    groups = await db.list_groups(uid)
    rows = [[K.btn(f"🗂 {g['name']} ({fmt_num(g['n'], lang)})", f"grp:view:{g['id']}")] for g in groups]
    rows.append([K.btn(t("b_add_group", lang), "grp:add", K.SUCCESS), K.btn(t("b_back", lang), "menu:home")])
    await ui.show(update, context, t("groups_title", lang) if groups else t("groups_empty", lang), K.kb(rows))


async def cb_grp_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    uid, lang = update.effective_user.id, ui.lang_of(context)
    gid = int(q.data.split(":")[2])
    g = await db.get_group(gid, uid)
    if not g:
        return
    n = len(await db.list_hosts(uid, gid))
    rows = [
        [K.btn(t("b_open", lang), f"hl:{gid}:0", K.PRIMARY)],
        [K.btn(t("b_delete", lang), f"grp:del:{gid}", K.DANGER), K.btn(t("b_back", lang), "grp:list")],
    ]
    await ui.show(update, context, t("group_view", lang, name=g["name"], count=fmt_num(n, lang)), K.kb(rows))


async def cb_grp_del(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    uid, lang, gid = update.effective_user.id, ui.lang_of(context), int(q.data.split(":")[2])
    if q.data.startswith("grp:delyes"):
        await db.delete_group(gid, uid)
        await cb_grp_list(update, context)
        return
    await ui.show(update, context, t("group_delete_confirm", lang), K.danger_confirm_kb(lang, f"grp:delyes:{gid}", f"grp:view:{gid}", t("b_delete_yes", lang)))


async def cb_grp_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    uid, lang = update.effective_user.id, ui.lang_of(context)
    if len(await db.list_groups(uid)) >= MAX_GROUPS:
        await ui.show(update, context, t("group_limit", lang), K.back_kb(lang, "grp:list"))
        return
    msg = await ui.show(update, context, t("group_ask_name", lang), K.back_kb(lang, "grp:list"))
    context.user_data["flow"] = {"type": "grp_add", "mid": msg.message_id}


async def flow_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    flow = context.user_data.get("flow")
    if not flow or flow.get("type") not in ("snip_add", "grp_add"):
        return False
    uid, chat_id, lang = update.effective_user.id, update.effective_chat.id, ui.lang_of(context)
    text = (update.message.text or "").strip()
    await ui.delete_message(update.message)
    bot, mid = context.bot, flow["mid"]

    if flow["type"] == "grp_add":
        if not 1 <= len(text) <= 24:
            await ui.edit(bot, chat_id, mid, t("err_group_name", lang) + "\n\n" + t("group_ask_name", lang), K.back_kb(lang, "grp:list"))
            return True
        await db.add_group(uid, text)
        context.user_data.pop("flow", None)
        groups = await db.list_groups(uid)
        rows = [[K.btn(f"🗂 {g['name']} ({fmt_num(g['n'], lang)})", f"grp:view:{g['id']}")] for g in groups]
        rows.append([K.btn(t("b_add_group", lang), "grp:add", K.SUCCESS), K.btn(t("b_back", lang), "menu:home")])
        await ui.edit(bot, chat_id, mid, t("group_created", lang) + "\n\n" + t("groups_title", lang), K.kb(rows))
        return True

    # snip_add
    if flow["step"] == "name":
        if not 1 <= len(text) <= 32:
            await ui.edit(bot, chat_id, mid, t("err_snip_name", lang) + "\n\n" + t("snip_ask_name", lang), K.back_kb(lang, "snip:list"))
            return True
        flow["data"]["name"] = text
        flow["step"] = "cmd"
        await ui.edit(bot, chat_id, mid, t("snip_ask_cmd", lang, name=text), K.back_kb(lang, "snip:list"))
        return True
    if not 1 <= len(text) <= 1000:
        await ui.edit(bot, chat_id, mid, t("err_snip_cmd", lang) + "\n\n" + t("snip_ask_cmd", lang, name=flow["data"]["name"]), K.back_kb(lang, "snip:list"))
        return True
    await db.add_snippet(uid, flow["data"]["name"], text)
    context.user_data.pop("flow", None)
    snippets = await db.list_snippets(uid)
    rows = [[K.btn(f"⚡ {s['name']}", f"snip:view:{s['id']}")] for s in snippets]
    rows.append([K.btn(t("b_add_snip", lang), "snip:add", K.SUCCESS), K.btn(t("b_back", lang), "menu:home")])
    await ui.edit(bot, chat_id, mid, t("snip_saved", lang) + "\n\n" + t("snip_title", lang, count=fmt_num(len(snippets), lang)), K.kb(rows))
    return True


# ================================================================== monitor
# One POSIX-sh script (works on dash/busybox) that prints key=value lines; parsing happens here.
_MON_SCRIPT = r"""
export LC_ALL=C
cpu() { read -r _ a b c d e f g h _ </proc/stat; echo "$((a+b+c+d+e+f+g+h)) $((d+e))"; }
set -- $(cpu); t1=$1; i1=$2; sleep 1; set -- $(cpu); t2=$1; i2=$2
dt=$((t2-t1)); di=$((i2-i1)); [ "$dt" -gt 0 ] && echo "cpu=$(( (100*(dt-di))/dt ))"
echo "cores=$(nproc 2>/dev/null || grep -c '^processor' /proc/cpuinfo 2>/dev/null)"
echo "load=$(cut -d' ' -f1-3 /proc/loadavg 2>/dev/null)"
echo "mem=$(free -m 2>/dev/null | awk '/^Mem:/{u=($7!=""?$2-$7:$3); print $2" "u}')"
echo "swap=$(free -m 2>/dev/null | awk '/^Swap:/{print $2" "$3}')"
echo "disk=$(df -P / 2>/dev/null | awk 'NR==2{print $2" "$3}')"
echo "uptime=$(cut -d. -f1 /proc/uptime 2>/dev/null)"
echo "os=$( (. /etc/os-release 2>/dev/null; echo "$PRETTY_NAME") )"
echo "kernel=$(uname -r 2>/dev/null)"
echo "host=$(hostname 2>/dev/null)"
ps -eo pcpu,pmem,comm --sort=-pcpu 2>/dev/null | sed -n '2,4p' | while read -r c m n; do echo "top=$n $c $m"; done
command -v docker >/dev/null 2>&1 && echo "containers=$(docker ps -q 2>/dev/null | wc -l)"
command -v systemctl >/dev/null 2>&1 && echo "failed=$(systemctl --failed --no-legend 2>/dev/null | wc -l)"
exit 0
"""
_MON_CMD = "sh -c " + shlex.quote(_MON_SCRIPT)


def _bar(pct: float) -> str:
    filled = max(0, min(10, round(pct / 10)))
    return "▰" * filled + "▱" * (10 - filled)


def _ints(text: str, n: int) -> list[int] | None:
    parts = text.split()
    if len(parts) < n:
        return None
    try:
        return [int(x) for x in parts[:n]]
    except ValueError:
        return None


def _fmt_mb(mb: float) -> str:
    return f"{mb / 1024:.1f} GB" if mb >= 1024 else f"{mb:.0f} MB"


def _fmt_uptime(seconds: int, lang: str) -> str:
    d, rem = divmod(max(0, seconds), 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if lang == "fa":
        parts = ([f"{d} روز"] if d else []) + ([f"{h} ساعت"] if h else []) + ([f"{m} دقیقه"] if m or not (d or h) else [])
        return " و ".join(parts)
    return " ".join(([f"{d}d"] if d else []) + ([f"{h}h"] if h else []) + ([f"{m}m"] if m or not (d or h) else []))


def parse_monitor(out: str) -> dict:
    data: dict = {"top": []}
    for line in (out or "").splitlines():
        key, sep, value = line.partition("=")
        if not sep:
            continue
        if key == "top":
            data["top"].append(value.strip())
        else:
            data[key] = value.strip()
    return data


def format_monitor(out: str, lang: str) -> str:
    d = parse_monitor(out)
    rows: list[str] = []
    if d.get("os") or d.get("host"):
        rows.append(f"🐧 <b>{ui.esc(d.get('os') or '—')}</b>" + (f" · <code>{ui.esc(d['host'])}</code>" if d.get("host") else ""))
    if d.get("kernel") or d.get("uptime", "").isdigit():
        bits = []
        if d.get("kernel"):
            bits.append(f"{t('mon_kernel', lang)} <code>{ui.esc(d['kernel'])}</code>")
        if d.get("uptime", "").isdigit():
            bits.append(f"⏱ {ui.esc(_fmt_uptime(int(d['uptime']), lang))}")
        rows.append(" · ".join(bits))
    rows.append("")
    if d.get("cpu", "").isdigit():
        pct = int(d["cpu"])
        extra = f"\n      <code>{ui.esc(d['load'])}</code>" if d.get("load") else ""
        if d.get("cores"):
            extra += f" · {ui.esc(d['cores'])} {t('mon_cores', lang)}"
        rows.append(f"⚙️ <b>CPU</b>  {_bar(pct)} {fmt_num(pct, lang)}%{extra}")
    m = _ints(d.get("mem", ""), 2)
    if m and m[0] > 0:
        pct = m[1] * 100 / m[0]
        rows.append(f"🧠 <b>RAM</b>  {_bar(pct)} {fmt_num(round(pct), lang)}%\n      <code>{_fmt_mb(m[1])} / {_fmt_mb(m[0])}</code>")
    sw = _ints(d.get("swap", ""), 2)
    if sw and sw[0] > 0:
        pct = sw[1] * 100 / sw[0]
        rows.append(f"🔁 <b>Swap</b> {_bar(pct)} {fmt_num(round(pct), lang)}%\n      <code>{_fmt_mb(sw[1])} / {_fmt_mb(sw[0])}</code>")
    dk = _ints(d.get("disk", ""), 2)
    if dk and dk[0] > 0:
        pct = dk[1] * 100 / dk[0]
        rows.append(f"💽 <b>Disk</b> {_bar(pct)} {fmt_num(round(pct), lang)}%\n      <code>{dk[1] / 1048576:.1f} / {dk[0] / 1048576:.1f} GB</code>")
    extras = []
    if d.get("containers", "").isdigit():
        extras.append(f"🐳 {t('mon_containers', lang)}: <b>{ui.esc(d['containers'])}</b>")
    if d.get("failed", "").isdigit():
        extras.append(f"{'⚠️' if d['failed'] != '0' else '✅'} {t('mon_failed', lang)}: <b>{ui.esc(d['failed'])}</b>")
    if extras:
        rows.append(" · ".join(extras))
    if d["top"]:
        tops = []
        for item in d["top"]:
            name, _, rest = item.partition(" ")
            cpu_s, _, mem_s = rest.partition(" ")
            tops.append(f"{ui.esc(name[:18])} {ui.esc(cpu_s)}% / {ui.esc(mem_s)}%")
        rows.append(f"🔥 <b>{t('mon_top', lang)}</b>\n      <code>" + "\n      ".join(tops) + "</code>")
    body = "\n".join(rows).strip()
    return body if len(rows) > 2 else t("mon_no_data", lang)


async def launch_monitor(bot, chat_id: int, mid: int, uid: int, lang: str, host: dict, conn) -> None:
    """Registered in registry.actions: take one snapshot of the server's stats, then close the connection."""
    try:
        res = await asyncio.wait_for(conn.run(_MON_CMD, check=False), 25)
        body = format_monitor(res.stdout if isinstance(res.stdout, str) else "", lang)
    except asyncio.TimeoutError:
        body = t("mon_timeout", lang)
    finally:
        await registry._close_conn(conn)
    kb = K.kb([[K.btn(t("b_refresh", lang), f"h:mon:{host['id']}", K.PRIMARY)], [K.btn(t("b_back", lang), f"h:view:{host['id']}")]])
    await ui.edit(bot, chat_id, mid, t("mon_view", lang, label=host["label"], body=Raw(body)), kb)
