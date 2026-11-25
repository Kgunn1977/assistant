r"""Acceptance: an edit made in the plugin's folder reaches a laid-down copy through the update, with the version
number unchanged. A scratch copy of the plugin, its working copy and a scratch home; nothing outside them changes.

    python tests\local_edit_acceptance.py
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)                                      # the plugin: this repository
results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="local-edit-")
    plug, data, root = os.path.join(tmp, "plugin"), os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home = os.path.join(root, "Live")
    shutil.copytree(PKG, plug, ignore=shutil.ignore_patterns(".git", ".claude", "__pycache__", "*.pyc", "tests"))
    spec = importlib.util.spec_from_file_location("assistant_copy_scratch", os.path.join(plug, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    a = os.path.join(data, "scripts", "assistant.py")

    def run(*args):
        r = subprocess.run([sys.executable, a, *args, "--root", root], capture_output=True, text=True)
        return r.returncode, (r.stdout + r.stderr).strip()

    try:
        check("working copy made", copier.sync(data), True)
        check("lay-down", run("lay-down", "--port", "47896", "--sending", "no")[0], 0)
        version = json.load(open(os.path.join(home, "personal", "install.json"), encoding="utf-8")).get("version")
        code, out = run("update-apply")
        check("nothing edited: nothing to update", (code, out.startswith("Nothing to update")), (0, True))
        # one engine file edited in the plugin's folder, version untouched
        rel = os.path.join("System", "live", "dates.py")
        with open(os.path.join(plug, "engine", rel), "a", encoding="utf-8") as f:
            f.write("\n# edited in the plugin's folder\n")
        check("the edit reaches the working copy at the next hook run", copier.sync(data), True)
        code, out = run("update-plan")
        plan = json.loads(out) if code == 0 else {}
        check("the plan takes that one file at the same version", (plan.get("from"), plan.get("to"), plan.get("take")),
              (version, version, 1))
        code, out = run("update-apply")
        check("the update goes through", code, 0)
        check("the edit is laid down", "edited in the plugin's folder" in open(os.path.join(root, rel), encoding="utf-8").read(), True)
        check("the version is unchanged",
              json.load(open(os.path.join(home, "personal", "install.json"), encoding="utf-8")).get("version"), version)
        code, out = run("update-apply")
        check("run again: nothing to update", (code, out.startswith("Nothing to update")), (0, True))
        run("uninstall", "--remove-data")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
