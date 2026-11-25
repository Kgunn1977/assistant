r"""Acceptance: the Calendar part of Settings, in a scratch home (never the owner's). Three made-up calendars (Work, Family,
North Building) each with an event today: the setting is its own part named Calendar with the explanation, a save that unticks one
takes its events off Today at once, the owner's saved setting stays the same key (personal today_calendars), a calendar the
assistant does not know is refused, and the page carries the Choose calendars link (Today) and the Settings link (Calendar).

    python tests\calendar_settings_acceptance.py
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


INSIDE = r'''
import json, os, sys, datetime as dt
sys.path.insert(0, sys.argv[1])
import common, db, settings_page, settings_data, paths
db.init_schema()
json.dump({"owner": "Tester", "today_calendars": ["Work", "Family", "North Building"]}, open(paths.PERSONAL_JSON, "w"))
today = dt.date.today()
with db.transaction() as con:
    for i, (cal, t) in enumerate([("Work", "Standup"), ("Family", "Dentist"), ("North Building", "Boiler check")]):
        s = dt.datetime.combine(today, dt.time(9 + i, 0))
        con.execute("INSERT INTO calendar_events (event_id, calendar, summary, start_ts, end_ts, all_day, location, description, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (f"e{i}", cal, t, s, s + dt.timedelta(hours=1), False, "", "", s))
import items
items.write_today()
def titles():
    t = json.load(open(os.path.join(common.HOME, "today.json")))
    return sorted(e["title"] for d in t["days"] for e in d["events"])
out = {"before": titles()}
d = settings_data.defs()
x = [s for s in d["settings"] if s["id"] == "calendars"][0]
out["part"] = [x["group"], [g["label"] for g in d["groups"] if g["id"] == x["group"]], x["control"], sorted(c["value"] for c in x["choices"]), sorted(x["value"])]
out["explain"] = x["explain"]
out["watch_has_it"] = any(s["group"] == "watch" and s["id"] == "calendars" for s in d["settings"])
ok, line = settings_page.save({"settings": {"group": "calendar", "values": {"calendars": ["Work", "North Building"]}}})
out["saved"] = ok
out["after"] = titles()
out["key"] = json.load(open(paths.PERSONAL_JSON))["today_calendars"]
out["refused"] = settings_page.save({"settings": {"group": "calendar", "values": {"calendars": ["Nobody"]}}})[0]
out["old_group_refused"] = settings_page.save({"settings": {"group": "watch", "values": {"calendars": ["Work"]}}})[0]
print(json.dumps(out))
'''

if __name__ == "__main__":
    tmp = tempfile.mkdtemp(prefix="calset-")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=os.path.join(tmp, "Live"))
    os.makedirs(os.path.join(tmp, "Live", "personal"))
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, os.path.join(PKG, "engine", "System", "live")],
                       capture_output=True, text=True, env=env, timeout=120, encoding="utf-8")
    try:
        got = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        got = {}
        print(r.stdout[-800:], r.stderr[-800:])
    check("three calendars show before", got.get("before"), ["Boiler check", "Dentist", "Standup"])
    check("its own part, named Calendar, a tick list of the three", got.get("part"), ["calendar", ["Calendar"], "checks", ["Family", "North Building", "Work"], ["Family", "North Building", "Work"]])
    check("its explanation", got.get("explain"), "Which of your calendars show in the Today box. Tick the ones you want; the colored boxes in the Calendar section show or hide calendars there separately. Takes effect at once.")
    check("no longer under Sources", got.get("watch_has_it"), False)
    check("unticking Family saves and takes its events off Today at once", (got.get("saved"), got.get("after")), (True, ["Boiler check", "Standup"]))
    check("the saved setting is the same key as before", got.get("key"), ["Work", "North Building"])
    check("an unknown calendar is refused", got.get("refused"), False)
    check("the old Sources group no longer takes calendars", got.get("old_group_refused"), False)
    page = open(os.path.join(PKG, "engine", "System", "live_page", "page.html"), encoding="utf-8").read()
    check("Today has Choose calendars and the Calendar header has no Settings link, Choose calendars still opening the Calendar part",
          (page.count('data-s="cal-set">Choose calendars<'), page.count('id="cl-h">Calendar</h2><button'), "setGo('calendar')" in page), (1, 0, True))
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    for n, ok, got_, want in results:
        print(("PASS " if ok else "FAIL ") + n + ("" if ok else f"\n   got {got_!r}\n   want {want!r}"))
    print(f"{sum(1 for r_ in results if r_[1])} of {len(results)} passed")
    sys.exit(0 if all(r_[1] for r_ in results) else 1)
