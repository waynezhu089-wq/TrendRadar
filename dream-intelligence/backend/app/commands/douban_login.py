"""User-controlled login in ordinary Chrome, isolated from daily browser data."""

import os
import shutil
import subprocess
from pathlib import Path

from app.research.douban import PROFILE_DIR, profile_lock


def open_login():
    chrome = shutil.which('chrome')
    if not chrome:
        for root in (os.environ.get('ProgramFiles'), os.environ.get('LOCALAPPDATA')):
            if root:
                candidate = Path(root) / 'Google/Chrome/Application/chrome.exe'
                if candidate.is_file():
                    chrome = str(candidate)
                    break
    if not chrome:
        raise RuntimeError('Chrome unavailable')
    with profile_lock(PROFILE_DIR):
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.Popen([chrome, f'--user-data-dir={PROFILE_DIR}', '--profile-directory=Default',
            '--no-first-run', '--new-window', 'https://accounts.douban.com/passport/login'], close_fds=True)


if __name__ == '__main__':
    open_login()
    print('请在 DSIH 专用 Chrome 窗口亲自登录豆瓣，完成后关闭该窗口。无需提供密码或 Cookie。')
