"""
toolbox.py - one-tap, non-interactive server tools (processes, disk, ports, docker, failed services,
logins, updates...) and a confirmed reboot. Output is shown right in the chat.

Everything goes through terminal.start_action, so the host-key confirmation, rate limit and
connection handling are exactly the same as for the terminal.
"""

from __future__ import annotations

import asyncio
import logging
import re
import shlex

from telegram import Update
from telegram.ext import ContextTypes

from core import registry
from core.ssh_manager import run_command
from handlers import keyboards as K
from handlers import terminal, ui
from locales.strings import Raw, t

logger = logging.getLogger("servermanager.toolbox")

# key -> shell command (run with `sh -c`, output is stdout+stderr)
TOOLS: dict[str, str] = {
    "top": "ps -eo pid,pcpu,pmem,comm --sort=-pcpu 2>/dev/null | head -n 11",
    "mem": "ps -eo pid,pmem,rss,comm --sort=-pmem 2>/dev/null | head -n 11",
    "disk": "df -hP -x tmpfs -x devtmpfs -x squashfs -x overlay 2>/dev/null | head -n 20",
    "du": "du -xh --max-depth=1 /var 2>/dev/null | sort -rh | head -n 12",
    "ports": "(ss -tuln 2>/dev/null || netstat -tuln 2>/dev/null) | head -n 40",
    "net": "ip -brief addr 2>/dev/null || ifconfig 2>/dev/null | head -n 30",
    "docker": "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}' 2>&1 | head -n 25",
    "failed": "systemctl --failed --no-legend --plain 2>&1 | head -n 20",
    "journal": "journalctl -p err -n 20 --no-pager 2>&1 | tail -n 20",
    "logins": "last -n 8 -a 2>/dev/null | head -n 10",
    "updates": (
        "if command -v apt >/dev/null 2>&1; then apt list --upgradable 2>/dev/null | tail -n +2 | head -n 25; "
        "elif command -v dnf >/dev/null 2>&1; then dnf -q check-update 2>/dev/null | head -n 25; "
        "else echo 'n/a'; fi"
    ),
}
TOOL_ORDER = list(TOOLS)
REBOOT_CMD = "(sleep 2; sudo -n reboot 2>/dev/null || reboot) >/dev/null 2>&1 &"

_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
MAX_OUTPUT = 3300


def clean_output(text: str, limit: int = MAX_OUTPUT) -> tuple[str, bool]:
    """Strip ANSI codes and cut to `limit` characters *after* HTML escaping. Returns (escaped, was_cut)."""
    text = _ANSI.sub("", text).replace("\r", "").rstrip()
    escaped = ui.esc(text)
    if len(escaped) <= limit:
        return escaped, False
    lines = text.split("\n")
    while len(lines) > 1 and len(ui.esc("\n".join(lines))) > limit:
        lines.pop()
    out = ui.esc("\n".join(lines))
    return out[:limit], True


# ------------------------------------------------------------------ handlers
async def cb_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    lang, hid = ui.lang_of(context), int(q.data.split(":")[2])
    from database.db import db   # local import keeps module import order simple

    host = await db.get_host(hid, update.effective_user.id)
    if not host:
        await ui.show(update, context, t("host_missing", lang), K.back_kb(lang, "menu:hosts"))
        return
    await ui.show(update, context, t("tb_menu", lang, label=host["label"]), K.toolbox_kb(lang, hid, TOOL_ORDER))


async def cb_run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """h:tr:<host id>:<tool key>"""
    q = update.callback_query
    _, _, hid, key = q.data.split(":")
    if key not in TOOLS:
        await q.answer()
        return
    await terminal.start_action(update, context, int(hid), f"tool_{key}")


async def cb_reboot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    lang, hid = ui.lang_of(context), int(q.data.split(":")[2])
    if q.data.startswith("h:rbyes:"):
        await terminal.start_action(update, context, hid, "reboot")
        return
    await q.answer()
    await ui.show(
        update, context, t("tb_reboot_confirm", lang),
        K.danger_confirm_kb(lang, f"h:rbyes:{hid}", f"h:tb:{hid}", t("b_reboot_yes", lang)),
    )


# ------------------------------------------------------------------ actions (registered in main.post_init)
def make_runner(key: str):
    async def runner(bot, chat_id: int, mid: int, uid: int, lang: str, host: dict, conn) -> None:
        try:
            try:
                status, out = await run_command(conn, "sh -c " + shlex.quote(TOOLS[key]), timeout=25)
                body, cut = clean_output(out)
                if not body.strip():
                    body = t("tb_no_output", lang)
            except asyncio.TimeoutError:
                body, cut = t("tb_timeout", lang), False
        finally:
            await registry._close_conn(conn)
        if cut:
            body += "\n…"
        kb = K.kb([
            [K.btn(t("b_refresh", lang), f"h:tr:{host['id']}:{key}", K.PRIMARY)],
            [K.btn(t("b_back", lang), f"h:tb:{host['id']}")],
        ])
        await ui.edit(bot, chat_id, mid, t("tb_result", lang, title=t("tb_" + key, lang), label=host["label"], body=Raw(f"<pre>{body}</pre>")), kb)

    return runner


async def launch_reboot(bot, chat_id: int, mid: int, uid: int, lang: str, host: dict, conn) -> None:
    try:
        await asyncio.wait_for(conn.run("sh -c " + shlex.quote(REBOOT_CMD), check=False), 10)
    except asyncio.TimeoutError:
        pass
    finally:
        await registry._close_conn(conn)
    await ui.edit(bot, chat_id, mid, t("tb_rebooting", lang, label=host["label"]), K.back_kb(lang, f"h:view:{host['id']}"))
