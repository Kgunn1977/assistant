"""Before a file is deleted: is it still named by code in the repo or the working copy? Standard library only.

    inuse.users(path, roots) -> up to 5 files that name it (empty when nothing does)
    inuse.refuse_if_used(path, roots) -> raises InUse naming them, so the delete does not happen
"""
import os

TEXT = {".py", ".pyw", ".js", ".json", ".md", ".html", ".ps1", ".sql", ".sh", ".txt", ".css", ".php", ".cmd", ".bat"}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "Briefings", "Database", "worktrees"}
BIGGEST = 1_000_000


class InUse(Exception):
    pass


def default_roots():
    """The repo this code sits in (when it is one) and the working copy beside the data home."""
    here = os.path.dirname(os.path.abspath(__file__))
    roots, p = [], here
    for _ in range(8):
        if os.path.exists(os.path.join(p, ".git")) or os.path.isdir(os.path.join(p, ".claude-plugin")):
            roots.append(p)
            break
        p = os.path.dirname(p)
    try:
        import paths
        roots.append(os.path.join(paths.HOME, "System"))
    except Exception:  # noqa: BLE001  no data home known: the repo alone is checked
        pass
    return roots


def users(path, roots=None, most=5):
    name = os.path.basename(str(path).rstrip(os.sep + "/"))
    if not name:
        return []
    me, stem, found = os.path.normcase(os.path.abspath(path)), os.path.splitext(name)[0], []
    needles = [name.encode("utf-8", "ignore")] + ([stem.encode("utf-8", "ignore")] if os.path.splitext(name)[1] in (".py", ".pyw") and len(stem) > 3 else [])
    for root in (default_roots() if roots is None else roots):
        for d, dirs, files in os.walk(root):
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
            for f in files:
                p = os.path.join(d, f)
                if os.path.splitext(f)[1].lower() not in TEXT or os.path.normcase(os.path.abspath(p)) == me:
                    continue
                try:
                    if os.path.getsize(p) > BIGGEST:
                        continue
                    with open(p, "rb") as fh:
                        data = fh.read()
                except OSError:
                    continue
                if any(n in data for n in needles[:1]) or (len(needles) > 1 and (b"import " + needles[1] in data or b"from " + needles[1] in data)):
                    found.append(p)
                    if len(found) >= most:
                        return found
    return found


def refuse_if_used(path, roots=None):
    used = users(path, roots)
    if used:
        raise InUse(f"{os.path.basename(path)} is still named by other files ({', '.join(os.path.basename(u) for u in used)}), so it was not deleted.")
