"""main.py - application entry point"""

from __future__ import annotations

import asyncio
import logging

from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    BaseUpdateProcessor,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    TypeHandler,
    filters,
)

from config import settings
from version import VERSION
from core import housekeeping, registry
from core.crypto import vault
from database.db import db
from handlers import admin, gate, hosts, router, sftp, start, terminal, toolbox, tools, ui
from locales.strings import t

logger = logging.getLogger("servermanager")


class OrderedProcessor(BaseUpdateProcessor):
    """Updates from different users run concurrently, but the updates of one chat are processed in
    order (the order of commands typed into the terminal matters)."""

    def __init__(self, max_concurrent: int = 32):
        super().__init__(max_concurrent)
        self._locks: dict[int, asyncio.Lock] = {}
        self._refs: dict[int, int] = {}

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    async def do_process_update(self, update, coroutine) -> None:
        chat = getattr(update, "effective_chat", None)
        key = chat.id if chat else 0
        lock = self._locks.setdefault(key, asyncio.Lock())
        self._refs[key] = self._refs.get(key, 0) + 1
        try:
            async with lock:
                await coroutine
        finally:
            self._refs[key] -= 1
            if self._refs[key] <= 0:
                self._refs.pop(key, None)
                self._locks.pop(key, None)


def register(app: Application) -> None:
    private = filters.ChatType.PRIVATE
    app.add_handler(TypeHandler(Update, gate.pre_check), group=-1)

    for name, fn in (("start", start.cmd_start), ("menu", start.cmd_start), ("help", start.cmd_help), ("cancel", start.cmd_cancel), ("id", start.cmd_id)):
        app.add_handler(CommandHandler(name, fn, filters=private))

    def cb(fn, pattern: str) -> None:
        app.add_handler(CallbackQueryHandler(fn, pattern=pattern))

    # general
    cb(start.cb_menu_home, r"^menu:home$")
    cb(start.cb_noop, r"^noop$")
    cb(start.cb_lang, r"^lang:toggle$")
    cb(start.cb_terms, r"^terms:accept$")
    cb(start.cb_join_check, r"^join:check$")
    cb(start.cb_account, r"^me:home$")
    cb(start.cb_account_delete, r"^me:del$")
    cb(start.cb_account_delete_yes, r"^me:delyes$")
    # servers
    cb(hosts.cb_list, r"^(menu:hosts|hl:\d+:\d+)$")
    cb(hosts.cb_view, r"^h:view:\d+$")
    cb(hosts.cb_fav, r"^h:fav:\d+$")
    cb(hosts.cb_group_pick, r"^h:grp:\d+$")
    cb(hosts.cb_set_group, r"^h:setgrp:\d+:\d+$")
    cb(hosts.cb_test, r"^h:test:\d+$")
    cb(hosts.cb_watch, r"^h:watch:\d+$")
    cb(hosts.cb_delete, r"^h:del:\d+$")
    cb(hosts.cb_delete_yes, r"^h:delyes:\d+$")
    cb(hosts.cb_edit, r"^h:edit:\d+$")
    cb(hosts.cb_edit_field, r"^h:ef:\d+:\w+$")
    cb(hosts.cb_add, r"^hosts:add$")
    cb(hosts.cb_wizard, r"^wz:")
    # connect / terminal / SFTP
    cb(terminal.cb_connect, r"^h:(conn|connf|sftp|mon):\d+$")
    cb(terminal.cb_conn_cancel, r"^conn:cancel$")
    cb(terminal.cb_trust_yes, r"^trust:yes$")
    cb(terminal.cb_trust_no, r"^trust:no$")
    cb(terminal.cb_control_pad, r"^term:")
    cb(toolbox.cb_menu, r"^h:tb:\d+$")
    cb(toolbox.cb_run, r"^h:tr:\d+:\w+$")
    cb(toolbox.cb_reboot, r"^h:(rb|rbyes):\d+$")
    cb(sftp.cb_nav, r"^sf:")
    # tools
    cb(tools.cb_snip_list, r"^snip:list$")
    cb(tools.cb_snip_view, r"^snip:view:\d+$")
    cb(tools.cb_snip_del, r"^snip:del(yes)?:\d+$")
    cb(tools.cb_snip_add, r"^snip:add$")
    cb(tools.cb_snip_run, r"^snip:run:\d+$")
    cb(tools.cb_snip_close, r"^snip:close$")
    cb(tools.cb_grp_list, r"^grp:list$")
    cb(tools.cb_grp_view, r"^grp:view:\d+$")
    cb(tools.cb_grp_del, r"^grp:del(yes)?:\d+$")
    cb(tools.cb_grp_add, r"^grp:add$")
    # admin
    cb(admin.cb_home, r"^adm:home$")
    cb(admin.cb_stats, r"^adm:st$")
    cb(admin.cb_users, r"^adm:users:(all|sub|exp|banned):\d+$")
    cb(admin.cb_user, r"^adm:u:\d+$")
    cb(admin.cb_ban, r"^adm:(ban|unban):\d+$")
    cb(admin.cb_revoke, r"^adm:revoke(yes)?:\d+$")
    cb(admin.cb_delete_user, r"^adm:del(yes)?:\d+$")
    cb(admin.cb_grant_new, r"^adm:grantnew$")
    cb(admin.cb_grant, r"^adm:grant:\d+$")
    cb(admin.cb_find, r"^adm:find$")
    cb(admin.cb_message_user, r"^adm:msg:\d+$")
    cb(admin.cb_mode, r"^(adm:mode|adm:modeyes:(free|paid))$")
    cb(admin.cb_broadcast, r"^(adm:bc|adm:bcaud:(all|subs))$")
    cb(admin.cb_bc_go, r"^af:bcgo$")
    cb(admin.cb_channels, r"^(adm:ch|adm:chdel:\d+)$")
    cb(admin.cb_channel_add, r"^adm:chadd$")
    cb(admin.cb_backup, r"^(adm:bk|adm:bknow)$")
    cb(admin.cb_restore, r"^adm:rs$")
    cb(admin.cb_restore_go, r"^af:rsgo$")
    cb(admin.cb_sessions, r"^(adm:ss|adm:kill:\d+)$")
    cb(admin.cb_settings, r"^(adm:set|adm:live:-?\d+)$")
    cb(admin.cb_log, r"^adm:log$")
    # free-form messages
    app.add_handler(MessageHandler(private & filters.TEXT & ~filters.COMMAND, router.on_text))
    app.add_handler(MessageHandler(private & filters.Document.ALL, router.on_document))
    app.add_handler(MessageHandler(private & filters.PHOTO, router.on_photo))
    app.add_error_handler(router.on_error)


def register_actions() -> None:
    """Actions that run after a connection is established and its host key verified."""
    registry.actions.update(terminal=terminal.launch_terminal, sftp=sftp.launch_sftp, monitor=tools.launch_monitor,
                            reboot=toolbox.launch_reboot)
    for key in toolbox.TOOLS:
        registry.actions[f"tool_{key}"] = toolbox.make_runner(key)


async def post_init(app: Application) -> None:
    await db.open()
    register_actions()
    en = [BotCommand("start", "Main menu"), BotCommand("cancel", "Cancel the current operation"), BotCommand("id", "Show my numeric ID"), BotCommand("help", "Help")]
    fa = [BotCommand("start", "منوی اصلی"), BotCommand("cancel", "لغو عملیات فعلی"), BotCommand("id", "نمایش آیدی عددی من"), BotCommand("help", "راهنما")]
    await app.bot.set_my_commands(en)
    await app.bot.set_my_commands(fa, language_code="fa")
    housekeeping.start(app.bot)
    me = await app.bot.get_me()
    logger.info("%s v%s started as @%s", settings.brand, VERSION, me.username)
    lang = await db.admin_language()
    mode = await db.get_mode()
    notice = t("boot_notice", lang, version=VERSION, mode=t("mode_paid" if mode == "paid" else "mode_free", lang))
    if settings.host_access:
        notice += "\n" + t("boot_host_access", lang)
    await ui.send(app.bot, settings.admin_id, notice)


async def post_shutdown(app: Application) -> None:
    await housekeeping.stop()
    await registry.close_all()
    await db.close()


def main() -> None:
    logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
    # httpx logs request URLs (which contain the bot token) at INFO level; silence it
    for noisy in ("httpx", "httpcore", "telegram.ext.Application"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    vault.load()
    app = (
        Application.builder()
        .token(settings.bot_token)
        .concurrent_updates(OrderedProcessor(32))
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    register(app)
    app.run_polling(allowed_updates=["message", "callback_query"], drop_pending_updates=False)


if __name__ == "__main__":
    main()
