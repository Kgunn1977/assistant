r"""The assistant's guard: a PreToolUse hook that asks the guardrails of each laid-down copy of the assistant whether
a tool call may go ahead. It holds no rule and no routing of its own (decided 11/17/26): it gathers the tool call,
runs `python <root>\System\live\rules\rulebook.py route -` with it, and refuses when that says so. The
guardrails decide which guards (a) to (e) apply, where, and to what, and is run fresh on every call, so a committed rule
change is enforced without touching this file.

Where it runs:
  - in every Claude session, from the plugin's hooks.json;
  - in the assistant's hidden runs, from the settings file lay-down writes (<home>\personal\guard_settings.json),
    with --root naming the copy it guards.

What it promises, whatever the guardrails say:
  - reading is never blocked (READ_ONLY tools return at once, before any guardrails run);
  - it never touches the roadmap's own hooks or their files; it only answers for its own call;
  - the guardrails' exit 2 refuses; exit 1 (the check itself failed) refuses too in a hidden run, in a session inside
    the assistant's folder, or when the call names a copy or a project's .assistant folder; unrelated work elsewhere
    goes on. When a copy's guardrails are not there at all (its program folder is missing or half gone), only a send is
    refused there (a connector's sending tool, or a command the plugin's own copy of the guardrails judges would send),
    so file work, messages to helpers and the repair itself go through while sending stays shut.
Exit 0 lets the call through; exit 2 refuses it, naming each broken rule in the guardrails' own sentence on stderr
(Claude Code shows it to Claude). The event it sends is made by event() below (RULEBOOK.md, hooks section).
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)

READ_ONLY = {"Read", "Glob", "Grep", "LS", "WebFetch", "WebSearch", "ToolSearch", "TodoRead", "ListMcpResourcesTool",
             "ReadMcpResourceTool", "ListAgents", "TaskList", "TaskGet", "TaskOutput", "NotebookRead"}
FILE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
SHELL_TOOLS = {"Bash", "PowerShell"}
WRITE_WORDS = re.compile(r"(^|[\s;|&(])(set-content|sc|add-content|ac|out-file|copy-item|cpi|copy|cp|move-item|mi|move|mv|"
                         r"remove-item|ri|rm|rmdir|rd|del|erase|ren|rename-item|rni|new-item|ni|tee|tee-object|clear-content|"
                         r"truncate|dd|install|ln|robocopy|xcopy|attrib|icacls|takeown|mkdir|md|touch)(\s|$)"
                         r"|sed\s+(-\w*\s+)*-i|writealltext|writeallbytes|appendalltext|\[io\.file\]|open\(|write_text|"
                         r"write_bytes|shutil\.|os\.(remove|unlink|rename|replace|makedirs)|>{1,2}", re.I)
RULEBOOK = os.path.join("System", "live", "rules", "rulebook.py")
HARMLESS_REDIRECT = re.compile(r"\d?>&\d|\d?>{1,2}\s*(?:/dev/null|nul|\$null)(?![\w.])", re.I)     # joins or drops output: writes no file


def norm(p):
    return os.path.normcase(os.path.abspath(p)) if p else ""


def inside(path, folder):
    path, folder = norm(path), norm(folder)
    return bool(path) and (path == folder or path.startswith(folder.rstrip("\\/") + os.sep))


def roots(argv):
    """The copies of the assistant this call is checked against: the one named with --root (a hidden run), else
    every copy recorded by lay-down in the plugin's working copy."""
    if "--root" in argv:
        i = argv.index("--root")
        return [argv[i + 1]] if i + 1 < len(argv) else []
    found = []
    for base in (os.environ.get("CLAUDE_PLUGIN_DATA"), PLUGIN):
        try:
            with open(os.path.join(base, "roots.json"), encoding="utf-8") as f:
                found += [r for r in json.load(f).get("roots") or [] if isinstance(r, str)]
        except (OSError, ValueError, TypeError):
            continue
    out, seen = [], set()
    for r in found:
        if norm(r) not in seen and os.path.isdir(r):
            seen.add(norm(r))
            out.append(r)
    return out


def final_text(tool, ti, path):
    """What the file will hold after a file tool runs, when that can be known; None when it cannot."""
    if tool == "Write":
        return ti.get("content")
    if tool in ("Edit", "MultiEdit"):
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            text = ""
        edits = ti.get("edits") if tool == "MultiEdit" else [ti]
        for e in edits or []:
            old, new = e.get("old_string") or "", e.get("new_string") or ""
            if not old:
                text = new + text
            elif e.get("replace_all"):
                text = text.replace(old, new)
            elif old in text:
                text = text.replace(old, new, 1)
            else:
                return None
        return text
    return None


def event(data, root, hidden):
    tool = data.get("tool_name") or ""
    ti = data.get("tool_input") or {}
    cwd = data.get("cwd") or os.getcwd()
    ev = {"tool": tool, "input": ti, "cwd": cwd, "root": os.path.abspath(root), "home": os.path.join(os.path.abspath(root), "Live"),
          "where": "hidden" if hidden else ("assistant" if inside(cwd, root) else "elsewhere"),
          "writes": [], "command": None, "command_writes": False, "session": data.get("session_id")}
    if tool in FILE_TOOLS:
        path = ti.get("file_path") or ti.get("notebook_path") or ""
        path = path if os.path.isabs(path) else os.path.join(cwd, path)
        ev["writes"].append({"path": os.path.abspath(path), "text": final_text(tool, ti, path)})
    elif tool in SHELL_TOOLS:
        ev["command"] = str(ti.get("command") or "")
        ev["command_writes"] = bool(WRITE_WORDS.search(HARMLESS_REDIRECT.sub(" ", ev["command"])))
    return ev


def names_guarded(data, rts):
    """True when the call names a copy of the assistant or a project's .assistant folder (for failing closed)."""
    ti = data.get("tool_input") or {}
    text = json.dumps(ti).replace("\\\\", "\\").lower().replace("/", "\\")
    if "\\.assistant\\" in text or text.endswith("\\.assistant"):
        return True
    return any(norm(r).lower() in text for r in rts)


def ask(root, ev):
    """Run the copy's guardrails on one tool call: (exit code, verdict or None). 0 = through, 2 = refused, 1 = the check
    itself failed. Run as its own program (RULEBOOK.md section 3), so it is read fresh every time."""
    book = os.path.join(root, RULEBOOK)
    if not os.path.isfile(book):
        return 1, {"why": "the guardrails are not there"}
    try:
        r = subprocess.run([sys.executable, book, "route", "-"], input=json.dumps(ev), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=20, cwd=os.path.dirname(book),
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, {"why": f"the guardrails did not answer ({type(e).__name__})"}
    try:
        verdict = json.loads(r.stdout or "null")
    except ValueError:
        verdict = None
    code = r.returncode if r.returncode in (0, 2) else 1
    return code, verdict


def refusal(verdict):
    """The guardrails' own words: each broken rule's id and sentence."""
    broken = (verdict or {}).get("broken") or [] if isinstance(verdict, dict) else []
    said = [f"rule {b.get('rule')}: {b.get('says')}" for b in broken if isinstance(b, dict) and b.get("rule")]
    return "; ".join(said) or "a rule was broken (the guardrails named none)"


PLUGIN_BOOK = os.path.join(PLUGIN, "engine", RULEBOOK)
SEND_WORDS = re.compile(r"send|smtp|postmessage|ntfy", re.I)


def sends_without_book(data):
    """With no guardrails in the copy: True when this call would send, judged by the plugin's own copy of the guardrails
    (the same sending check, only read); when even that cannot be read, any call that names sending counts as one."""
    tool = data.get("tool_name") or ""
    ti = data.get("tool_input") or {}
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("plugin_rulebook", PLUGIN_BOOK)
        book = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(book)
    except Exception:  # noqa: BLE001  no sending check to read: anything that names sending is held back
        return bool(SEND_WORDS.search(tool if tool.startswith("mcp__") else str(ti.get("command") or "")))
    if tool.startswith("mcp__"):
        return not book.APP_TOOL.search(tool) and bool(book.SEND_TOOL.search(tool.split("__")[-1]))
    if tool in SHELL_TOOLS:
        return book.would_send(str(ti.get("command") or ""))
    return False


def decide(data, argv):
    tool = data.get("tool_name") or ""
    if tool in READ_ONLY:
        return None
    hidden = "--root" in argv
    rts = roots(argv)
    for root in rts:
        ev = event(data, root, hidden)
        code, verdict = ask(root, ev)
        if code == 2:
            return refusal(verdict)
        if code == 1 and not os.path.isfile(os.path.join(root, RULEBOOK)):
            # no guardrails: only sending stays shut, so a broken assistant can be put right
            if (hidden or ev["where"] != "elsewhere" or names_guarded(data, rts)) and sends_without_book(data):
                return f"its guardrails are missing in {root}, and nothing is sent while they are (rule B1)"
            continue
        if code == 1:
            # a check that cannot run fails closed for the assistant's own work, never for unrelated work elsewhere
            if hidden or ev["where"] != "elsewhere" or names_guarded(data, rts):
                why = (verdict or {}).get("why") if isinstance(verdict, dict) else None
                return f"this could not be checked against the guardrails in {root} ({why or 'its check failed'})"
    return None


def main(argv):
    try:
        data = json.load(sys.stdin)
    except Exception:  # noqa: BLE001
        print("Refused by the assistant's guard: the call could not be read.", file=sys.stderr)
        return 2
    try:
        why = decide(data, argv)
    except Exception as e:  # noqa: BLE001
        tool = data.get("tool_name") or ""
        try:
            closed = tool not in READ_ONLY and ("--root" in argv or names_guarded(data, roots(argv)))
        except Exception:  # noqa: BLE001
            closed = tool not in READ_ONLY and "--root" in argv
        if not closed:
            return 0
        why = f"the guard itself failed ({type(e).__name__}), so this cannot be checked"
    if why:
        print("Refused by the assistant's guardrails, " + why, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
