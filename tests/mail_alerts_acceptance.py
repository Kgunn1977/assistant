r"""Acceptance: phone alerts for mail that matters (mail_alerts.py), with made-up mail, a stub database and a stub sender.

- The first run only learns what is there; nothing is sent.
- Only mail that matters alerts (sender who always gets through, or on an important card); other mail does not.
- Several in one pass make one alert; the tap opens the email (one) or the Mail page (several).
- Never twice for the same email; quiet hours send nothing and the mail alerts when they end.
- "every" alerts for all; "none" for nothing.

    python tests\mail_alerts_acceptance.py
"""
import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(os.path.dirname(HERE), "engine", "System", "live")
os.environ["ASSISTANT_LIVE_HOME"] = tempfile.mkdtemp()
sys.path.insert(0, LIVE)
sys.path.insert(0, os.path.join(LIVE, "core"))
import common  # noqa: E402

ROWS = []
db = types.ModuleType("db")
db.query = lambda sql, params=(): [(3,)] if "direction = 'out'" in sql else list(ROWS)
items = types.ModuleType("items")
items.rows = lambda where="1=1", params=(): [{"id": "c1", "source_messages": [2]}]
quiet = {"on": False}
sp = types.ModuleType("settings_page")
sp.in_quiet = lambda: quiet["on"]
ss = types.ModuleType("setup_steps")
ss.page_address = lambda: "https://page.example"
for name, mod in (("db", db), ("items", items), ("settings_page", sp), ("setup_steps", ss)):
    sys.modules[name] = mod
import mail_alerts  # noqa: E402

s = common.settings()
s["alerts"] = {"server": "https://ntfy.example", "topic": "stub", "mail": "matters"}
s["filter"] = {"always_through": ["boss@vip.example"]}
common.write_json(common.SETTINGS, s)
SENT = []
send = lambda a: (SENT.append(a), ("sent", "ok"))[1]  # noqa: E731
results = []


def check(name, ok):
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name)


def mail(i, frm, name, subject):
    return (i, "email:" + frm, name, subject)


ROWS[:] = [mail(1, "boss@vip.example", "The Boss", "old")]
mail_alerts.run("p0", send)
check("first run sends nothing", not SENT)
ROWS[:] = [mail(1, "boss@vip.example", "The Boss", "old"), mail(2, "x@shop.example", "", "Your order"),
           mail(3, "y@news.example", "", "Weekly"), mail(4, "boss@vip.example", "The Boss", "Contract")]
quiet["on"] = True
check("quiet hours send nothing", mail_alerts.run("p1", send)[0] == 0 and not SENT)
quiet["on"] = False
r = mail_alerts.run("p2", send)
check("one grouped alert: always-through sender, a reply in my thread, mail on an important card", r[0] == 1 and len(SENT) == 1 and SENT[0]["title"] == "3 emails that matter"
      and "Contract" in SENT[0]["message"] and "Weekly" in SENT[0]["message"] and "Your order" in SENT[0]["message"] and SENT[0]["click"] == "https://page.example")
mail_alerts.run("p3", send)
check("never twice for the same email", len(SENT) == 1)
ROWS[:] += [mail(5, "boss@vip.example", "The Boss", "Call me")]
mail_alerts.run("p4", send)
check("one email: sender, subject, taps to that email", len(SENT) == 2 and SENT[1]["title"] == "The Boss"
      and SENT[1]["message"] == "Call me" and SENT[1]["click"] == "https://page.example/#mail=5")
s["alerts"]["mail"] = "every"
common.write_json(common.SETTINGS, s)
ROWS[:] += [mail(6, "z@any.example", "", "Hello")]
mail_alerts.run("p5", send)
check("every: any new inbox email alerts", len(SENT) == 3 and "Hello" in SENT[2]["message"])
s["alerts"]["mail"] = "none"
common.write_json(common.SETTINGS, s)
ROWS[:] += [mail(7, "boss@vip.example", "The Boss", "More")]
mail_alerts.run("p6", send)
check("none: nothing", len(SENT) == 3)
sys.exit(0 if all(results) else 1)
