r"""The page's Refresh button: read every mailbox now, in its own hidden run.

    python mailpull.py

Started by mail.pull_now() (the Refresh press). It waits its turn behind a pass (the same lock the pass and the card rebuild
take), reads every email mailbox the way a pass does (new mail first, then the changes made elsewhere and the folders), and
says how it went in state\mail_pull.json, which the page asks for. Nothing here runs on its own.
"""
import os
import subprocess
import sys
import time

import common
import gather

STATE = os.path.join(common.HOME, "state", "mail_pull.json")
READ = os.path.join(common.paths.CONNECTIONS, "run.py")
WAIT = 15 * 60
SYNC_SECONDS = 120              # asked for by the owner's press: more time for the slow work than a pass gives it


def main():
    import onboard
    if onboard.holding():       # no new mail before the setup's history catalog is built (mail.pull_now says so too)
        common.write_json(STATE, {"running": None, "done_at": (common.read_json(STATE, {}) or {}).get("done_at"),
                                  "said": "new mail waits until your history catalog is built"})
        return 0
    end = time.time() + WAIT
    while not gather.take_lock():
        if time.time() > end:
            common.write_json(STATE, {"running": None, "done_at": (common.read_json(STATE, {}) or {}).get("done_at"), "said": "a check held the lock too long"})
            return 1
        time.sleep(5)
    said = ""
    try:
        pid = "pull-" + common.now().strftime("%Y%m%d-%H%M%S")
        r = subprocess.run([sys.executable, READ, "--kind", "email", "--run-id", pid, "--limit", "400", "--sync-seconds", str(SYNC_SECONDS)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        said = "ok" if r.returncode == 0 else f"exit {r.returncode}: {(r.stderr or r.stdout)[-300:]}"
    except (subprocess.SubprocessError, OSError) as e:
        said = f"{type(e).__name__}"
    finally:
        gather.drop_lock()
        common.write_json(STATE, {"running": None, "done_at": common.now().isoformat(timespec="seconds"), "said": said})
    return 0


if __name__ == "__main__":
    sys.exit(main())
