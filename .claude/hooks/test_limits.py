r"""PreToolUse hook (Bash, Read, Grep) for every session working in this repo: keeps testing light, in code.

Refuses:  a test command that runs more than 2 test files, or a whole tests folder, or a glob of tests;
          any copy, open or read of the owner's real database (Assistant\Live\Resources\Database), or a copy of the Live folder;
          a 9th test command in one session (the session reports instead).
Allows a test command with its timeout set to 2 minutes.

The coordinator can allow one exception: write a file named  <session id>.once  (that session) or  any.once  (the next session
to ask) into  ~/.claude/assistant-test-allow/ , or set ASSISTANT_TEST_ALLOW=1 in that session's environment. A .once file is used up by the
one command it allows (a full run, more files, or the real data).
"""
import json, os, re, sys, tempfile

MAX_FILES = 2
MAX_RUNS = 8
TIMEOUT_MS = 120000
ALLOW_DIR = os.path.join(os.path.expanduser("~"), ".claude", "assistant-test-allow")
ASK = " If you truly need a full run or the real data, ask the coordinator (the session that started you) to allow it, and wait for its answer; otherwise report what you have."


def refuse(why):
    sys.stderr.write("Refused by this repo's test limits: " + why + ASK + "\n")
    sys.exit(2)


def norm(s):
    return str(s).replace("\\", "/").lower()


def allowance(session):
    """True when the coordinator allowed this one command (a .once token is used up here)."""
    if os.environ.get("ASSISTANT_TEST_ALLOW") == "1":
        return True
    for name in (session + ".once", "any.once"):
        p = os.path.join(ALLOW_DIR, name)
        if os.path.isfile(p):
            try:
                os.remove(p)
            except OSError:
                pass
            return True
    return False


def touches_real_data(text):
    n = norm(text)
    if "assistant/live/resources" in n:
        return True
    return "claudeos/assistant/live" in n and re.search(r"\b(copy|cp|xcopy|robocopy|copytree|copy-item|shutil|mv|move)\b", n) is not None


TEST_FILE = re.compile(r"(?:^|[\/])(?:test_[^\/\s]*|[^\/\s]*_(?:acceptance|test|check))\.py$", re.I)


def test_segments(command):
    """The parts of the command (split at && ; | newline) that run tests."""
    out = []
    for seg in re.split(r"&&|\|\||;|\||\n", command):
        s = seg.strip()
        if re.search(r"(^|\s)(pytest|py\.test)(\s|$)", s) or re.search(r"-m\s+(pytest|unittest)\b", s):
            out.append(s)
        elif re.search(r"(^|[\s\"'])(python3?|py)(\.exe)?[\"']?\s", s, re.I) and any(TEST_FILE.search(t.strip("\"'")) for t in s.split()):
            out.append(s)
        elif re.search(r"(^|[\s\"'])(python3?|py)(\.exe)?[\"']?\s.*\btests?[\/]", s, re.I):
            out.append(s)
    return out


def check_tests(segments):
    files = set()
    for s in segments:
        toks = [t.strip("\"'") for t in s.split()]
        pyfiles = [t for t in toks if t.lower().endswith(".py")]
        for t in toks:
            if any(c in t for c in "*?[") and ("test" in t.lower() or t.lower().endswith(".py")):
                return "a glob of tests (" + t + ") would run many test files."
            if re.search(r"(^|[\/])tests?[\/]*$", t, re.I) or re.search(r"(discover|-k)\b", t):
                return "a whole tests folder (" + t + ") would run every test."
        if re.search(r"pytest|unittest", s) and not pyfiles:
            return "pytest or unittest with no test file named would run every test."
        files.update(norm(t) for t in pyfiles)
    if len(files) > MAX_FILES:
        return f"this command runs {len(files)} test files; the limit is {MAX_FILES} (the one for what you changed)."
    return None


def count_run(session):
    p = os.path.join(tempfile.gettempdir(), "assistant_test_runs")
    os.makedirs(p, exist_ok=True)
    f = os.path.join(p, re.sub(r"[^\w.-]", "_", session) + ".txt")
    n = 0
    try:
        n = int(open(f).read().strip() or 0)
    except (OSError, ValueError):
        pass
    return f, n


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    tool, inp, session = data.get("tool_name"), data.get("tool_input") or {}, str(data.get("session_id") or "unknown")
    probe = inp.get("command") if tool == "Bash" else " ".join(str(inp.get(k) or "") for k in ("file_path", "path", "pattern", "glob"))
    probe = probe or ""
    if touches_real_data(probe):
        if allowance(session):
            return 0
        refuse("the owner's real database and Live folder are not copied, opened or read in testing.")
    if tool != "Bash":
        return 0
    segs = test_segments(probe)
    if not segs:
        return 0
    if allowance(session):
        return 0
    why = check_tests(segs)
    if why:
        refuse(why)
    f, n = count_run(session)
    if n >= MAX_RUNS:
        refuse(f"{MAX_RUNS} test commands have already run in this session; report instead of testing more.")
    try:
        open(f, "w").write(str(n + 1))
    except OSError:
        pass
    inp = dict(inp)
    inp["timeout"] = min(int(inp.get("timeout") or TIMEOUT_MS), TIMEOUT_MS)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                              "permissionDecisionReason": f"test command {n + 1} of {MAX_RUNS}, 2-minute limit",
                                              "updatedInput": inp}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
