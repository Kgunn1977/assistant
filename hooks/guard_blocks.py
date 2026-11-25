"""PreToolUse hook on file tools and terminal commands: the lock on the guardrails themselves. Kevin 11/25/26: guards
"only prevent really bad things", and "The roadmap IS NOT A CRITICAL FUNCTION. it should have very few blocks." So in a
project that has been set up it refuses only a real change to what switches every guard on: the project's settings
files (.claude/settings*.json) and hook scripts (.claude/hooks) (unless config says "lock_settings": false), and the
plugin's own hooks.json and this lock, in the plugin's folder and its working copy (SAFEGUARDS below). The roadmap's
ids and logbook, its holds and its setup script are ordinary files, and switching the roadmap off or on is not refused.
A write is judged by the paths it actually writes, moves or deletes: a file tool's path, a shell part's targets (a
copy: where it copies to), a redirect's target, and the paths on the writing lines of code it runs (python -c,
here-documents, scripts). Words that only mention a guard (a commit message, a document, a test, code that reads one)
never count, a path that cannot be worked out is not refused, and ordinary git work goes through; a git command is
refused only when it changes one of those files by path (git checkout main -- .claude/settings.json). If this check
itself fails, the call is refused. A project that has not been set up is left alone.
It also notes which session ran the plugin's setup script, so setup can record that session's id."""
import json, os, posixpath, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import roadmap_blocks as rb
import working_copy

PLUGIN_ROOT = os.path.dirname(HERE)
SETUP_SCRIPT = "roadmap_setup.py"
# the plugin's own guard switches: what turns every hook on, and this lock
SAFEGUARDS = ("hooks/guard_blocks.py", "hooks/hooks.json")
SETTINGS = re.compile(r"\.claude/(settings[^/\s\"']*\.json|hooks([/\s\"';|&)]|$))")
WRITES = re.compile(r"(^|[\s;|&(])(set-content|sc|add-content|ac|out-file|copy-item|cpi|copy|cp|move-item|mi|move|mv|"
                    r"remove-item|ri|rm|rmdir|rd|del|erase|ren|rename-item|rni|new-item|ni|tee|tee-object|clear-content|"
                    r"truncate|dd|install|ln|robocopy|xcopy|attrib|icacls|takeown)(\s|$)"
                    r"|sed\s+(-\w*\s+)*-i|writealltext|writeallbytes|appendalltext|\[io\.file\]|write_text|write_bytes|"
                    r"open\([^)]*,\s*(mode\s*=\s*)?[\"'][^\"']*[wax+]|\.open\(\s*(mode\s*=\s*)?[\"'][^\"']*[wax+]|"
                    r"shutil\.|os\.(remove|unlink|rename|replace)|"
                    r"writefilesync|appendfilesync|\bfs\.(promises\.)?(writefile|appendfile|unlink|rm|rmdir|rename|copyfile|truncate|mkdir)\b", re.I)
_NOT_NULL = r"(?!&|\s*\$null|\s*/dev/null|\s*nul\b)"
REDIRECT = re.compile(r"(?<![0-9&-])>{1,2}" + _NOT_NULL + r"|(?:(?<=\s)|^)[0-9]>{1,2}" + _NOT_NULL, re.I | re.M)
SED_W = re.compile(r"""\bsed\b[^|;&\n]*?(['";{}\s]|/)[\d,$!]*w\s+[^\s'"]""")
NESTED = re.compile(r"""(^|[\s;|&(])(iex|invoke-expression|cmd(\.exe)?\s+/[ck]|(ba|z|da|k)?sh(\.exe)?(\s+-\w+)*\s+-c|"""
                    r"""(powershell|pwsh)(\.exe)?(\s+-\w+)*\s+-c(ommand)?)\s+(?P<s>"[^"]*"|'[^']*')""")
TOKEN = re.compile(r"""\"([^\"]*)\"|'([^']*)'|([^\s"'`;|&()<>,=]+)""")
TARGET = re.compile(r"""\s*("[^"]*"|'[^']*'|[^\s"';|&()<>]+)""")
POPD = re.compile(r"^\s*\(?\s*(popd|pop-location)(\s|$|\))")
SETS = re.compile(r"(^|[\s;|&(])(?:(?:export|local|declare|typeset|readonly)\s+(?:-\w+\s+)*([a-z_]\w*)\+?=|([a-z_]\w*)\+?=|"
                  r"for\s+([a-z_]\w*)\s+in\b|read\s+(?:-\w+\s+(?:\S+\s+)?)*([a-z_]\w*)|\$([a-z_]\w*)\s*\+?=|"
                  r"foreach\s*\(\s*\$([a-z_]\w*))")
CD_ANY = re.compile(r"(^|[\s;|&(])(cd|chdir|pushd|push-location|set-location|sl)(\s|$)", re.M)
# inline code (python -c and the like) counts as a write only when it can change files or start something that might
RISKY_INLINE = re.compile(r"subprocess|os\.(system|popen|open|exec|spawn|startfile|mkdir|makedirs|rmdir|removedirs|chmod)|"
                          r"\bexec\(|\beval\(|__import__|importlib|\bfs\.\w*(write|append|unlink|rm|rename|copy|mkdir|truncate)|"
                          r"child_process|\bsystem\(|\bunlink\b|file\.(write|delete|move|copy)", re.I)
QUOTED = re.compile(r"\"[^\"]*\"|'[^']*'")                    # backslashes are already slashes after norm()
INLINE = re.compile(r"(^|[\s;|&(])(python[\d.]*|py|node|perl|ruby|powershell|pwsh)(\.exe)?\s+(-\w+\s+)*-(c|e|command)\b", re.I)
SCRIPT = re.compile(r"""[^\s"';|&]*\.(?:py|pyw|ps1|sh|bat|cmd)\b|"[^"]+\.(?:py|pyw|ps1|sh|bat|cmd)"|'[^']+\.(?:py|pyw|ps1|sh|bat|cmd)'""", re.I)
UPDATE = re.compile(r"""roadmap_setup\.py["']?\s+updated?(\s|$)""")
OFF = re.compile(r"""roadmap_setup\.py["']?(\s+--project\s+(\"[^\"]*\"|'[^']*'|\S+))?\s+off(\s|$)""")
CHAINS = re.compile(r"[;|&<>`\n]|\$\(")
# reading a command part by part: here-documents, the parts, plain variables, directory changes, code an interpreter runs
PS_HERE = re.compile(r"""@(['"])[ \t]*\n(.*?)\n[ \t]*\1@""", re.S)       # a PowerShell here-string
PS_RUNS = re.compile(r"""\s*\|\s*(iex|invoke-expression|powershell|pwsh|cmd|bash|sh)\b""")
HEREDOC = re.compile(r"""<<-?[ \t]*(['"]?)([a-z_][\w-]*)\1""")
MARK = re.compile("\x00\\d+\x00")
LAST = re.compile(r"(;|&&|\|\||\|)")
CODE_IN = re.compile(r"""^\s*\(?\s*["']?[^\s"']*(python[\d.]*|py|pythonw|node|perl|ruby)(\.exe)?["']?(\s+-[\w-]+)*(\s+-)?\s*$""")
SHELL_IN = re.compile(r"""^\s*\(?\s*["']?[^\s"']*(bash|sh|zsh|dash|ksh|powershell|pwsh|cmd)(\.exe)?["']?(\s+-[\w-]+)*(\s+-)?\s*$""")
SEP = re.compile(r"\"[^\"]*\"|'[^']*'|(&&|\|\||;|\n)")
ASSIGN = re.compile(r"""^\s*(export\s+)?([a-z_]\w*)=("[^"$`]*"|'[^']*'|[^\s"'$`;|&()<>]+)\s*$|^\s*\$([a-z_]\w*)\s*=\s*("[^"$`]*"|'[^']*')\s*$""")
VAR = re.compile(r"\$\{?([a-z_]\w*)\}?")
DYNAMIC = re.compile(r"\$\(|`|\$(?!(null|true|false|lastexitcode)\b)[\w{]|(^|[\s|;&(])(xargs|eval|iex|invoke-expression|source)(\s|$)")
CD = re.compile(r"""^\s*\(?\s*(cd|chdir|pushd|push-location|set-location|sl)(\s|$)""")
CD_TO = re.compile(r"""^\s*\(?\s*(cd|chdir|pushd|push-location|set-location|sl)(\s+/d)?(\s+-(literal)?path)?\s+("[^"]*"|'[^']*'|[^\s"'();|&]+)\s*\)?\s*$""")
READS = re.compile(r"""^\s*\(?\s*(cat|type|get-content|gc|more|less|head|tail|wc|grep|egrep|fgrep|rg|findstr|select-string|sls|"""
                   r"""ls|dir|get-childitem|gci|stat|diff|fc|git\s+(diff|show|log|blame|grep|status)|sed\s+-n)(\s|$)""")
CODE_ARG = re.compile(r"""((^|[\s;|&("'])(python[\d.]*|py|pythonw|node|perl|ruby)(\.exe)?["']?\s+(-[\w-]+\s+)*-(c|e)\s+)("[^"]*"|'[^']*')""")
STRINGS = re.compile(r"""'''.*?'''|\"\"\".*?\"\"\"|"[^"\n]*"|'[^'\n]*'|`[^`]*`""", re.S)
STARTS = re.compile(RISKY_INLINE.pattern + r"|\broadmap_setup\b|\brunpy\b", re.I)
# ordinary git work (merge, apply, checkout, reset ...) is let through; only a git command that changes files and names a
# safeguard path (git checkout main -- .claude/settings.json, git rm of one) is judged as a write to it
GIT = re.compile(r"""^\s*\(?\s*["']?[^\s"']*git(\.exe)?["']?\s""")
GIT_CHANGES = {"checkout", "restore", "rm", "mv", "apply", "reset", "stash", "clean", "switch", "am", "merge", "pull", "rebase",
               "cherry-pick", "revert"}
SAFE_NAMES = {f.rsplit("/", 1)[-1] for f in SAFEGUARDS}
# Kevin 11/25/26 ("only prevent really bad things"): a write is judged by the paths it can reach, never by prose that
# mentions a safeguard. A quoted text counts as a path only when it looks like one (a drive, a slash or ./ at its start, or
# no spaces); text a here-document only carries (cat > x <<EOF ... EOF) is content, not a target.
PATHLIT = re.compile(r"^([a-z]:/|/|\.\.?/|~/|[^\s]+$)")


def path_words(code):
    """The string literals in code that look like paths, each quoted, one per line."""
    out = []
    for m in STRINGS.finditer(code):
        s = m.group()
        inner = s[3:-3] if s[:3] in ("'''", '"""') else s[1:-1]
        if inner and "\n" not in inner and PATHLIT.match(inner):
            out.append('"' + inner + '"')
    return "\n".join(out)


# code (python -c, a here-document python runs, a script that is run) is judged by the paths on its writing lines only:
# the path texts on a line that writes, moves or deletes, and the path texts plainly given to a name that such a line
# uses (p = Path(".claude/settings.json") ... p.write_text(x)). A path the code only reads is not a target.
CODE_SET = re.compile(r"""^\s*\$?([a-z_]\w*)\s*=\s*(.*)$""")
CODE_RUN = re.compile(r"subprocess|os\.(system|popen|exec\w*|spawn\w*|startfile)|start-process|\bsystem\(|"
                      r"child_process|(^|[\s;(])&\s*[\"'$]", re.I)
# a name holds a path only when it is given one plainly: a path text, Path("..."), os.path.join(...) of texts
CODE_PATH = re.compile(r"""^\s*(r?"[^"]*"|r?'[^']*'|(pathlib\.)?path\(\s*r?("[^"]*"|'[^']*')\s*\)|os\.path\.join\(\s*(r?("[^"]*"|'[^']*')\s*,?\s*)+\))\s*;?\s*$""")
COPY_CMD = re.compile(r"""^\s*\(?\s*(cp|copy|cpi|copy-item)(\s|$)""")
COPY2_CMD = re.compile(r"""^\s*\(?\s*(robocopy|xcopy)(\s|$)""")


JOIN = re.compile(r"""(os\.path\.join|path)\(\s*((r?("[^"]*"|'[^']*')\s*,?\s*)+)\)""")


def joined(text):
    """text with each os.path.join("a", "b") or Path("a", "b") of plain texts written as the one path "a/b"."""
    return JOIN.sub(lambda m: '"' + "/".join(s[1:-1] for s in re.findall(r"""r?("[^"]*"|'[^']*')""", m.group(2))) + '"', text)


def code_targets(code):
    """The paths code can write to: path texts on its writing lines, and those given to names its writing lines use."""
    names, out = {}, []
    lines = [joined(ln) for ln in norm(code).split("\n")]
    for line in lines:
        m = CODE_SET.match(line)
        if m and CODE_PATH.match(m.group(2)):
            lits = path_words(m.group(2))
            if lits:
                names[m.group(1)] = lits
    for line in lines:
        if not (WRITES.search(line) or SED_W.search(line)):
            continue
        out.append(path_words(line))
        for name, lits in names.items():
            if re.search(r"(?<![\w.])" + re.escape(name) + r"\b", line):
                out.append(lits)
    return "\n".join(o for o in out if o)


def copy_target(seg):
    """For a copy command, only where it copies to: -destination's value, else the last word (robocopy and xcopy:
    the second); the source is only read."""
    words = [w for w in re.findall(r"\"[^\"]*\"|'[^']*'|\S+", seg)][1:]
    for i, w in enumerate(words):
        if w.startswith("-destination") and i + 1 < len(words):
            return words[i + 1]
    plain = [w for w in words if not w.startswith("-") and not (w.startswith("/") and len(w) <= 4)]
    if COPY2_CMD.match(seg):
        return plain[1] if len(plain) > 1 else ""
    return plain[-1] if plain else ""


def target_text(shell, own=()):
    """What a command part can write to: its shell words with prose strings left out (a copy: only where it copies
    to), the paths code it runs writes to, and code handed to another shell; here-document content is left out."""
    s = norm(shell)
    extra = [target_text(n) for n in nested(s)]
    s = CODE_ARG.sub(lambda m: (extra.append(code_targets(m.group(7)[1:-1])) or m.group(1)) + '""', s)
    if COPY_CMD.match(s) or COPY2_CMD.match(s):
        s = copy_target(s)
    s = QUOTED.sub(lambda q: q.group() if PATHLIT.match(q.group()[1:-1]) else '""', s)
    parts = [s] + extra
    for k, b in own:
        if k == "code":
            parts.append(code_targets(b))
        elif k == "shell":
            parts.append(target_text(b))
    return "\n".join(p for p in parts if p)


def norm(text):
    return re.sub(r"/+", "/", (text or "").replace("\\", "/")).lower()


def root_forms(root):
    """The plugin folder as it may be written: C:/x/y and, in Git Bash, /c/x/y."""
    r = norm(root).rstrip("/")
    forms = {r}
    m = re.match(r"^([a-z]):/(.*)$", r)
    if m:
        forms.add("/" + m.group(1) + "/" + m.group(2))
    return forms


def real(p):
    """p ("c:/x/y") with junctions and links followed, as far as the folders exist; p itself when that fails."""
    try:
        return posixpath.normpath(norm(os.path.realpath(p)))
    except (OSError, ValueError):
        return p


def resolve(tok, here):
    """A path word as a full path ("c:/x/y"), read from the folder here; None when it cannot be known (a variable, a
    wildcard, the home folder, or a relative path where the folder is not known; a redirect with no readable target)."""
    if tok is None:
        return None
    tok = norm(tok.replace("\\ ", " ")).replace("\x01", " ").strip().strip("\"'").rstrip(",")
    if not tok or re.search(r"[$%*?`{]", tok) or tok.startswith("~"):
        return None
    m = re.match(r"^/([a-z])(/.*)?$", tok)                    # Git Bash /c/x is c:/x
    if m:
        tok = m.group(1) + ":/" + (m.group(2) or "").lstrip("/")
    if re.match(r"^[a-z]:", tok):
        tok = tok[:2] + "/" + tok[2:].lstrip("/")
    elif not tok.startswith("/"):
        if here is None:
            return None
        tok = here.rstrip("/") + "/" + tok
    return posixpath.normpath(tok)


def tokens(t):
    """The words of a text that may be paths: quoted strings whole and the words inside them (code handed to python
    -c, sh -c and the like), and unquoted runs."""
    out = []
    for m in TOKEN.finditer(t):
        quoted = m.group(3) is None
        s = (m.group(1) if m.group(1) is not None else m.group(2) if quoted else m.group(3)).replace("\x01", " ")
        out.append(s)
        if quoted and s != t:
            out.extend(tokens(s))
    return out


class Lock:
    def __init__(self, cfg=None, plugin_root=PLUGIN_ROOT, data_root=None, project=None):
        self.settings = (cfg or {}).get("lock_settings", True) is not False
        self.roots = root_forms(plugin_root)
        data_root = data_root or working_copy.data_dir()      # the working copy the skills run is locked the same way
        if data_root:
            self.roots |= root_forms(data_root)
        self.places = {resolve(r, None) for r in self.roots}
        self.places |= {real(p) for p in self.places}
        self.files = {p + "/" + f for p in self.places for f in SAFEGUARDS}
        # the folders that hold them, removed whole (rm -rf of the plugin folder or its hooks): those would take every
        # guard with them; only these, not their parents
        self.holders = {p + d for p in self.places for d in ("", "/hooks")}

    def in_protected(self, p, whole=True):
        """True when the full path p is a guard switch, inside a project's settings or hooks, or (whole) a plugin folder
        that holds a guard switch; a path that cannot be known is not."""
        if p is None:
            return False
        for c in {p, real(p)} if re.match(r"^[a-z]:/", p) else {p}:
            if self.settings and SETTINGS.search(c):
                return True
            if c in self.files or (whole and c in self.holders):
                return True
        return False

    def protected_path(self, path, here=None):
        """For one path (a file tool's, a script's): resolved, else judged by its words."""
        r = resolve(path, here)
        return self.in_protected(r) if r is not None else self.protected(path, here)

    def protected(self, text, here=None):
        """True when a text (a command part, a script) names a safeguard: the settings or the plugin's folders by
        name, or a path word that resolves (from the folder here) into one; a roadmap path that cannot be resolved is."""
        raw = str(text or "").replace("\x01", "\\ ")
        t = norm(raw.replace("\\ ", " "))
        if self.settings and SETTINGS.search(t):
            return True
        if any(re.search(re.escape(r + "/" + f) + r"""([\s"';|&)]|$)""", t) for r in self.roots for f in SAFEGUARDS):
            return True
        for tok in tokens(norm(raw.replace("\\ ", "\x01"))):
            if "/" not in tok and (here is None or tok.strip("\"'") in (".", "..")):
                continue                                      # a bare word is a path only read from a known folder
            r = resolve(tok, here)
            if r is not None and self.in_protected(r):
                return True
        return False

    def names_safeguard(self, text):
        """True when a text names a guard switch by its path (read where the folder cannot be worked out)."""
        t = norm(text)
        if self.settings and SETTINGS.search(t):
            return True
        return any(re.search(r"(^|/)hooks/" + re.escape(n) + r"""([\s"';|&)]|$)""", t) for n in SAFE_NAMES)

    def git_touches(self, shell, here):
        """True when a git command that changes files names a safeguard path. The repository it works in (-C, or the
        folder it runs in) is not itself a safeguard, so a merge or checkout in the plugin's repo goes through."""
        words = [w.strip("\"'").replace("\x01", " ") for w in re.findall(r"\"[^\"]*\"|'[^']*'|\S+", norm(shell).lstrip(" ("))]
        i, base = 1, here
        while i < len(words) and words[i].startswith("-"):
            if words[i] in ("-c", "--git-dir", "--work-tree") and i + 1 < len(words):
                if words[i] == "-c" and "=" not in words[i + 1]:       # -C <folder> (the words are lower case here)
                    base = resolve(words[i + 1], here)
                i += 2
                continue
            i += 1
        if i >= len(words) or words[i] not in GIT_CHANGES:
            return False
        for tok in words[i + 1:]:
            if tok.startswith("-") or not ("/" in tok or tok.startswith(".")):
                continue
            r = resolve(tok, base)
            if (r is not None and self.in_protected(r, whole=False)) or (r is None and self.names_safeguard(tok)):
                return True
        return False

    def plugin_test(self, path):
        """True for a test file (test_*.py, or anything in a tests folder): tests work on throwaway copies and name
        the safeguards on purpose, so running one is never a change to the safeguards (Kevin 11/25/26)."""
        p = norm(path)
        name = p.rsplit("/", 1)[-1]
        return (name.startswith("test_") and name.endswith(".py")) or "/tests/" in p

    def own_setup(self, cmd):
        """True for a plain run of the plugin's own setup script: one command, nothing chained or redirected."""
        if CHAINS.search(cmd):
            return False
        t = norm(cmd)
        return any(re.match(r"""^\s*["']?[^"'\s]*(python[\d.]*|py)(\.exe)?["']?\s+["']?""" + re.escape(r + "/scripts/" + SETUP_SCRIPT) + r"""["']?(\s|$)""", t)
                   for r in self.roots)

    def check_command(self, cmd, cwd):
        if self.own_setup(cmd):
            return None
        views = [view(p, own, dyn) for p, own, dyn in pieces(cmd)]
        refusal = "a command that changes the guardrails themselves (a project's settings or hooks, or the plugin's hooks.json or this lock)"
        start = resolve(cwd, None)
        here, seen = start, {start}
        for v in views:
            if CD.match(v["shell"]):
                to = None if v["dynamic"] or v["shell"].lstrip().startswith("(") else CD_TO.match(v["shell"])
                here = resolve(to.group(5), here) if to else None   # a folder change it cannot read: folder unknown
                seen.add(here)
                continue
            if POPD.match(v["shell"]) or (v["dynamic"] and CD_ANY.search(v["shell"])):
                here = None                                   # back to a folder it did not follow, or a change built while running
                seen.add(here)
                continue
            if GIT.match(v["shell"]) and not v["dynamic"] and not v["own"] \
                    and "|" not in QUOTED.sub('""', v["shell"]) and not REDIRECT.search(QUOTED.sub('""', v["shell"])):
                if self.git_touches(v["shell"], here):
                    return refusal
                continue
            hard, redir = write_kinds(v["all"], v["redirect"])
            if not (hard or redir):
                continue
            if not hard and not any(REDIRECT.search(QUOTED.sub('""', b)) for k, b in v["own"] if k != "code"):
                # the only write is the shell's own redirect: judge where it goes
                goes = [resolve(t, here) for t in redirect_targets(v["shell"])]
                if any(g is not None and self.in_protected(g) for g in goes):
                    return refusal
                if goes and all(g is not None for g in goes):
                    continue
            if (here is None and self.names_safeguard(v["targets"])) or self.protected(v["targets"], here):
                return refusal                                # a folder it cannot follow is judged by the paths the part gives
        for v in views:
            if v["reads"]:
                continue                                      # cat, grep, sed -n and the like read a script; they do not run it
            for path in scripts_run(v["run"], cwd):
                if self.protected_path(path) or self.plugin_test(path):
                    continue                                  # the safeguards' own scripts and the plugin's tests are run, not changed
                with open(path, encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
                if self.protected(code_targets(text), start):
                    return "a script (" + os.path.basename(path) + ") that changes the guardrails themselves"
        return None

    def decide(self, data):
        tool = data.get("tool_name") or ""
        ti = data.get("tool_input") or {}
        cwd = data.get("cwd") or "."
        if tool in ("Bash", "PowerShell"):
            return self.check_command(ti.get("command") or "", cwd)
        if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
            path = ti.get("file_path") or ti.get("notebook_path") or ""
            if self.protected_path(os.path.join(cwd, path)):
                return "a change to the roadmap safeguards (" + path + ")"
        return None


def nested(t):
    """The code another shell is handed in quotes (sh -c '...', cmd /c "...", iex "...")."""
    return [m.group("s")[1:-1] for m in NESTED.finditer(t)]


def write_kinds(text, shell=None):
    """(hard, redirect): hard when the text has a writing command, sed's w, inline code that writes or starts
    something, or a write in code handed to another shell; redirect when the shell part (shell, default the whole
    text) has a redirect outside quotes."""
    t = norm(text)
    inner = nested(t)
    hard = bool(WRITES.search(t) or SED_W.search(t) or (INLINE.search(t) and RISKY_INLINE.search(t))
                or any(WRITES.search(" " + s) or REDIRECT.search(s) for s in inner))
    redir = bool(REDIRECT.search(QUOTED.sub('""', norm(text if shell is None else shell))))
    return hard, redir


def writes(text, shell=None):
    """True when a command (or a script's text) can change files. Reading (cat, type, Get-Content, python that only
    reads) is not."""
    hard, redir = write_kinds(text, shell)
    return hard or redir


def redirect_targets(shell):
    """Where each redirect outside quotes in a shell part writes, as written; None for one with no readable target."""
    masked = QUOTED.sub(lambda q: "_" * len(q.group()), shell)
    out = []
    for m in REDIRECT.finditer(masked):
        t = TARGET.match(shell, m.end())
        out.append(t.group(1) if t else None)
    return [t for t in out] if out else [None]


def starts(code):
    """True when code an interpreter runs can start another program or the setup script; words inside its own string
    literals (source text it is editing, say) do not count."""
    return bool(STARTS.search(STRINGS.sub('""', code)))


def heredocs(t):
    """Takes each here-document body out of the command, leaving a mark on the line that opens it. Returns the command
    without the bodies and {mark: (kind, body)}: kind "code" when python or the like runs it, "shell" when a shell
    does, else "data". A PowerShell here-string (@' ... '@ or @" ... "@, a commit message say) is text the same way: it
    is taken out whole and left as an empty string with its mark, "shell" only when it is piped to iex or a shell."""
    bodies = {}

    def here_string(m):
        mark = "\x00" + str(len(bodies)) + "\x00"
        bodies[mark] = ("shell" if PS_RUNS.match(t, m.end()) else "data", m.group(2))
        return '""' + mark
    t = PS_HERE.sub(here_string, t)
    lines, out, i = t.split("\n"), [], 0
    while i < len(lines):
        line = lines[i]
        i += 1
        masked = QUOTED.sub(lambda q: "_" * len(q.group()), line)
        for at in re.finditer("<<", masked):
            m = HEREDOC.match(line, at.start())
            if not m:
                continue
            end = next((k for k in range(i, len(lines)) if lines[k].strip() == m.group(2)), None)
            if end is None:
                continue                                      # no closing line: not a here-document
            last = LAST.split(line[:at.start()])[-1]
            kind = "code" if CODE_IN.match(last) else "shell" if SHELL_IN.match(last) else "data"
            mark = "\x00" + str(len(bodies)) + "\x00"
            bodies[mark] = (kind, "\n".join(lines[i:end]))
            line += mark
            i = end + 1
        out.append(line)
    return "\n".join(out), bodies


def fill(p, known):
    """p with each plainly set variable filled in; a variable set more than once gives one line per value (at most 8)."""
    outs = [p]
    for name in dict.fromkeys(m.group(1) for m in VAR.finditer(p)):
        vals = known.get(name)
        if vals:
            one = re.compile(r"\$\{?" + re.escape(name) + r"\}?(?!\w)")
            outs = [one.sub(lambda _m, v=v: v, o) for o in outs for v in vals][:8]
    return "\n".join(outs)


def pieces(cmd):
    """The command cut into the parts a shell runs one after another (at ; && || and new lines outside quotes): [(text,
    here-documents it opens, dynamic)]. Plainly set variables are filled in; a variable also set in a way that cannot be
    read (from $(...), a loop, read) stays unfilled. dynamic is True for a part that still builds text while running
    ($(...), backticks, an unfilled variable, xargs, eval); only that part is judged the strict way."""
    # an escaped space (Git Bash "Plugin\ repo") is held as \x01 so the path stays one word
    t, bodies = heredocs(norm(cmd.replace("\\\r\n", " ").replace("\\\n", " ").replace("\\ ", "\x01")))
    cuts, start = [], 0
    for m in SEP.finditer(t):
        if m.group(1):
            cuts.append(t[start:m.start()])
            start = m.end()
    cuts.append(t[start:])
    out, known, unknown = [], {}, set()
    for p in cuts:
        own = [bodies[k] for k in MARK.findall(p)]
        p = MARK.sub("", p)
        a = ASSIGN.match(p)
        if a:
            name = a.group(2) or a.group(4)
            if name not in unknown:
                known.setdefault(name, []).append((a.group(3) or a.group(5)).strip("\"'"))
            continue
        for m in SETS.finditer(p):                            # set some other way: its value cannot be read
            name = next(g for g in m.groups()[1:] if g)
            unknown.add(name)
            known.pop(name, None)
        p = fill(p, known)
        dynamic = bool(DYNAMIC.search(p)) or any(k == "shell" and DYNAMIC.search(b) for k, b in own)
        if p.strip() or own:
            out.append((p, own, dynamic))
    return out


def view(shell, own, dynamic):
    """One command part as the checks see it: all (every word, for writes), redirect (what a shell reads for > and >>),
    run (what may be run: inline code that cannot start anything is left out, since paths in it are only read) and
    reads (a part made only of reading commands such as cat, grep or sed -n, which runs nothing)."""
    run = CODE_ARG.sub(lambda m: m.group(1) + (m.group(7) if starts(m.group(7)[1:-1]) else '""'), shell)
    run = "\n".join([run] + [b for k, b in own if k != "code" or starts(b)])
    stages = QUOTED.sub('""', shell).split("|")
    return {"shell": shell, "own": own, "dynamic": dynamic, "run": run, "all": "\n".join([shell] + [b for _, b in own]),
            "targets": target_text(shell, own),
            "redirect": "\n".join([shell] + [b for k, b in own if k != "code"]),
            "reads": not dynamic and not own and all(READS.match(s) for s in stages)}


# a script counts as run only when a part starts with an interpreter or with the script itself; a .py name handed to
# git add, cp or an editor is a file name, not a run (Kevin 11/25/26: committing the plugin's own files is ordinary work)
RUNNER = re.compile(r"""^\s*\(?\s*(&\s*)?["']?([^\s"']*[/\\])?(python[\d.]*|py|pythonw|node|perl|ruby|bash|sh|zsh|dash|ksh|"""
                    r"""powershell|pwsh|cmd|uv|uvx)(\.exe)?["']?(\s|$)|^\s*(source|\.)\s|"""
                    r"""^\s*\(?\s*(&\s*)?["']?[^\s"']*\.(py|pyw|ps1|sh|bat|cmd)["']?(\s|$)""", re.I)


def scripts_run(cmd, cwd):
    for line in cmd.replace("\x01", " ").split("\n"):
        for seg in line.split("|"):
            if not RUNNER.match(seg):
                continue
            for raw in SCRIPT.findall(seg):
                path = os.path.join(cwd, raw.strip("\"'"))
                if os.path.isfile(path) and os.path.getsize(path) < 2_000_000:
                    yield path


def note_setup_session(data, project, now=None):
    """When a session itself (not a helper) runs the plugin's setup script, note its id for the script to read."""
    if data.get("tool_name") not in ("Bash", "PowerShell") or data.get("agent_id") or data.get("agent_type"):
        return False
    cmd = str((data.get("tool_input") or {}).get("command") or "")
    if SETUP_SCRIPT not in cmd or not data.get("session_id"):
        return False
    if OFF.search(cmd):
        return False                                          # turning the roadmap off moves the folder; it must not make one first
    if UPDATE.search(cmd) and not os.path.isfile(rb.config_path(project)):
        return False                                          # update in a project that is not set up changes nothing at all
    rb.save_json({"session_id": data["session_id"], "time": time.time() if now is None else now},
                 os.path.join(project, ".claude", "roadmap", "seen.json"))
    return True


def main(data):
    try:
        working_copy.sync()                                   # the copy the command is about to run is the plugin's own
    except Exception:
        pass
    project = rb.project_dir(data)
    note_setup_session(data, project)
    cfg_file = rb.config_path(project)
    if not os.path.isfile(cfg_file):
        return None                                           # not set up here: nothing to protect
    return Lock(rb.load_json(cfg_file, {}), project=project).decide(data)


if __name__ == "__main__":
    try:
        why = main(json.load(sys.stdin))
    except Exception as e:
        # Kevin 11/25/26: guards stop only really bad things. A fault in this check is not one: the call goes on, and
        # the fault is shown (exit 1: a hook error the person sees, which does not stop the call) so it gets fixed.
        print("The guardrail lock could not judge this command and let it through; this is a fault to fix: " + repr(e),
              file=sys.stderr)
        sys.exit(1)
    if why:
        print("Refused: this is " + why + ". Only the user changes these, by hand or by running /assistant:roadmap-setup.", file=sys.stderr)
        sys.exit(2)
    sys.exit(0)
