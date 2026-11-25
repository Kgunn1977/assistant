r"""What is already on this computer, before the assistant is set up: the setup interview's audit stage.

Read only. It looks for what could clash with the assistant: skills and plugins doing the same jobs, scheduled
jobs and other things running on their own, ready-made and other connections already set up, project folders
whose Claude checks commands (and may refuse the assistant's), instructions files that describe things no
longer on the computer, something else on the page's spot, what Tailscale already shares, and older copies of
an assistant or its data. Each finding is said in plain words: what it is, how it is used, what would clash.

Nothing is changed here. A decision (keep, change, remove) is recorded by setup_home.py, which acts only on
the person's yes; removing deletes outright (a scheduled job is deleted from Windows' scheduled jobs).
"""
import json
import os
import re
import socket
import subprocess

NO_WINDOW = 0x08000000
JOB_WORDS = {"assistant", "briefing", "brief", "inbox", "email", "mail", "morning", "roadmap", "triage", "calendar", "texts", "sms"}
RUNS_CODE = re.compile(r"python|pythonw|claude|powershell|\.ps1\b|\.py\b|\.pyw\b|node\.exe|\.bat\b|\.cmd\b", re.I)
WIN_PATH = re.compile(r"[A-Za-z]:\\[^\s`'\"<>|*?\r\n]+")
REL_PATH = re.compile(r"(?<![\w:/\\])(?:\.\.?[\\/])?(?:[\w.-]+[\\/])+[\w.-]+\.(?:md|py|pyw|ps1|json|txt|bat|cmd)\b")
SKIP_DIRS = {"node_modules", ".git", "__pycache__", "AppData", "To Delete", "site-packages", ".venv", "venv"}
NEVER_JOB = ("\\Microsoft\\",)


def _read(path, limit=200_000):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read(limit)
    except OSError:
        return ""


def _json(path):
    try:
        return json.loads(_read(path) or "null")
    except ValueError:
        return None


def _front(text):
    """name and description from a skill's opening block."""
    out = {}
    if text.startswith("---"):
        for line in text.split("---", 2)[1].splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                out[k.strip()] = v.strip()
    return out


def _words(text):
    return {w for w in re.findall(r"[a-z]+", str(text).lower())} & JOB_WORDS


class Ctx:
    """Where to look. Every place can be pointed elsewhere for a test."""

    def __init__(self, root, home, own_jobs=(), port=47815, claude_dir=None, project_roots=None, own_plugin="assistant@assistant"):
        self.root, self.home, self.own_jobs, self.port, self.own_plugin = root, home, tuple(own_jobs), int(port), own_plugin
        self.claude_dir = claude_dir or os.path.join(os.path.expanduser("~"), ".claude")
        self.project_roots = project_roots or [os.path.join(os.path.expanduser("~"), "Documents")]


# --- each place looked at -------------------------------------------------------------------------------
def skills(ctx):
    out = []
    folders = [os.path.join(ctx.claude_dir, "skills")]
    for base in folders:
        for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
            path = os.path.join(base, name, "SKILL.md")
            front = _front(_read(path, 4000))
            hits = _words(name + " " + front.get("description", ""))
            if hits:
                out.append({"kind": "skill", "where": os.path.join(base, name), "name": front.get("name") or name,
                            "what": f"A Claude skill called \"{front.get('name') or name}\", added to Claude on this computer.",
                            "used": front.get("description", "")[:200] or "No description.",
                            "clash": f"It does the same kind of work as your assistant ({', '.join(sorted(hits))}), so the two may both act on the same things.",
                            "choices": ["keep", "remove"]})
    return out


def plugins(ctx):
    got = _json(os.path.join(ctx.claude_dir, "plugins", "installed_plugins.json")) or {}
    out = []
    for key, installs in (got.get("plugins") or {}).items():
        if key == ctx.own_plugin:
            continue
        hits = _words(key.replace("@", " ").replace("-", " "))
        if hits:
            first = installs[0] if isinstance(installs, list) and installs else {}
            out.append({"kind": "plugin", "where": key, "name": key.split("@")[0],
                        "what": f"A Claude plugin called \"{key.split('@')[0]}\".",
                        "used": f"Turned on {'for one project' if first.get('scope') == 'local' else 'for all of Claude'}, version {first.get('version', '?')}.",
                        "clash": f"It may do the same kind of work as your assistant ({', '.join(sorted(hits))}). An older roadmap plugin would also give its roadmap reminders twice, beside the one in your assistant.",
                        "choices": ["keep", "remove"]})
    return out


def list_jobs():
    """Every scheduled job on this computer: [{name, action, state, next_run}] (read only)."""
    r = subprocess.run(["schtasks", "/Query", "/FO", "CSV", "/V"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    import csv
    rows = list(csv.reader((r.stdout or "").splitlines()))
    if not rows:
        return []
    head = rows[0]
    idx = {k: head.index(k) for k in ("TaskName", "Task To Run", "Status", "Next Run Time") if k in head}
    out = []
    for row in rows[1:]:
        if len(row) < len(head) or row[0] == head[0]:
            continue
        out.append({"name": row[idx["TaskName"]].lstrip("\\"), "action": row[idx.get("Task To Run", 0)],
                    "state": row[idx.get("Status", 0)], "next_run": row[idx.get("Next Run Time", 0)]})
    return out


def jobs(ctx, listed=None):
    out, seen = [], set()
    for j in (listed if listed is not None else list_jobs()):
        name = j["name"]
        if name in seen or name in ctx.own_jobs or any(n in "\\" + name for n in NEVER_JOB):
            continue
        seen.add(name)
        action = j.get("action") or ""
        if not (RUNS_CODE.search(action) or _words(name)):
            continue
        missing = [p for p in WIN_PATH.findall(action) if not os.path.exists(p.rstrip('".'))]
        clash = ("It points at something that is no longer on this computer, so it fails each time it starts."
                 if missing else "It starts on its own; if it reads the same accounts or writes to the same places as your assistant, the two get in each other's way.")
        out.append({"kind": "job", "where": name, "name": name,
                    "what": f"Something Windows starts by itself on a schedule, called \"{name}\".",
                    "used": f"It is {j.get('state', 'set').lower() or 'set'}; it next starts {j.get('next_run') or 'when nothing says'}.",
                    "clash": clash, "missing": missing[:5], "choices": ["keep", "remove"]})
    return out


def connections(ctx):
    got = _json(os.path.join(os.path.dirname(ctx.claude_dir), ".claude.json")) or {}
    names = sorted((got.get("mcpServers") or {}).keys())
    if not names:
        return []
    return [{"kind": "connections", "where": "Claude's own list", "name": "connections",
             "what": f"Connections Claude already has on this computer: {', '.join(names)}.",
             "used": "Claude uses them while you work with it.",
             "clash": "Nothing clashes; I mention them so we use what you already have when we connect accounts.",
             "choices": ["keep"]}]


def _project_dirs(ctx, depth=4):
    for top in ctx.project_roots:
        for here, dirs, files in os.walk(top):
            rel = os.path.relpath(here, top)
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and (rel == "." or rel.count(os.sep) < depth - 1)]
            if os.path.normcase(os.path.abspath(here)).startswith(os.path.normcase(os.path.abspath(ctx.root))):
                continue
            if "CLAUDE.md" in files or ".claude" in dirs:
                yield here


def _missing_paths(text, folder):
    """Places an instructions file names that are not on this computer. A relative name is tried from the file's
    folder and the two above it, and, because folder names can hold spaces, with up to three words before it."""
    found = []
    bases = (folder, os.path.dirname(folder), os.path.dirname(os.path.dirname(folder)))
    for raw in WIN_PATH.findall(text):
        p = raw.rstrip(".,;:)`'\"")
        if not any(c in p for c in "<*{") and not os.path.exists(p) and p not in found:
            found.append(p)
    rest = WIN_PATH.sub(" ", text)
    for m in REL_PATH.finditer(rest):
        p = m.group(0).strip().rstrip(".,;:)`'\"")
        if any(c in p for c in "<*{"):
            continue
        before = rest[:m.start()].split()[-3:]
        tries = [p] + [" ".join(before[i:] + [p]).strip("`'\"(") for i in range(len(before))]
        tries += [t.split(" ", 1)[1] for t in tries if " " in t]
        if not any(os.path.exists(os.path.join(b, t)) for b in bases for t in tries if t) and p not in found:
            found.append(p.split(" ")[-1] if not any(os.path.exists(os.path.join(b, p)) for b in bases) and " " in p else p)
    return found


def project_settings(folder):
    """The project's own Claude settings files, read only: [dict, ...]."""
    return [_json(os.path.join(folder, ".claude", s)) or {} for s in ("settings.json", "settings.local.json")]


def projects(ctx, settings=project_settings):
    out = []
    for folder in _project_dirs(ctx):
        name = os.path.basename(folder)
        guard = []
        for got in settings(folder):
            hooks = got.get("hooks") or {}
            if "PreToolUse" in hooks:
                guard.append("it looks at each thing Claude is about to do and can stop it")
            if (got.get("permissions") or {}).get("deny"):
                guard.append("it has a list of things Claude may not do")
        if guard:
            out.append({"kind": "guard", "where": folder, "name": name,
                        "what": f"The project \"{name}\" has its own rules for Claude: {' and '.join(dict.fromkeys(guard))}.",
                        "used": "They keep Claude inside that project while you work there.",
                        "clash": "If you introduce this project to your assistant, its rules may refuse the assistant's small changes there (a note folder, one line, the roadmap note).",
                        "choices": ["keep", "change"]})
        text = _read(os.path.join(folder, "CLAUDE.md"))
        gone = _missing_paths(text, folder) if text else []
        if gone:
            out.append({"kind": "stale", "where": os.path.join(folder, "CLAUDE.md"), "name": name,
                        "what": f"The instructions for Claude in the project \"{name}\" name things that are no longer on this computer.",
                        "used": "Claude reads these instructions every time you work in that project.",
                        "clash": "Claude may try to use what is gone, or follow an older way of working (for example an assistant you had before). Missing: " + "; ".join(gone[:5]),
                        "missing": gone[:10], "choices": ["keep", "change"]})
    return out


def port_user(port):
    """(busy, program name) for the page's spot on this computer."""
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
            return False, ""
        except OSError:
            pass
    r = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True, creationflags=NO_WINDOW)
    pid = next((ln.split()[-1] for ln in (r.stdout or "").splitlines() if f":{port} " in ln and "LISTEN" in ln.upper()), "")
    name = ""
    if pid:
        t = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], capture_output=True, text=True, creationflags=NO_WINDOW)
        name = (t.stdout or "").split(",")[0].strip('"') if t.stdout and "," in t.stdout else ""
    return True, name or "another program"


def port(ctx, check=port_user):
    busy, who = check(ctx.port)
    if not busy:
        return []
    return [{"kind": "port", "where": str(ctx.port), "name": f"spot {ctx.port}",
             "what": f"Your page's spot on this computer (number {ctx.port}) is already used by {who}.",
             "used": f"{who} answers there now.",
             "clash": "Two things cannot answer in one spot; your page would not open.",
             "choices": ["change"]}]


def tailscale_shares(ctx, status=None):
    if status is None:
        import shutil
        exe = shutil.which("tailscale") or (r"C:\Program Files\Tailscale\tailscale.exe" if os.path.exists(r"C:\Program Files\Tailscale\tailscale.exe") else "")
        if not exe:
            return []
        r = subprocess.run([exe, "funnel", "status", "--json"], capture_output=True, text=True, creationflags=NO_WINDOW, timeout=20)
        try:
            status = json.loads(r.stdout or "{}")
        except ValueError:
            return []
    web = (status or {}).get("Web") or {}
    if not web:
        return []
    return [{"kind": "tailscale", "where": "Tailscale", "name": "Tailscale",
             "what": f"Tailscale on this computer already shares {len(web)} thing(s) with the internet.",
             "used": "Something else of yours is reached through it.",
             "clash": "Nothing, as long as your page takes a spot that is free; that is left exactly as it is.",
             "choices": ["keep"]}]


def older_copies(ctx):
    out = []
    own_home = os.path.normcase(os.path.abspath(ctx.home))
    me = _json(os.path.join(ctx.home, "personal", "personal.json")) or {}
    answered = (_json(os.path.join(ctx.home, "personal", "setup.json")) or {}).get("answers") or {}
    if me.get("owner") and me.get("owner") != "the owner" and "name" not in answered:
        out.append({"kind": "home", "where": ctx.home, "name": "data",
                    "what": "An assistant's data is already in the place this setup uses.",
                    "used": "It came from an earlier assistant, not from this setup.",
                    "clash": "This setup would write over parts of it.",
                    "choices": ["keep", "remove"]})
    for top in ctx.project_roots:
        for here, dirs, files in os.walk(top):
            rel = os.path.relpath(here, top)
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and (rel == "." or rel.count(os.sep) < 3)]
            norm = os.path.normcase(os.path.abspath(here))
            if norm.startswith(os.path.normcase(os.path.abspath(ctx.root))):
                continue
            if os.path.exists(os.path.join(here, "setup_steps.py")) or (os.path.basename(here) == "Live" and os.path.exists(os.path.join(here, "personal", "personal.json"))):
                if norm == own_home:
                    continue
                kind = "data" if os.path.basename(here) == "Live" else "program"
                out.append({"kind": "older", "where": here, "name": os.path.basename(os.path.dirname(here)),
                            "what": f"An older copy of an assistant's {kind} is in {os.path.basename(os.path.dirname(here))}.",
                            "used": "It may still be running from there, or be left over.",
                            "clash": "Two assistants reading the same accounts make every card twice.",
                            "choices": ["keep", "remove"]})
                dirs[:] = []
    return out


SYNC_NAMES = {"onedrive": "OneDrive", "dropbox": "Dropbox", "google drive": "Google Drive", "my drive": "Google Drive",
              "icloud drive": "iCloud", "iclouddrive": "iCloud"}
SYNC_MARKERS = {".dropbox": "Dropbox", ".dropbox.cache": "Dropbox", ".tmp.drivedownload": "Google Drive",
                ".tmp.driveupload": "Google Drive", ".icloud": "iCloud", ".odcontainer": "OneDrive"}


def _onedrive_roots():
    """Where OneDrive keeps its folders on this computer, from its own settings (read only)."""
    roots = [os.environ.get(k) for k in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial")]
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\OneDrive\Accounts") as acc:
            i = 0
            while True:
                try:
                    name = winreg.EnumKey(acc, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(acc, name) as k:
                        roots.append(winreg.QueryValueEx(k, "UserFolder")[0])
                except OSError:
                    pass
    except (ImportError, OSError):
        pass
    extra = os.environ.get("ASSISTANT_SYNC_ROOTS", "")              # for tests: folders to treat as synced
    roots += [p for p in extra.split(os.pathsep) if p]
    return [os.path.normcase(os.path.realpath(r)) for r in roots if r]


def documents_folder():
    """The real place of this person's Documents, after any OneDrive redirection (read only)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
            return os.path.realpath(os.path.expandvars(winreg.QueryValueEx(k, "Personal")[0]))
    except (ImportError, OSError):
        return os.path.join(os.path.expanduser("~"), "Documents")


def synced(path):
    """(service name or "", plain why) when path is inside a folder a cloud service keeps uploading."""
    real = os.path.realpath(os.path.abspath(path))
    norm = os.path.normcase(real)
    for r in _onedrive_roots():
        if norm == r or norm.startswith(r.rstrip("\\/") + os.sep):
            return "OneDrive", "it is inside the folder OneDrive keeps uploading"
    for part in real.replace("/", "\\").split("\\"):
        low = part.lower()
        for word, name in SYNC_NAMES.items():
            if low == word or low.startswith(word + " -") or (word == "onedrive" and low.startswith("onedrive")):
                return name, f"it is inside a folder called \"{part}\""
    here = real
    while True:
        for marker, name in SYNC_MARKERS.items():
            if os.path.exists(os.path.join(here, marker)):
                return name, f"{name} has marked a folder it sits in"
        up = os.path.dirname(here)
        if up == here:
            break
        here = up
    return "", ""


SAFE_DEFAULT = r"C:\Assistant"


def sync_finding(ctx):
    name, why = synced(ctx.root)
    if not name:
        return []
    return [{"kind": "synced", "where": ctx.root, "name": name,
             "what": f"Your assistant's folder is kept in step with {name}: {why}.",
             "used": f"{name} uploads every file there and may lock, copy or bring back old versions of them.",
             "clash": "That gets in the way of Claude and your assistant changing their own files. A folder outside it, such as C:\\Assistant, avoids this.",
             "choices": ["keep"]}]


def scan(ctx, listed_jobs=None, port_check=port_user, tailscale_status=None):
    found = (sync_finding(ctx) + skills(ctx) + plugins(ctx) + jobs(ctx, listed_jobs) + connections(ctx) + projects(ctx)
             + port(ctx, port_check) + tailscale_shares(ctx, tailscale_status) + older_copies(ctx))
    for i, f in enumerate(found, 1):
        f["id"] = f"a{i}"
    return found


# --- acting on a decision (only after the person's yes) ------------------------------------------------
def remove_job(name):
    """Delete a scheduled job outright."""
    subprocess.run(["schtasks", "/End", "/TN", name], capture_output=True, text=True, creationflags=NO_WINDOW)
    r = subprocess.run(["schtasks", "/Delete", "/TN", name, "/F"], capture_output=True, text=True, creationflags=NO_WINDOW)
    if r.returncode:
        raise RuntimeError(f"Windows would not delete \"{name}\".")
    return name
