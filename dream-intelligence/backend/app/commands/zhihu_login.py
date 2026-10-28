"""Open a normal Edge window with DSIH's dedicated Zhihu profile for manual login."""

import os
import shutil
import subprocess
from pathlib import Path

from app.research.zhihu import PROFILE_DIR, ZHIHU_HOME


def edge_path() -> str:
    installed = shutil.which("msedge")
    if installed:
        return installed
    for root in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
        if root:
            candidate = Path(root) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            if candidate.is_file():
                return str(candidate)
    raise RuntimeError("Microsoft Edge is required for Zhihu browser collection")


def main() -> None:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    print("Opening a normal Edge window with the DSIH-only Zhihu profile.")
    print("Sign in yourself, then close that Edge window before running a plan.")
    print("No username, password, or browser cookies are printed or exported.")
    subprocess.Popen([edge_path(), f"--user-data-dir={PROFILE_DIR}",
                      "--no-first-run", ZHIHU_HOME], close_fds=True)


if __name__ == "__main__":
    main()
