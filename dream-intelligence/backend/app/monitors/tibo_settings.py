"""Non-secret subscription preferences shared by the API and resident Scheduler."""
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock

from app.db.database import DATA_DIR
from .tibo_sources import ACCOUNT

CONFIG_PATH = DATA_DIR / 'tibo-monitor.json'
RUNTIME_PATH = DATA_DIR / 'tibo-monitor-runtime.json'
POLL_MINUTES = 120
INTERVAL_OPTIONS = (30, 60, 120, 240, 720, 1440)
_write_lock = Lock()


@dataclass(frozen=True)
class TiboConfig:
    enabled: bool = True
    browser_enabled: bool = False
    poll_minutes: int = POLL_MINUTES


def read_config(path=None):
    values = json.loads((path or CONFIG_PATH).read_text(encoding='utf-8-sig'))
    if not isinstance(values, dict) or values.get('account') != ACCOUNT:
        raise ValueError('Invalid subscription')
    minutes = values.get('poll_minutes', POLL_MINUTES)
    # Keep the former five-minute value readable until the user saves a new interval.
    if type(minutes) is not int or minutes not in (5, *INTERVAL_OPTIONS):
        raise ValueError('Invalid interval')
    return values


def load_tibo_config(path=None):
    try:
        values = read_config(path)
        if values.get('enabled') is not True:
            return None
        return TiboConfig(browser_enabled=values.get('browser_enabled') is True,
                          poll_minutes=values.get('poll_minutes', POLL_MINUTES))
    except (OSError, ValueError, TypeError):
        return None


def atomic_json(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                prefix=path.name + '.', suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(values, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def save_poll_minutes(minutes, path=None):
    if type(minutes) is not int or minutes not in INTERVAL_OPTIONS:
        raise ValueError('Invalid interval')
    with _write_lock:
        target = path or CONFIG_PATH
        values = read_config(target)
        if values.get('enabled') is not True:
            raise ValueError('Subscription disabled')
        atomic_json(target, {**values, 'poll_minutes': minutes})


def settings_status(now=None, config_path=None, runtime_path=None):
    now = now or datetime.now(timezone.utc)
    config = load_tibo_config(config_path)
    result = {'enabled': bool(config), 'poll_minutes': config.poll_minutes if config else POLL_MINUTES,
              'interval_options': list(INTERVAL_OPTIONS), 'applied_poll_minutes': None,
              'next_run_time': None, 'scheduler_connected': False, 'pending': bool(config)}
    try:
        runtime = json.loads((runtime_path or RUNTIME_PATH).read_text(encoding='utf-8'))
        updated = datetime.fromisoformat(runtime['updated_at'])
        if updated.tzinfo and timedelta(0) <= now - updated <= timedelta(seconds=90):
            result.update(applied_poll_minutes=runtime['poll_minutes'],
                          next_run_time=runtime['next_run_time'], scheduler_connected=True,
                          pending=bool(config and runtime['poll_minutes'] != config.poll_minutes))
    except (OSError, ValueError, TypeError, KeyError):
        pass
    return result
