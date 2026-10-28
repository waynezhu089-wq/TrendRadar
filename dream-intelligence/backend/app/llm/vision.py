"""Separate, explicitly configured Qwen vision endpoint. Secrets stay in the environment."""
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from app.db.database import DATA_DIR
from .openai_compatible import LLMSettings, OpenAICompatibleClient, ConfigurationError

CONFIG_PATH = DATA_DIR / 'vision-provider.json'


def vision_settings(path: Path | None = None):
    try:
        target = path or CONFIG_PATH
        config = json.loads(target.read_text(encoding='utf-8-sig')) if target.exists() else {}
        base = os.environ.get('DSIH_VISION_BASE_URL') or config.get('base_url', '')
        model = os.environ.get('DSIH_VISION_MODEL') or config.get('model', '')
        key_env = os.environ.get('DSIH_VISION_API_KEY_ENV') or config.get('api_key_env', 'DSIH_VISION_API_KEY')
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{1,100}', key_env):
            raise ValueError()
        key = os.environ.get(key_env, '').strip()
        url = urlsplit(base)
        timeout = float(os.environ.get('DSIH_VISION_TIMEOUT', '90'))
        if (not base or not model or not key or url.scheme not in ('http','https') or not url.hostname
                or url.username or url.password or url.query or url.fragment or not 0 < timeout <= 180):
            raise ValueError()
        return LLMSettings(base.rstrip('/'), key, model, timeout)
    except (OSError, ValueError, TypeError, AttributeError):
        raise ConfigurationError('VISION_NOT_CONFIGURED') from None


def vision_status():
    try:
        settings = vision_settings()
        return {'configured':True, 'model':settings.model, 'base_url':settings.base_url}
    except ConfigurationError:
        return {'configured':False, 'model':None, 'base_url':None}


class QwenVisionClient(OpenAICompatibleClient):
    def analyze(self, messages):
        # Non-thinking JSON mode is supported by the configured Qwen vision interface.
        return self._complete(messages, {'enable_thinking':False, 'max_tokens':12000})
