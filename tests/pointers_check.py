r"""Dead-pointer check: a message the owner can see must not send him somewhere that does not exist.

Reads the user-facing strings of the live page (engine/System/live_page/page.html) and of the Python modules that return
text to the page (engine/System/live/*.py), finds each phrase that points ("Open the key window in Settings", "in Settings,
under What it does for you", "Settings, Tools", "press Learn my voice now", "the Save button", "open the Email section"),
takes the named target, and checks it exists by that exact name. The real names come from the page's own sources:
Settings part titles (page.html sPart), Settings groups and item labels and Tools names (settings_data.py, tools.py),
section headings and button labels (page.html). No hand-kept list.

    python tests/pointers_check.py            quiet and exit 0 when clean; one line per bad message and exit 1 otherwise
"""
import ast
import glob
import os
import re
import sys

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYS = os.path.join(PKG, "engine", "System")
PAGE = os.path.join(SYS, "live_page", "page.html")
LIVE = os.path.join(SYS, "live")


def norm(s):
    s = re.sub(r"<[^>]+>|&[a-z]+;", " ", s)
    s = re.sub(r"[\"'`“”‘’.,:;!?()]", " ", s).lower()
    s = re.sub(r"^(the|your|a)\s+", "", " ".join(s.split()))
    return re.sub(r"\s+(section|button|part|item|tool)$", "", s)


def _consts(path):
    """(line, text) of every string constant that is not a docstring."""
    tree = ast.parse(open(path, encoding="utf-8").read())
    doc = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)) and n.body \
                and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant):
            doc.add(id(n.body[0].value))
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in doc:
            yield n.lineno, n.value


def page_lines():
    """(line, text) of the page's lines outside comments."""
    out, in_c = [], False
    for i, ln in enumerate(open(PAGE, encoding="utf-8").read().split("\n"), 1):
        s = ln
        if in_c:
            if "*/" not in s:
                continue
            s, in_c = s.split("*/", 1)[1], False
        s = re.sub(r"/\*.*?\*/", " ", s)
        if "/*" in s:
            s, in_c = s.split("/*", 1)[0], True
        if s.lstrip().startswith("//"):
            continue
        out.append((i, s))
    return out


def names():
    """Real names: settings (parts, groups, items, tools) and the page's headings and button labels."""
    page = open(PAGE, encoding="utf-8").read()
    settings, tools, others, conn = {"tools"}, set(), set(), set()
    for m in re.finditer(r"sPart\('[^']*',\s*'([^']+)'", page):
        settings.add(norm(m.group(1)))
        conn.add(norm(m.group(1)))
    sd = os.path.join(LIVE, "settings_data.py")
    tree = ast.parse(open(sd, encoding="utf-8").read())
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "GROUPS" for t in n.targets):
            for g in n.value.elts:
                settings.add(norm(g.elts[1].value))
                conn.add(norm(g.elts[1].value))
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_one" and len(n.args) > 2 \
                and isinstance(n.args[2], ast.Constant):
            settings.add(norm(n.args[2].value))
            # only a display item can hold a connection; a choice, list or text box cannot be reconnected
            if len(n.args) > 3 and isinstance(n.args[3], ast.Constant) and n.args[3].value in ("words", "rules", "checks"):
                conn.add(norm(n.args[2].value))
    tt = ast.parse(open(os.path.join(LIVE, "tools.py"), encoding="utf-8").read())
    for n in ast.walk(tt):
        if isinstance(n, ast.Dict):
            for k, v in zip(n.keys, n.values):
                if isinstance(k, ast.Constant) and k.value == "name" and isinstance(v, ast.Constant):
                    tools.add(norm(v.value))
    settings |= tools
    conn |= tools | {"tools"}
    # headings and button labels: the text of any element, and any short quoted label, in the page and the data files
    for _, ln in page_lines():
        for m in re.finditer(r">([^<>]{2,60})<", ln):
            others.add(norm(m.group(1)))
        for m in re.finditer(r"'([A-Z][^'<>]{1,50})'|\"([A-Z][^\"<>]{1,50})\"", ln):
            others.add(norm(m.group(1) or m.group(2)))
    for f in ("settings_data.py", "tools.py", "project_tools.py", "settings_page.py", "Setup.pyw", "onboard.py"):     # onboard: the setup cards' buttons
        for _, t in _consts(os.path.join(LIVE, f)):
            if len(t) < 60:
                others.add(norm(t))
    return settings, tools, others | settings, conn


T = r"([A-Z][A-Za-z0-9'’-]*(?: [A-Za-z0-9'’-]+){0,5}?)"      # a capitalised name of a few words
RULES = (
    # (regex, kind): kind says where the target must exist
    (re.compile(r"\b(?:Reconnect|Connect)\s+(?:the )?" + T + r"\s+in\s+Settings\b(?!,\s*(?:under\s+)?Tools)"), "connect"),
    (re.compile(r"\b(?:Set up|Open|Turn on|Turn off|Find)\s+(?:the )?" + T + r"\s+in\s+Settings\b(?!,\s*(?:under\s+)?Tools)"), "settings"),
    (re.compile(r"\b(?:Reconnect|Connect|Open|Find|[Rr]un the|[Uu]se the|Start on)\s+(?:the )?" + T + r"\s+in\s+Tools\b"), "tools"),
    (re.compile(r"\bStart on\s+" + T + r"\s+in\s+Settings, Tools\b"), "tools"),
    (re.compile(r"\b(?:[Rr]un|[Uu]se) the\s+" + T + r"\s+in\s+(?:Settings, )?Tools\b"), "tools"),
    (re.compile(r"Settings,\s+under\s+" + T + r"(?=[,.;:)\"]|$| where| to|\s*$)"), "settings"),
    (re.compile(r"\bpress(?:ed)? (?:the )?\"?([A-Z][A-Za-z0-9' ]{1,40}?)\"?(?=\s+(?:button|now|again|to|and|or|in)\b|[.,;)\"]|$)"), "button"),
    (re.compile(r"\bthe\s+\"?([A-Z][A-Za-z0-9' ]{1,40}?)\"?\s+button\b"), "button"),
    (re.compile(r"\bopen the\s+" + T + r"\s+section\b"), "section"),
)
# what a rule's sentence is not a pointer to: a word that merely starts a sentence
SKIP = {"it", "this", "that", "them", "here", "space", "enter", "escape", "tab", "shift"}   # words and keys, not buttons
OTHER_APP = re.compile(r"Safari|Chrome|Tailscale|Google Messages|iPhone|Android", re.I)   # a pointer into another program
# names the page no longer has: the card kinds are the Cards filters (Needs you, Waiting, FYI, Done, Hidden), Ready to send is
# Drafts in Email, Changes to your assistant is Change history in Settings; any of these in words the owner reads is a dead pointer
RETIRED = re.compile(r"Yours to decide|Small questions?|In motion|For your information|Handled for you|Done on your say-so|"
                     r"Ready to send(?! the)|Changes to your assistant|Finished (?:list|section)|Finished in the last|finished cards")
# old names of Settings parts, the Someday choice, the held list and the 15-minute check (the wording audit of 11/22/26):
# the parts are Sources, Filters, Appearance, Approvals, Writing style, AI and usage; a card put off with no date is under Someday;
# what was kept off the page is under Hidden ("Hidden today: 43." is the card that opens it); the scheduled run is a check
RETIRED_MORE = re.compile(r"Someday shelf|next gathering|middle of gathering|What it watches|"
                          r"What reaches you|What it does for you|How the page looks|Settings, (?:under )?\"?Your voice|Thinking and cost|"
                          r"Learn my voice|thinking runs|next pass|Dismiss")
# the wording decisions of 11/22/26 (second round): messages kept off the page are Hidden (never "Held back" as a filter or tag, nor
# "held-back list"), the tool is the Writing style builder, a card is snoozed (never "Later" as its button or state, nor "Put off to"),
# the section is Talk to your assistant (never "the chat"), the approval level is "Do it and notify me" (never "tell me"; the old
# lower-case answer "yes, do it and tell me" is still accepted from an old card), and a phone message is a notification (never an alert)
RETIRED_WORDS = re.compile(r"Held back|Held because|held-back list|held back today|Voice builder|"
                           r"[Pp]ut (?:it )?off (?:to|until) (?!the next check)|Later, back|Later to \d|Back from Later|Later options|Default date for Later|"
                           r"What Later offers|(?:press|pressing|the) Later(?: button| on a card)|Later dates|"
                           r"\bthe (?:page's )?chat\b(?!['(]|\.\w)|(?<!yes, )[Dd]o it and tell me|done and told")
# the Email section was named Mail until 11/23/26: the old name only where it names the section ("in Mail", "the Mail part",
# "Mail's header", "Today, Mail, Texts"), never the word mail itself, Mail rules (the services' own rules) or Mail.ReadWrite
RETIRED_SECTION = re.compile(r"\b(?:[Ii]n|of|to|under|at) (?:the )?Mail\b(?!\.\w|\s+rules)|\b[Tt]he Mail (?:part|section|page)\b|\bMail's header|"
                             r"\bMail part\b|, Mail\b(?!\.\w|\s+rules)")
ALERT = re.compile(r"(?<![\w\"'.\-/_|])[Aa]lerts?(?![\w\"'\-/_?]|\.\w)")     # the word as prose; role="alert", the settings key and "alerts?|" are not


def scan():
    settings, tools, anything, conn = names()
    bad = []
    srcs = [(PAGE, l, t) for l, t in page_lines()]
    for f in sorted(glob.glob(os.path.join(LIVE, "*.py"))):
        srcs += [(f, l, t) for l, t in _consts(f)]
    for path, line, text in srcs:
        if OTHER_APP.search(text):
            continue
        for rx, kind in RULES:
            for m in rx.finditer(text):
                tgt = norm(m.group(1))
                if not tgt or tgt.split()[0] in SKIP:
                    continue
                pool = {"settings": settings, "tools": tools, "connect": conn}.get(kind, anything)
                if kind == "button":       # "Send on goes out": the name may be followed by more words; "Sign" may be "Sign in"
                    ok = any(tgt == n or tgt.startswith(n + " ") or n.startswith(tgt + " ") for n in pool)
                else:
                    ok = tgt in pool
                if not ok:
                    where = {"connect": "Settings has no part, item or tool you can connect named", "settings": "Settings has no part, item or tool named", "tools": "Tools has no tool named",
                             "button": "the page has no button or label named", "section": "the page has no section named"}[kind]
                    bad.append((os.path.relpath(path, PKG), line, m.group(0).strip(), f"{where} \"{m.group(1)}\""))
    docs = sorted(glob.glob(os.path.join(LIVE, "rules", "*.md")) + glob.glob(os.path.join(LIVE, "prompts", "*.md")) +
                  glob.glob(os.path.join(LIVE, "SETUP.md")) + glob.glob(os.path.join(LIVE, "setup", "**", "*.md"), recursive=True))
    for f in docs:
        srcs += [(f, i + 1, t) for i, t in enumerate(open(f, encoding="utf-8").read().splitlines())]
    srcs += [(os.path.join(LIVE, "Setup.pyw"), l, t) for l, t in _consts(os.path.join(LIVE, "Setup.pyw"))]
    for path, line, text in srcs:
        m = RETIRED.search(text) or RETIRED_MORE.search(text) or RETIRED_WORDS.search(text) or RETIRED_SECTION.search(text)
        a = ALERT.search(text)
        if not m and a and a.group(0) != text.strip():
            m = a
        if m:
            bad.append((os.path.relpath(path, PKG), line, m.group(0), "a name the page no longer has"))
    return sorted(set(bad))


def main():
    bad = scan()
    for f, l, msg, why in bad:
        print(f"{f}:{l}: \"{msg}\" - {why}")
    if bad:
        print(f"{len(bad)} message(s) point at something that does not exist.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
