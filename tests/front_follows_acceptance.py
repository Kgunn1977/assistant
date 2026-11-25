r"""Acceptance (quick): a card's front follows the conversation. Words typed on a card go the normal way (the card's answer,
the chat, the card's record); the reply's card action (in the same Claude call: a stand-in here, no Claude run) rewrites the
front: the recommendation, the why, the first question and its choices with the recommended one first, while the title stays
and the old recommendation's question and choices are gone. The reply itself is in the card's conversation. On a scratch copy
laid down from this plugin, with made-up names.

    python tests\front_follows_acceptance.py
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
import json, os, sys
live = sys.argv[1]
sys.path.insert(0, live); sys.path.insert(0, os.path.join(live, "core")); os.chdir(live)
import common, items, answers, chat, card
iid, _ = items.upsert("live:test-window", "t", kind="question", area="Work", state="question",
    title="The window install at 12 Elm Street needs a date",
    recommended="Ask Pat whether the installer's scheduler called with a time.",
    why="The installer has not confirmed a date for the windows.", asks=["Ask Pat about the scheduler's call?"])
items.update(iid, "t", **items.card_extras({"state": "question", "asks": ["Ask Pat about the scheduler's call?"],
                                            "choices": ["Ask Pat", "Wait for the installer"], "recommended_choice": "Ask Pat"}))
items.export("t")
REPLY = ("I searched your mail and saved texts since 10/28 for an install time from Pat or the installer and found none.\n"
         'ACTION: {"type": "card", "state": "question", "settled": [], "card": {'
         '"why": "You think Pat gave a time, but none is in mail or texts since 10/28.", '
         '"recommended": "Ask Pat directly for the install time; it is not in your mail or saved texts.", '
         '"asks": ["Text Pat for the install time?"], "choices": ["Text Pat", "Call Pat"], "recommended_choice": "Text Pat"}, '
         '"ask": null, "waiting_on": null, "next_check": null}')
chat._run = lambda words, instructions, sess: (REPLY, "", 1.0, {})
out = answers.act_on_answer({"id": iid, "action": "answer", "text": "I think Pat gave me an install time already."})
answers.wait_landed(30)
snap = common.read_json(common.ITEMS_JSON, {}).get("items") or []
it = next(i for i in snap if i.get("id") == iid)
print(json.dumps({"ok": out.get("ok"), "title": it.get("title"), "recommended": it.get("recommended"), "why": it.get("why"),
                  "asks": it.get("asks"), "choices": it.get("choices"), "questions": it.get("questions"), "state": it.get("state"),
                  "answer": it.get("answer"), "conversation": (it.get("assistant_did") or "").split("\n")[-1]}))
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="front-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("ac_front", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47935", "--sending", "no",
                            "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live], capture_output=True, text=True, env=env, timeout=600)
        o = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {"error": r.stderr[-1500:]}
        check("the reply went through the card's normal path", o.get("ok"), True)
        check("the recommendation follows the exchange", o.get("recommended"), "Ask Pat directly for the install time; it is not in your mail or saved texts.")
        check("the summary line follows the exchange", o.get("why"), "You think Pat gave a time, but none is in mail or texts since 10/28.")
        check("the question is the new recommended step; the old one is gone", o.get("asks"), ["Text Pat for the install time?"])
        labels = [(c.get("text") if isinstance(c, dict) else c, bool(isinstance(c, dict) and c.get("recommended"))) for c in o.get("choices") or []]
        check("its choices: the recommended action first and marked; the old ones gone", labels, [("Text Pat", True), ("Call Pat", False)])
        check("the title stays; the card stays open, with nothing left waiting", (o.get("title"), o.get("state"), o.get("answer")),
              ("The window install at 12 Elm Street needs a date", "question", None))
        check("the full reply is in the card's conversation", "found none" in str(o.get("conversation")), True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
