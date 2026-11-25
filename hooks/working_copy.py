"""Keeps a working copy of the files a session runs or reads (the setup script, the manual, the agreement, the list of
changes, the page) in
the plugin's own data folder, which Claude Code names in CLAUDE_PLUGIN_DATA (<home>/.claude/plugins/data/<plugin>).
The skills name that copy, never the plugin's folder: a plugin added from a folder on the same PC is run where it sits,
and a project that keeps its sessions inside its own folder refuses a command that names such a place. Called by the
plugin's hooks, which already run before every message and every terminal command; a file is written only when it is
missing or differs from the plugin's own."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(HERE)
FILES = ("scripts/roadmap_setup.py", "hooks/roadmap_blocks.py", "page/roadmap.html",
         "reference/database.md", "reference/agreement.md", "reference/changes.md",
         "skills/roadmap-director/SKILL.md", "skills/roadmap-writer/SKILL.md",     # these two are there only so update can tell when they change
         "skills/roadmap-update/SKILL.md")                                       # read by a main session handed its step after an update


def data_dir():
    """The plugin's data folder, or None when Claude Code did not name one."""
    d = os.environ.get("CLAUDE_PLUGIN_DATA")
    return os.path.abspath(d) if d else None


def sync(dest=None, source=PLUGIN_ROOT):
    """Brings the working copy up to date. Returns the files written."""
    dest = dest or data_dir()
    if not dest or os.path.normcase(os.path.abspath(dest)) == os.path.normcase(os.path.abspath(source)):
        return []
    written = []
    for rel in FILES:
        with open(os.path.join(source, rel), "rb") as fh:
            want = fh.read()
        path = os.path.join(dest, rel)
        try:
            with open(path, "rb") as fh:
                if fh.read() == want:
                    continue
        except OSError:
            pass
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp" + str(os.getpid())
        with open(tmp, "wb") as fh:
            fh.write(want)
        os.replace(tmp, path)
        written.append(rel)
    return written
