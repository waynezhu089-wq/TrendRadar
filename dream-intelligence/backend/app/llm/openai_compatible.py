import json
import math
import os
from dataclasses import dataclass, field
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from .base import LLMError

class ConfigurationError(Exception):
    pass

@dataclass(frozen=True)
class LLMSettings:
    base_url: str = field(repr=False)
    api_key: str = field(repr=False)
    model: str
    timeout: float = 30

    @classmethod
    def from_env(cls):
        names = ("DSIH_LLM_BASE_URL", "DSIH_LLM_API_KEY", "DSIH_LLM_MODEL")
        values = [os.environ.get(name, "").strip() for name in names]
        if not all(values):
            raise ConfigurationError("REAL_LLM_NOT_VALIDATED: configure DSIH_LLM_BASE_URL, DSIH_LLM_API_KEY and DSIH_LLM_MODEL")
        try:
            timeout = float(os.environ.get("DSIH_LLM_TIMEOUT", "30") or "30")
            parts = urlsplit(values[0])
            valid_url = parts.scheme in ("http", "https") and parts.hostname and not (parts.username or parts.password or parts.query or parts.fragment)
        except ValueError:
            raise ConfigurationError("Invalid LLM URL or timeout configuration") from None
        if not valid_url or not math.isfinite(timeout) or not 0 < timeout <= 300:
            raise ConfigurationError("Invalid LLM URL or timeout configuration")
        return cls(*values, timeout)

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Do not forward Authorization to a redirect destination.

class OpenAICompatibleClient:
    def __init__(self, settings: LLMSettings):
        self.settings = settings
        self.opener = build_opener(NoRedirect())
        self.last_usage = None

    def analyze(self, messages: list[dict[str, str]]) -> str:
        return self._complete(messages)

    def _complete(self, messages, options=None) -> str:
        self.last_usage = None
        payload = {"model": self.settings.model, "messages": messages,
                   "response_format": {"type": "json_object"}, **(options or {})}
        request = Request(self.settings.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json",
                     "Authorization": "Bearer " + self.settings.api_key})
        try:
            with self.opener.open(request, timeout=self.settings.timeout) as response:
                data = json.load(response)
            usage = data.get('usage', {})
            self.last_usage = {key: value for key, value in usage.items()
                               if key in ('prompt_tokens', 'completion_tokens', 'total_tokens')
                               and type(value) is int and value >= 0} if isinstance(usage, dict) else None
            choice = data["choices"][0]
            content = choice["message"]["content"]
            if choice.get("finish_reason") not in (None, "stop") or not isinstance(content, str) or not content.strip():
                raise LLMError("Provider returned incomplete content")
            return content
        except HTTPError as error:
            raise LLMError(f"Provider HTTP {error.code}") from None
        except LLMError:
            raise
        except Exception:
            raise LLMError("Provider request or response failed") from None
