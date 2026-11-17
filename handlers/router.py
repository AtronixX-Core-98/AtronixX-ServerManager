"""router.py - routes free-form messages (text / file / photo) to the active flow or the live terminal"""

from __future__ import annotations

import logging
import time

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from config import settings
from handlers import admin, hosts, sftp, terminal, tools, ui
from locales.strings import t

logger = logging.getLogger("servermanager.router")
_last_admin_alert = 0.0


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # 1) active flows (server wizard, saved command, new folder, admin)  2) live terminal  3) show the menu
    for handler in (hosts.flow_text, tools.flow_text, sftp.flow_text, admin.flow_text):
        if await handler(update, context):
            return
    if await terminal.handle_text(update, context):
        return
    await ui.show_main(update, context)


async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await hosts.flow_media(update, context):
        return
    if await admin.flow_media(update, context):
        return
    if await sftp.on_upload(update, context):
        return
    await ui.send(context.bot, update.effective_chat.id, t("unexpected_file", ui.lang_of(context)))


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await admin.flow_media(update, context):
        return
    await ui.send(context.bot, update.effective_chat.id, t("unexpected_file", ui.lang_of(context)))


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _last_admin_alert
    err = context.error
    logger.error("Unhandled error: %s", type(err).__name__, exc_info=err)
    if isinstance(update, Update) and update.callback_query:
        try:
            await update.callback_query.answer()
        except TelegramError:
            pass
    if time.time() - _last_admin_alert > 600:   # at most one alert to the admin every 10 minutes
        _last_admin_alert = time.time()
        await ui.send(context.bot, settings.admin_id, f"⚠️ <b>{ui.esc(settings.brand)}</b>\n<code>{ui.esc(type(err).__name__)}: {ui.esc(str(err)[:200])}</code>")
