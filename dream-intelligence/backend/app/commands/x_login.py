"""Open only DSIH's X profile for the owner to sign in personally."""
import subprocess
from pathlib import Path
import os
from app.monitors.tibo_sources import PROFILE_DIR


def open_login():
    chrome=next((Path(root)/'Google/Chrome/Application/chrome.exe'
        for root in [os.environ.get('ProgramFiles',''),os.environ.get('LOCALAPPDATA','')]
        if root and (Path(root)/'Google/Chrome/Application/chrome.exe').is_file()),None)
    if chrome is None:raise RuntimeError('Chrome unavailable')
    PROFILE_DIR.mkdir(parents=True,exist_ok=True)
    subprocess.Popen([str(chrome),f'--user-data-dir={PROFILE_DIR}','--profile-directory=Default',
        '--no-first-run','--new-window','https://x.com/i/flow/login'],close_fds=True)


if __name__=='__main__':
    open_login()
    print('请在专用 Chrome 中登录 X，完成后关闭该窗口；无需提供密码或 Cookie。')
