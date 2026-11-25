r"""Acceptance (quick): the plugin's working copy stays whole when several sessions' hooks bring it up to date at the same
moment (one refresh at a time), and a copy that lost files is made again though its stamp says it is current. On a scratch
folder standing in for the plugin's data folder.

    python tests\working_copy_acceptance.py
"""
import filecmp
import os
import shutil
import _cleanup  # noqa: E402  the scratch folder goes when the test ends
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
results = []
RUN = ("import importlib.util, sys; s = importlib.util.spec_from_file_location('ac', sys.argv[1]); m = importlib.util.module_from_spec(s); "
       "s.loader.exec_module(m); m.sync(sys.argv[2])")


def whole(dest):
    def same(a, b):
        c = filecmp.dircmp(a, b, ignore=["__pycache__"])
        return not (c.left_only or c.right_only) and all(same(os.path.join(a, d), os.path.join(b, d)) for d in c.common_dirs)
    return os.path.isdir(os.path.join(dest, "engine")) and same(os.path.join(PKG, "engine"), os.path.join(dest, "engine"))


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="wcopy-")
    dest = os.path.join(tmp, "data")
    hook = os.path.join(PKG, "hooks", "assistant_copy.py")
    try:
        subprocess.run([sys.executable, "-c", RUN, hook, os.path.join(tmp, "first")], timeout=300)
        check("a first copy into a folder that does not exist yet is made whole", whole(os.path.join(tmp, "first")), True)
        os.makedirs(dest)
        procs = [subprocess.Popen([sys.executable, "-c", RUN, hook, dest]) for _ in range(4)]      # four sessions at once
        for p in procs:
            p.wait(timeout=300)
        subprocess.run([sys.executable, "-c", RUN, hook, dest], timeout=300)        # the next one finishes what a skipped one left
        check("four refreshes at the same moment leave the copy whole", whole(dest), True)
        check("no lock is left behind", os.path.exists(os.path.join(dest, "assistant-copy.lock")), False)
        os.remove(os.path.join(dest, "engine", "System", "live", "pass.py"))
        shutil.rmtree(os.path.join(dest, "engine", "System", "live_page"))
        subprocess.run([sys.executable, "-c", RUN, hook, dest], timeout=300)
        check("a copy that lost files is made again, though its stamp says it is current", whole(dest), True)
    finally:
        _cleanup.remove(tmp)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
