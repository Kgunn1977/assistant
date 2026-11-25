"""What a test made in a scratch folder goes when it ends, all of it: any program still running from that folder (a page
server, a pass) is stopped first, since on Windows a folder a running program has open cannot be removed, then the folder is
removed, tried again for a few seconds. Used by every test that starts a program there or copies anything large."""
import json
import os
import shutil
import stat
import subprocess
import time


def _writable_again(fn, path, _exc):
    try:
        os.chmod(path, stat.S_IWRITE)
        fn(path)
    except OSError:
        pass


def _stop_programs_in(path):
    if os.name != "nt":
        return
    ps = ("Get-CimInstance Win32_Process | Select-Object ProcessId, CommandLine | ConvertTo-Json -Compress")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True, text=True,
                           timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        rows = json.loads(r.stdout or "[]")
    except (OSError, ValueError, subprocess.SubprocessError):
        return
    want = os.path.normcase(os.path.abspath(path))
    for row in rows if isinstance(rows, list) else [rows]:
        cmd = os.path.normcase(str((row or {}).get("CommandLine") or "")).replace("/", "\\")
        pid = (row or {}).get("ProcessId")
        if pid and pid != os.getpid() and want in cmd:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def remove(path, wait=15):
    """True when the folder is gone."""
    if not path or not os.path.exists(path):
        return True
    _stop_programs_in(path)
    end = time.time() + wait
    while True:
        shutil.rmtree(path, onerror=_writable_again)
        if not os.path.exists(path):
            return True
        if time.time() >= end:
            print(f"NOTE the scratch folder could not be removed: {path}")
            return False
        time.sleep(1)
