"""Minimal one-shot Feishu custom-bot webhook sender."""

from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx


@dataclass(frozen=True)
class SendReceipt:
    http_status: int
    provider_code: int


class FeishuSendError(Exception):
    def __init__(self, code: str, http_status: int | None = None):
        self.code = code
        self.http_status = http_status
        super().__init__(code)


class FeishuWebhookSender:
    def __init__(self, webhook_url: str):
        try:
            parsed = urlsplit(webhook_url)
            valid = (parsed.scheme == "https" and parsed.hostname == "open.feishu.cn" and
                     parsed.port in (None, 443) and
                     parsed.path.startswith("/open-apis/bot/v2/hook/") and
                     bool(parsed.path.removeprefix("/open-apis/bot/v2/hook/")) and
                     not parsed.username and not parsed.password and
                     not parsed.query and not parsed.fragment)
        except ValueError:
            valid = False
        if not valid:
            raise FeishuSendError("INVALID_WEBHOOK_CONFIG")
        self._webhook_url = webhook_url

    def send(self, payload: dict) -> SendReceipt:
        try:
            response = httpx.post(self._webhook_url, json=payload, timeout=10.0,
                                  follow_redirects=False)
        except httpx.RequestError:
            # httpx exceptions may contain the secret-bearing URL: never propagate them.
            raise FeishuSendError("NETWORK_ERROR") from None
        if response.status_code != 200:
            raise FeishuSendError("HTTP_ERROR", response.status_code)
        try:
            body = response.json()
        except ValueError:
            raise FeishuSendError("INVALID_RESPONSE", response.status_code) from None
        if not isinstance(body, dict):
            raise FeishuSendError("INVALID_RESPONSE", response.status_code)
        code = body.get("code", body.get("StatusCode"))
        if type(code) is not int:
            raise FeishuSendError("INVALID_RESPONSE", response.status_code)
        if code != 0:
            raise FeishuSendError(f"FEISHU_{code}", response.status_code)
        return SendReceipt(response.status_code, code)
