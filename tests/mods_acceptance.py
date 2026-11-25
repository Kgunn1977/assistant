r"""Acceptance of mods (System\live\mods.py): an owner's change kept apart from the program, taking its place where it
applies. On a scratch copy laid down from this plugin with a made-up mod, every place the program asks a mod is tried,
and the program's own files still match the plugin, so an update asks nothing about the owner's change.
No Claude run is made; nothing outside the scratch folder changes.

    python tests\mods_acceptance.py [<a mod folder to try as well>]
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

MOD_JSON = {"name": "tally", "title": "Tally cards", "on": True, "card_prefixes": ["live:tally-"], "pass_seconds": 1,
            "chat_tools": {"allow": ["mcp__claude_ai_Tally__tally_read"], "deny": ["mcp__claude_ai_Tally__tally_pay"]},
            "chat_actions": ["tally_count"],
            "settings": {"title": "Tally", "fields": [{"id": "on", "label": "Count on its own", "control": "toggle", "explain": "Counts without asking."},
                                                       {"id": "limit", "label": "Most a day", "control": "text"}]},
            "loosens": [{"rule": "B9", "yes": "Test owner, 11/17/26: yes", "what": "The chat may count."}],
            "hold_reasons": {"room": "Tally held a room message."},
            "page": {"id": "tally", "title": "Tally", "script": "page.js"}}
MOD_PY = r'''
import common, items
def pass_step(pass_id):
    items.upsert("live:tally-1", pass_id, kind="question", area="Tally", state="question", status=None, title="Count which?",
                 detail="d", asks=["Which?"], source_who="Tally", source_when=common.now())
    return "tally: one card"
def choices(item):
    if item.get("source_key") == "live:tally-3":         # an add-on's own choice dict, with a meaning word of its own
        return [{"label": "Green", "text": "Green", "meaning": "go"}, "Grey"]
    return ["Red", "Blue"]
def answer(item, rec, on_update=None):
    t = (rec.get("text") or "").strip()
    if t not in ("Red", "Blue", "Green"):
        return None
    return {"said": "Counted " + t + ".", "fields": {"state": "done", "status": "Counted " + t}}
def chat_action(action, when):
    return "Counted " + str(action.get("n"))
def hold(message):
    return "room" if message.get("channel") == "tally" and not message.get("named") else None
def door(route, method, query, body):
    if route == "count":
        return 200, {"ok": True, "method": method, "n": (body or {}).get("n")}
    return 404, {"error": "no"}
def check_settings(v):
    if "limit" in v and not str(v["limit"]).isdigit():
        raise ValueError("Most a day is a number.")
    return v
'''
RULES = {"rules": [{"id": "T1", "guard": "b", "says": "Tally only counts."}],
         "loosens": {"B9": "The chat box acts only through its ACTION lines, and may count with the Tally mod."}}

INSIDE = r'''
import json, os, sys
sys.path.insert(0, sys.argv[1])
import common, mods, items, answers, think, settings_page, settings_data, chat, rebuild
out = {}
items.ensure()
lines, bad = mods.pass_steps("t1")
out["pass: the mod's step runs"] = [lines, bad]
out["pass: each mod's run is logged"] = "tally: ran" in open(os.path.join(common.LOGS, "mods.log"), encoding="utf-8").read()
card = items.rows("source_key='live:tally-1'")[0]
items.export("t1")                  # on the page, as each pass leaves it
out["cards: the mod owns its card and gives its buttons"] = [mods.owns(card), items.finish(dict(card)).get("choices")]
got = answers.act_on_answer({"id": card["id"], "action": "answer", "text": "Blue", "at": common.now().isoformat(timespec="seconds"), "device": "t"})
after = items.rows("id=?", (card["id"],))[0]
out["answers: a press on its card is the mod's"] = [got.get("result"), after["state"], after["status"]]
# a press as the page sends it now (its button id and meaning beside its words) still reaches the mod, never refused first
items.upsert("live:tally-3", "t1", kind="question", area="Tally", state="question", status=None, title="Count which colour?",
             detail="d", asks=["Which?"], source_who="Tally", source_when=common.now())
items.export("t1")
c3 = items.rows("source_key='live:tally-3'")[0]
shown = next(i for i in common.read_json(common.ITEMS_JSON, {})["items"] if i["id"] == c3["id"])
got3 = answers.act_on_answer({"id": c3["id"], "action": "answer", "text": "Green", "label": "Green", "button": "q1-1",
                              "meaning": shown["choices"][0].get("meaning") or "other", "at": common.now().isoformat(timespec="seconds"), "device": "t"})
after3 = items.rows("id=?", (c3["id"],))[0]
out["answers: a page press with its button and meaning reaches the mod"] = [shown["choices"], got3.get("result"), got3.get("duplicate"),
                                                                           after3["state"], after3["status"]]
items.upsert("live:tally-2", "t1", kind="question", area="Tally", state="question", title="Another", detail="d", asks=["?"],
             source_who="Tally", source_when=common.now(), source_messages=json.dumps(["1"]))
seen = []
think._write_batch = lambda work, loose, new_set, goals: (seen.extend(r["id"] for r in work), (True, ""))[1]
iid2 = items.rows("source_key='live:tally-2'")[0]["id"]
think.write_items([], [], {iid2})
out["card writer: leaves the mod's cards alone"] = iid2 in seen
allow, deny = mods.chat_tools()
out["chat: only the mod's named tools"] = [allow, deny]
out["chat: the mod's words and action"] = ["Tally" in chat.instructions_for_test() if hasattr(chat, "instructions_for_test") else True,
                                          chat._do({"type": "tally_count", "n": 3}, "w", common.now(), 0)[1]]
defs = settings_data.defs()
out["settings: the mod's section is drawn"] = [any(g["id"] == "mod:tally" for g in defs["groups"]),
                                              [[x["id"], x.get("explain")] for x in defs["settings"] if x["group"] == "mod:tally"]]       # its own (i) words, or none
out["settings: checked by the mod, saved to its part"] = [settings_page.save({"settings": {"group": "mod:tally", "values": {"limit": "x"}}})[0],
                                                         settings_page.save({"settings": {"group": "mod:tally", "values": {"limit": "5"}}})[0],
                                                         common.settings().get("tally")]
rb = common.rulebook()
rules, _w, skipped = rb.book()
out["rule book: its rule added, B9 loosened with the recorded yes"] = ["tally.T1" in rules, rules["B9"]["says"].endswith("Tally mod."),
                                                                     rules["B9"].get("loosened_with")]
import held
out["filters: a mod holds its own messages, with its own reason"] = [mods.hold({"channel": "tally", "named": False}), mods.hold({"channel": "email"}),
                                                                   held.why(None, "mod:tally:room")]
out["page: the mod's part, its files and its door"] = [[[p["mod"], p["id"], p["title"], p["script"]] for p in mods.page_parts()],
    bool(mods.page_file("tally", "page.js")), mods.page_file("tally", "mod.py"), mods.page_file("tally", "../mod.json"),
    mods.door("tally", "count", "GET", {}, None), mods.door("nobody", "count", "GET", {}, None)]
out["page: its part placed at the bottom, last"] = settings_page._order({})["bottom"][-1:]      # Held back is a kind of card now (aa38abd), no longer a part
import hashlib, secrets, time, urllib.request, urllib.error
sys.path.insert(0, os.path.join(os.path.dirname(sys.argv[1]), "live_page"))
import local_site
srv = local_site.start(); port = srv.server_address[1]
tok, csrf = secrets.token_urlsafe(48), secrets.token_hex(32)
local_site._save("sessions", {hashlib.sha256(tok.encode()).hexdigest(): {"made": int(time.time()), "seen": int(time.time()), "exp": int(time.time()) + 3600, "len": 3600, "csrf": csrf}})
def go(path, body=None, signed=True, check=True):
    h = {"Host": f"127.0.0.1:{port}", "Content-Type": "application/json"}
    if signed: h["Cookie"] = f"{local_site.cookie_name()}={tok}"
    if body is not None and check: h["X-Brief-Csrf"] = csrf; h["Origin"] = f"http://127.0.0.1:{port}"
    rq = urllib.request.Request(f"http://127.0.0.1:{port}/{path}", data=None if body is None else json.dumps(body).encode(), method="GET" if body is None else "POST", headers=h)
    try:
        with urllib.request.urlopen(rq, timeout=30) as r:
            return r.status, r.headers.get("Content-Type", "").split(";")[0]
    except urllib.error.HTTPError as e:
        return e.code, ""
out["page server: the mod's file and door, signed in only, a press with its check only"] = [go("s/mod/tally/page.js"), go("s/mod/tally/mod.py")[0],
    go("api/mod/tally/count")[0], go("api/mod/tally/count", signed=False)[0], go("api/mod/tally/count", {"n": 2})[0],
    go("api/mod/tally/count", {"n": 2}, check=False)[0], go("api/mod/nobody/count")[0]]
srv.shutdown()
print(json.dumps(out, default=str))
'''

NO_YES = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
import common
rules, _w, skipped = common.rulebook().book()
print(json.dumps([rules["B9"]["says"], [s for s in skipped if "B9" in s]]))
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="mods-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("assistant_copy_mods", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    a = os.path.join(data, "scripts", "assistant.py")

    def inside(code):
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", code, live], capture_output=True, text=True, env=env, timeout=300)
        return json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {"error": r.stderr[-600:]}

    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, a, "lay-down", "--port", "47901", "--sending", "no", "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, os.path.join(live, "pass.py")], capture_output=True, text=True, env=env, timeout=600)
        check("a first pass makes the database", r.returncode, 0)
        md = os.path.join(home, "mods", "tally")
        os.makedirs(md)
        json.dump(MOD_JSON, open(os.path.join(md, "mod.json"), "w", encoding="utf-8"))
        open(os.path.join(md, "mod.py"), "w", encoding="utf-8").write(MOD_PY)
        json.dump(RULES, open(os.path.join(md, "rules.json"), "w", encoding="utf-8"))
        open(os.path.join(md, "chat.md"), "w", encoding="utf-8").write("Tally: count when asked.")
        open(os.path.join(md, "page.js"), "w", encoding="utf-8").write("window.ASSISTANT_PAGE.part({id: 'tally', title: 'Tally', render: function () {}});")
        got = inside(INSIDE)
        if "error" in got:
            check("the checks ran", got["error"], "")
        check("pass: the mod's step runs", got.get("pass: the mod's step runs"), [["tally: one card"], []])
        check("filters: a mod holds its own messages, with its own reason", got.get("filters: a mod holds its own messages, with its own reason"),
              ["mod:tally:room", None, ["Tally held a room message.", "setting"]])
        check("page: the mod's part, its files and its door", got.get("page: the mod's part, its files and its door"),
              [[["tally", "tally", "Tally", "page.js"]], True, None, None, [200, {"ok": True, "method": "GET", "n": None}], None])
        check("page: its part placed at the bottom, last", got.get("page: its part placed at the bottom, last"), ["tally"])
        check("page server: the mod's file and door, signed in only, a press with its check only",
              got.get("page server: the mod's file and door, signed in only, a press with its check only"),
              [[200, "text/javascript"], 404, 200, 401, 200, 403, 404])
        check("pass: each mod's run is logged", got.get("pass: each mod's run is logged"), True)
        check("cards: the mod owns its card and gives its buttons", got.get("cards: the mod owns its card and gives its buttons"), [True, ["Red", "Blue"]])
        check("answers: a press on its card is the mod's", got.get("answers: a press on its card is the mod's"), ["Counted Blue.", "done", "Counted Blue"])
        check("answers: a page press with its button and meaning reaches the mod",
              got.get("answers: a page press with its button and meaning reaches the mod"),
              [[{"label": "Green", "text": "Green"}, "Grey"], "Counted Green.", None, "done", "Counted Green"])
        check("card writer: leaves the mod's cards alone", got.get("card writer: leaves the mod's cards alone"), False)
        check("chat: only the mod's named tools", got.get("chat: only the mod's named tools"),
              [["mcp__claude_ai_Tally__tally_read"], ["mcp__claude_ai_Tally__tally_pay"]])
        check("chat: the mod's action", (got.get("chat: the mod's words and action") or [None, None])[1], "Counted 3")
        check("settings: the mod's section is drawn", got.get("settings: the mod's section is drawn"), [True, [["on", "Counts without asking."], ["limit", ""], ["loosens-B9", None]]])
        check("settings: checked by the mod, saved to its part", got.get("settings: checked by the mod, saved to its part"), [False, True, {"limit": "5"}])
        check("rule book: its rule added, B9 loosened with the recorded yes",
              got.get("rule book: its rule added, B9 loosened with the recorded yes"), [True, True, "Test owner, 11/17/26: yes"])
        # without the owner's yes, the mod cannot loosen a rule
        m = dict(MOD_JSON, loosens=[])
        json.dump(m, open(os.path.join(md, "mod.json"), "w", encoding="utf-8"))
        says, skipped = inside(NO_YES)
        check("rule book: no loosening without the owner's recorded yes", ("Tally" in says, bool(skipped)), (False, True))
        # the chat's run, with a mod naming tools: connectors load, and only the named tools may run
        src = open(os.path.join(live, "chat.py"), encoding="utf-8").read()
        check("chat: with a mod's tools the run allows only those, in dontAsk mode", ('"--permission-mode", "dontAsk"' in src,
              '"--strict-mcp-config"' in src), (True, True))
        # the program's own files are untouched: an update plan names no owner change
        plan = json.loads(subprocess.run([sys.executable, a, "update-plan", "--root", root], capture_output=True, text=True).stdout or "{}")
        check("the program still matches the plugin: no owner change in the update plan", (plan.get("keep"), plan.get("yours"), plan.get("conflict")), (0, [], []))
        if len(sys.argv) > 1:          # a real mod as well (not kept in this repository): it loads and its places answer
            shutil.rmtree(md)
            shutil.copytree(sys.argv[1], os.path.join(home, "mods", os.path.basename(sys.argv[1].rstrip("\\/"))))
            r = subprocess.run([sys.executable, "-X", "utf8", "-c", "import sys, json; sys.path.insert(0, sys.argv[1]); import mods, common; "
                                "print(json.dumps([[m['name'], mod is not None] for m, mod in mods.on()] + [list(mods.chat_tools()[0][:1])] + "
                                "[sorted(k for k in common.rulebook().book()[0] if '.' in k)] + [common.rulebook().book()[0]['B9'].get('loosened_with') is not None]))",
                                live], capture_output=True, text=True, env=env)
            check("a real mod loads, names its tools, adds its rule and loosens B9 with the yes", r.stdout.strip()[:300] != "" and "true" in r.stdout, True)
            print("real mod:", r.stdout.strip()[:400], r.stderr.strip()[-300:])
        subprocess.run([sys.executable, a, "uninstall", "--remove-data", "--root", root], capture_output=True, text=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got_, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got_!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
