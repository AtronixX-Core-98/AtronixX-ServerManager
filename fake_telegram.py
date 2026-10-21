"""A fake Telegram Bot API: records every call and returns plausible results, so real handlers can be
driven end to end without a network. It also validates that every HTML message is well formed."""

from __future__ import annotations

import json
from html.parser import HTMLParser

from telegram import Update
from telegram.request import BaseRequest

ALLOWED_TAGS = {"b", "i", "u", "s", "code", "pre", "a", "em", "strong", "tg-spoiler", "blockquote"}


class _Balance(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in ALLOWED_TAGS:
            self.errors.append(f"tag <{tag}> not supported by Telegram")
        self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"unbalanced </{tag}> (open: {self.stack})")
        else:
            self.stack.pop()


def check_html(text: str) -> list[str]:
    p = _Balance()
    p.feed(text)
    p.close()
    return p.errors + ([f"unclosed tags {p.stack}"] if p.stack else [])


class FakeRequest(BaseRequest):
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self._mid = 1000

    @property
    def read_timeout(self):
        return 5

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    def _msg(self, params: dict, text: str | None = None) -> dict:
        self._mid += 1
        chat_id = int(params.get("chat_id", 0) or 0)
        return {"message_id": int(params.get("message_id") or self._mid), "date": 1,
                "chat": {"id": chat_id, "type": "private"}, "text": text or params.get("text") or "x"}

    async def do_request(self, url, method, request_data=None, read_timeout=None, write_timeout=None,
                         connect_timeout=None, pool_timeout=None):
        api = url.rsplit("/", 1)[-1]
        params = dict(request_data.parameters) if request_data else {}
        if "reply_markup" in params and isinstance(params["reply_markup"], str):
            params["reply_markup"] = json.loads(params["reply_markup"])
        self.calls.append((api, params))
        if params.get("parse_mode") == "HTML":
            text = params.get("text") or params.get("caption") or ""
            errors = check_html(text)
            assert not errors, f"{api}: malformed HTML {errors}\n{text}"
            assert len(text) <= 4096, f"{api}: message too long ({len(text)})"
        if api == "getMe":
            result = {"id": 999, "is_bot": True, "first_name": "bot", "username": "test_bot"}
        elif api in ("sendMessage", "editMessageText", "sendDocument", "editMessageReplyMarkup", "sendPhoto"):
            result = self._msg(params)
        elif api == "getFile":
            result = {"file_id": "f", "file_unique_id": "u", "file_size": 1, "file_path": "x"}
        elif api == "getChatMember":
            result = {"status": "member", "user": {"id": 1, "is_bot": False, "first_name": "x"}}
        else:
            result = True
        return 200, json.dumps({"ok": True, "result": result}).encode()

    # ---- helpers for assertions
    def sent(self, *apis: str) -> list[dict]:
        apis = apis or ("sendMessage", "editMessageText")
        return [p for a, p in self.calls if a in apis]

    def last_text(self) -> str:
        sent = self.sent()
        return sent[-1].get("text", "") if sent else ""

    def texts(self) -> str:
        return "\n".join(p.get("text", "") for p in self.sent())

    def buttons(self, call: dict | None = None) -> list[dict]:
        if call is None:
            sent = self.sent()
            if not sent:
                return []
            call = sent[-1]
        return [b for row in call.get("reply_markup", {}).get("inline_keyboard", []) for b in row]

    def callbacks(self, call: dict | None = None) -> list[str]:
        return [b["callback_data"] for b in self.buttons(call) if "callback_data" in b]

    def api_called(self, api: str) -> bool:
        return any(a == api for a, _ in self.calls)

    def clear(self) -> None:
        self.calls.clear()


_uid = [0]


def _user(uid: int, name: str = "User") -> dict:
    return {"id": uid, "is_bot": False, "first_name": name, "username": f"u{uid}", "language_code": "en"}


def message_update(bot, uid: int, text: str, mid: int = 5000) -> Update:
    _uid[0] += 1
    data = {"update_id": _uid[0], "message": {
        "message_id": mid + _uid[0], "date": 1, "chat": {"id": uid, "type": "private", "first_name": "U"},
        "from": _user(uid), "text": text}}
    if text.startswith("/"):
        data["message"]["entities"] = [{"type": "bot_command", "offset": 0, "length": len(text.split()[0])}]
    return Update.de_json(data, bot)


def callback_update(bot, uid: int, data: str, mid: int = 777) -> Update:
    _uid[0] += 1
    return Update.de_json({"update_id": _uid[0], "callback_query": {
        "id": str(_uid[0]), "from": _user(uid), "chat_instance": "ci", "data": data,
        "message": {"message_id": mid, "date": 1, "chat": {"id": uid, "type": "private"}, "text": "x"}}}, bot)
