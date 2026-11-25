r"""Acceptance: an update that failed puts the program back even while the page's listener is running (it holds its own
folder, which Windows will not let be replaced), and the restore command does the same from an update's safety copy.
On a scratch copy laid down from this plugin. Nothing outside the scratch folder changes.

1. A stand-in listener runs from System\live_page and holds that folder; a failed update's leftovers sit in System. The
   restore stops the listener, deletes what the failed update put there (no To Delete folder), puts System and Shipped
   back from the safety copy, and no pass is run.
2. The update's own failure path puts back the same way (the same step), and it runs no pass.
3. With the rule book gone (System missing), the guard refuses only a send: the plugin's own helper and file work go
   through, and a command that sends is still refused.

    python tests\restore_acceptance.py
"""
import filecmp
import importlib.util
import json
import os
import shutil
import _cleanup  # noqa: E402  the scratch folder goes when the test ends
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
results = []

HOLDER = r'''
import os, sys, time
os.chdir(os.path.dirname(os.path.abspath(__file__)))
f = open("held.txt", "w"); f.write("held"); f.flush()
print("holding", flush=True)
time.sleep(600)
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def same_tree(a, b):
    cmp = filecmp.dircmp(a, b, ignore=["__pycache__"])
    if cmp.left_only or cmp.right_only or cmp.diff_files:
        return False
    return all(same_tree(os.path.join(a, d), os.path.join(b, d)) for d in cmp.common_dirs)


def main():
    tmp = tempfile.mkdtemp(prefix="restore-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, system = os.path.join(root, "Live"), os.path.join(root, "System")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("assistant_copy_restore", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    holder = None
    try:
        copier.sync(data)
        helper = os.path.join(data, "scripts", "assistant.py")
        r = subprocess.run([sys.executable, helper, "lay-down", "--port", "47925", "--sending", "no", "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, os.path.join(system, "live", "pass.py")], capture_output=True, text=True, env=env, timeout=600)
        check("a first pass", r.returncode, 0)
        aside = os.path.join(home, "Update copies", "2026-11-19", "update 0.1.3 124703")
        os.makedirs(aside)
        shutil.copytree(system, os.path.join(aside, "System"), ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(os.path.join(root, "Shipped"), os.path.join(aside, "Shipped"))
        # a failed update's state: a new file in System, a changed one, and the listener running from its own folder
        with open(os.path.join(system, "live", "from_the_failed_update.py"), "w") as f:
            f.write("# left by an update that failed\n")
        with open(os.path.join(system, "live", "common.py"), "a") as f:
            f.write("\n# changed by an update that failed\n")
        stand_in = os.path.join(system, "live_page", "listen_stand_in.py")
        with open(stand_in, "w") as f:
            f.write(HOLDER)
        holder = subprocess.Popen([sys.executable, stand_in], stdout=subprocess.PIPE, text=True,
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        check("the stand-in listener holds its folder", holder.stdout.readline().strip(), "holding")
        try:
            os.replace(system, system + ".try")
            os.replace(system + ".try", system)
            held = False
        except PermissionError:
            held = True
        check("Windows will not let a folder in use be moved (what made the old put-back fail)", held, True)
        # another program (not the assistant's, so never stopped) with its working folder inside System, as on the owner's home
        sitter = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"], cwd=os.path.join(system, "live"),
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

        # 1. the restore
        r = subprocess.run([sys.executable, helper, "restore", "--root", root, "--from", aside], capture_output=True, text=True, timeout=1200)
        check("1 the restore ends ok", (r.returncode, r.stdout[-600:] if r.returncode else ""), (0, ""))
        time.sleep(1)
        check("1 the listener was stopped", holder.poll() is not None, True)
        check("1 put back file by file while another program still sits in System", sitter.poll() is None, True)
        sitter.kill()
        check("1 System is the safety copy's, file for file", same_tree(os.path.join(aside, "System"), system), True)
        check("1 Shipped is the safety copy's", same_tree(os.path.join(aside, "Shipped"), os.path.join(root, "Shipped")), True)
        check("1 what the failed update put there is deleted outright, and no To Delete folder is made",
              (os.path.exists(os.path.join(system, "live", "from_the_failed_update.py")), os.path.exists(os.path.join(home, "To Delete"))),
              (False, False))
        check("1 the safety copy itself is untouched", os.path.isfile(os.path.join(aside, "System", "live", "pass.py")), True)
        check("1 no pass is run, and the restore says so", ("No pass was run" in r.stdout, "Check: " in r.stdout), (True, False))
        check("1 the database opens", "Database: opens" in r.stdout, True)

        # 2. the update's failure path uses the same put-back, and its check is the quick one
        src = open(os.path.join(PKG, "scripts", "assistant.py"), encoding="utf-8").read()
        body = src[src.index("def update_apply("):src.index("# --- uninstall")]
        check("2 a failed update puts back through the step that stops the listener first",
              ("put_back(c, aside)" in body, "_rm(dest)" in body), (True, False))
        check("2 the update runs no pass (the owner runs check-pass when wanted)", "check_pass(" in body, False)

        # 3. the guard with the rule book gone
        shutil.move(system, os.path.join(tmp, "System away"))
        guard = os.path.join(PKG, "hooks", "rulebook_guard.py")
        genv = dict(os.environ, CLAUDE_PLUGIN_DATA=data)

        def asks(cmd):
            payload = {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": tmp, "session_id": "t"}
            return subprocess.run([sys.executable, guard, "--root", root], input=json.dumps(payload), capture_output=True, text=True,
                                  env=genv).returncode
        own = f'python "{helper}" status --root "{root}"'
        check("3 no rule book: the plugin's own helper and file work go through; a command that sends is still refused",
              [asks(own), asks(f'echo made-up > "{os.path.join(tmp, "note.txt")}"'), asks('python engine/System/live/send.py')],
              [0, 0, 2])
    finally:
        if holder and holder.poll() is None:
            holder.kill()
        _cleanup.remove(tmp)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
