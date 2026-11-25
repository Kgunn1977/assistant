r"""Acceptance (quick): the mail step's slower work (changes made elsewhere, folders, the backfill) reports apart from reading
the new mail. On a scratch copy with two stand-in mailboxes (no real account): one reads its new mail and syncs fine, one reads
its new mail and its sync fails. The mail source is ok (the new mail was read), the sync is its own source with the failure's
reason in full, the pass's problems name that reason (not the progress lines before it), and an update's check would not count
the mail as lost.

    python tests\mail_sync_report_acceptance.py
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
results = []

INSIDE = r'''
import json, os, sys, types
live = sys.argv[1]
sys.path.insert(0, live); sys.path.insert(0, os.path.join(live, "core")); os.chdir(live)
import common, db, connections, gather
class Good:
    @staticmethod
    def gather(c, ctx): return "3 new"
    @staticmethod
    def sync(c, ctx, end): return "12 changed elsewhere, 50 stored emails read (more to read next pass)"
class Bad(Good):
    @staticmethod
    def sync(c, ctx, end): raise RuntimeError("the folder list answered 403: the mailbox's sign-in does not allow reading folders")
conns = [{"id": "c1", "type": "good", "kind": "email", "address": "pat@example.com"}, {"id": "c2", "type": "bad", "kind": "email", "address": "lee@example.com"}]
connections.listed = lambda kind=None, everything=False: [c for c in conns if kind in (None, c["kind"])]
connections.module = lambda t: {"good": Good, "bad": Bad}[t]
sys.path.insert(0, os.path.join(live, "connections"))
import run
gather.sources_on = lambda: [("email", 60)]
def run_script(path, *args, run_id=None, timeout=600):
    import io, contextlib
    buf = io.StringIO()
    sys.argv = ["run.py"] + [str(a) for a in args] + ["--run-id", run_id]
    with contextlib.redirect_stdout(buf):
        code = run.main()
    return code == 0, buf.getvalue()[-2000:]
gather.run_script = run_script
g = gather.gather("t-sync")
print(json.dumps({"sources": {k: v["status"] for k, v in g["sources"].items()}, "problems": g["problems"],
                  "summary": gather.summary(g)}, default=str))
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="syncrep-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("ac_syncrep", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47938", "--sending", "no",
                            "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live], capture_output=True, text=True, env=env, timeout=600)
        o = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {"error": r.stderr[-1500:]}
        s = o.get("sources") or {}
        check("the mail source is ok: the new mail was read", (s.get("email"), s.get("email:pat@example.com"), s.get("email:lee@example.com")), ("ok", "ok", "ok"))
        check("the slower work is its own source, marked as having trouble", s.get("email-sync"), "degraded")
        p = " ".join(o.get("problems") or [])
        check("the problem names the failure's reason in full, not the progress lines",
              ("403: the mailbox's sign-in does not allow reading folders" in p, "lee@example.com" in p, "stored emails read" in p), (True, True, False))
        check("the pass summary names the sync, not the mail", "PROBLEM email-sync" in str(o.get("summary")) and "PROBLEM email," not in str(o.get("summary")), True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
