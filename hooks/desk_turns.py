"""UserPromptSubmit, Stop and PreToolUse (Bash, PowerShell) hook: a Claude desktop session in the assistant's folder that
joined Talk to your assistant (/assistant:talk) shares the box's conversation, and when it runs desk.py act, the hook
notes which session it is, so only that session's own words count as the owner's authority. The work is the home's own
System/live/desk.py, run hidden with the hook's JSON; this file only finds the home and hands it over. A session anywhere
else, one that never joined, or a home laid down before desk.py existed gets nothing; this hook never blocks."""
import json
import os
import re
import subprocess
import sys

MARK = "# This folder is your assistant (written by the assistant plugin"
STEP = re.compile(r"desk\.py[\"']?\s+(join|leave|act)\b")      # join, leave, or act (its words: this session's own)


def home_engine(cwd):
    """The home's System/live folder when cwd is an assistant home that has desk.py, else ''."""
    live = os.path.join(cwd, "System", "live")
    try:
        with open(os.path.join(cwd, "CLAUDE.md"), encoding="utf-8") as f:
            ours = f.read(len(MARK)) == MARK
    except OSError:
        return ""
    return live if ours and os.path.isfile(os.path.join(live, "desk.py")) else ""


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw or "{}")
    except ValueError:
        return
    live = home_engine(str(data.get("cwd") or ""))
    if not live or data.get("agent_id") or data.get("agent_type"):
        return
    event = data.get("hook_event_name")
    if event == "UserPromptSubmit":
        step = "heard"
    elif event == "Stop":
        step = "said"
    elif event == "PreToolUse":
        cmd = str((data.get("tool_input") or {}).get("command") or "").strip()
        m = STEP.search(cmd)
        if not m:
            return
        step = m.group(1) + "-hook"
    else:
        return
    try:
        r = subprocess.run([sys.executable, os.path.join(live, "desk.py"), step], input=raw, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", cwd=live, timeout=100,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired):
        return
    if step in ("heard", "said") and r.stdout.strip():      # the box's talk as context, or a reply sent back to finish what it promised
        sys.stdout.write(r.stdout)


if __name__ == "__main__":
    main()
