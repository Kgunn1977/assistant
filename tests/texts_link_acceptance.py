r"""Acceptance: the texts link to Google Messages (engine/System/live/messages_link, textlink.py), on made-up data only, in a
scratch home (never the owner's). Nothing pairs with a real account and nothing is sent to Google or anyone.

  1. the companion builds from its source (when Go is on this computer) and the shipped program is there;
  2. the server starts it hidden and stops it: with no sign-in it says signed out; stopped, the program is gone;
  3. a made-up message passed twice through the companion's own event handler (its test mode, no connection) is handed over
     once and stored once; storing the same again stores nothing; a send request is formed as the bridge forms one; a picture
     still downloading on the phone (as Google sends it: auto-downloading, then complete with only a small inline preview, then
     complete with its media id) is stored once as its placeholder and its picture filled into that same text; a picture with only
     its thumbnail is handed over with it, its full size asked for once (as the bridge asks), and handed over again with its
     media id; the full picture replaces the thumbnail in that same file, a thumbnail never replaces a full one, a picture stored at
     thumbnail size before this build is replaced, and a thumbnail and its full picture in one batch store the full one once;
  4. one taker per text: while the link is signed in, it takes each queued text it can send, once;
  5. the page: the Texts section's sign-in steps and emoji are in the page; a disconnected link is said plainly in the
     Texts section and the Errors box's line; the sign-in door says which cookies are missing.

    python tests\texts_link_acceptance.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
LINK = os.path.join(PKG, "engine", "System", "live", "messages_link")
APPJS = os.path.join(PKG, "engine", "System", "live_page", "site", "app", "app.js")
results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


INSIDE = r'''
import datetime as dt, json, os, sys, subprocess, time, hashlib, secrets, urllib.request, urllib.error, socket
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, os.path.join(os.path.dirname(sys.argv[1]), "live_page"))
import common, db, texts, textlink
db.init_schema()
sk = socket.socket(); sk.bind(("127.0.0.1", 0)); free = sk.getsockname()[1]; sk.close()
common.write_json(common.SETTINGS, {"page_port": free})
out = {}

# 2. started with the server, stopped with it
textlink.BEAT_SECONDS = 1
out["started"] = textlink.start()
p = textlink._proc
for _ in range(40):
    if textlink.status().get("state") == "signed_out" and textlink.status().get("beat"):
        break
    time.sleep(0.25)
out["state with no sign-in"] = textlink.status().get("state")
out["no window"] = bool(textlink.HIDDEN)
textlink.stop()
out["stopped"] = p.poll() is not None

# 3. a made-up message through the companion's own handler, twice
us = int(time.time() * 1e6) - 60_000_000
conv = {"conversationID": "77", "name": "Alex Example", "defaultOutgoingID": "5", "type": "RCS", "sendMode": "SEND_MODE_AUTO",
        "participants": [{"ID": {"participantID": "5", "number": "+15550100100"}, "isMe": True},
                         {"ID": {"participantID": "7", "number": "+15550100177"}},      # Google's fake participant: not visible, not one of the people
                         {"ID": {"participantID": "9", "number": "+15550100199"}, "fullName": "Alex Example", "isVisible": True}],
        "otherParticipants": ["9"], "simCard": {"SIMData": {"SIMPayload": {"two": 1, "SIMNumber": 2}}}}
msg = {"messageID": "m1", "messageStatus": {"status": "INCOMING_COMPLETE"}, "timestamp": str(us), "conversationID": "77",
       "participantID": "9", "messageInfo": [{"messageContent": {"content": "Hello from the made-up phone"}}], "type": 1}
sending = dict(msg, messageID="m2", messageStatus={"status": "OUTGOING_SENDING"}, participantID="5")
fake = subprocess.Popen([textlink.EXE, "--test"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, creationflags=textlink.HIDDEN)
lines = [{"cmd": "fake", "rid": "1", "conv": conv, "msg": msg},
         {"cmd": "fake", "rid": "2", "conv": conv, "msg": dict(msg, messageStatus={"status": "INCOMING_DISPLAYED"}), "is_old": True},
         {"cmd": "fake", "rid": "3", "conv": conv, "msg": sending},
         {"cmd": "form_send", "rid": "4", "conv": "77", "text": "On my way", "tmp": "tmp-1"}]
got, _ = fake.communicate(("\n".join(json.dumps(x) for x in lines) + "\n").encode(), timeout=30)
events = [json.loads(x) for x in got.decode().splitlines() if x.strip()]
rows = [e["row"] for e in events if e.get("type") == "message"]
out["handed over"] = [[r["conv"], r["id"], r["direction"], r["text"], r["sender"]["number"]] for r in rows]
out["stored first time"] = textlink.store(rows)
out["stored again"] = textlink.store(rows)
con = db.connect(read_only=True)
out["in the database"] = con.execute("SELECT provider_id, thread_id, direction, body, subject FROM messages WHERE channel='sms'").fetchall()
con.close()
# a picture sent from the phone: first with its picture not ready (handed over as its placeholder, and the link's log says so), then with
# it (handed over again, once); a small preview inline is not the picture (as the bridge takes it, only a media id or a thumbnail id is)
pic0 = {"messageID": "pm1", "messageStatus": {"status": "OUTGOING_COMPLETE"}, "timestamp": str(us + 5_000_000), "conversationID": "77",
        "participantID": "5", "messageInfo": [{"mediaContent": {"mediaName": "photo.jpg", "mimeType": "image/jpeg", "mediaData": "aGVsbG8="}}], "type": 1}
pic1 = dict(pic0, messageInfo=[{"mediaContent": {"mediaName": "photo.jpg", "mimeType": "image/jpeg", "mediaData": "aGVsbG8=", "thumbnailMediaID": "th-1"}}])
fk2 = subprocess.Popen([textlink.EXE, "--test"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=textlink.HIDDEN)
got2, err2 = fk2.communicate(("\n".join(json.dumps(x) for x in [{"cmd": "fake", "rid": "1", "conv": conv, "msg": pic0},
                                                                 {"cmd": "fake", "rid": "2", "conv": conv, "msg": pic1},
                                                                 {"cmd": "fake", "rid": "3", "conv": conv, "msg": pic1}]) + "\n").encode(), timeout=30)
ev2 = [json.loads(x) for x in got2.decode().splitlines() if x.strip()]
log2 = err2.decode("utf-8", "replace")
out["picture handed over when ready"] = [[(e["row"]["id"], e["row"]["direction"], len(e["row"]["media"]), e["row"]["pending"]) for e in ev2 if e.get("type") == "message"],
                                         "not ready: no media id or thumbnail id yet" in log2, "already handed over" in log2]
# a picture received while the phone still downloads it, as Google sends several sent at once: auto-downloading (no ids), auto-downloading
# with a small inline preview, complete with only that preview, then complete with its media id
inc = {"messageID": "rp1", "messageStatus": {"status": "INCOMING_AUTO_DOWNLOADING"}, "timestamp": str(us + 9_000_000), "conversationID": "77",
       "participantID": "9", "messageInfo": [{"mediaContent": {"mediaName": "", "mimeType": "image/jpeg"}}], "type": 1}
prev = [{"mediaContent": {"mimeType": "image/jpeg", "mediaData": "aGVsbG8="}}]
seq = [inc, dict(inc, messageInfo=prev), dict(inc, messageStatus={"status": "INCOMING_COMPLETE"}, messageInfo=prev),
       dict(inc, messageStatus={"status": "INCOMING_COMPLETE"}, messageInfo=[{"mediaContent": {"mimeType": "image/jpeg", "mediaData": "aGVsbG8=",
                                                                                                 "mediaID": "full-1", "thumbnailMediaID": "th-2"}}]),
       dict(inc, messageStatus={"status": "INCOMING_DISPLAYED"}, messageInfo=[{"mediaContent": {"mimeType": "image/jpeg", "mediaID": "full-1"}}])]
fk3 = subprocess.Popen([textlink.EXE, "--test"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=textlink.HIDDEN)
got3, err3 = fk3.communicate(("\n".join(json.dumps({"cmd": "fake", "rid": str(i), "conv": conv, "msg": x}) for i, x in enumerate(seq)) + "\n").encode(), timeout=30)
rows3 = [json.loads(x)["row"] for x in got3.decode().splitlines() if x.strip() and json.loads(x).get("type") == "message"]
log3 = err3.decode("utf-8", "replace")
out["downloading picture handed over"] = [[(r["id"], r["direction"], len(r["media"]), r["pending"]) for r in rows3],
                                          "still downloading on the phone" in log3, "with_media_id=1" in log3]
os.makedirs(textlink.MEDIA, exist_ok=True)
for r in rows3:                     # test mode downloads nothing: the full picture's file, as the companion writes it
    for f in r["media"]:
        f["path"] = os.path.join(textlink.MEDIA, "rp1_0.jpg")
        with open(f["path"], "wb") as fh:
            fh.write(bytes(4098))
out["downloading picture stored"] = [textlink.store(rows3[:1]), textlink.store(rows3[1:])]
con = db.connect(read_only=True)
out["downloading picture in the database"] = con.execute(
    "SELECT m.provider_id, m.body, (SELECT count(*) FROM attachments a WHERE a.message_id = m.id) FROM messages m WHERE m.provider_id = 'gl:77:rp1'").fetchall()
con.close()
# the next catch-up starts at the newest stored text when no placeholder waits, and at the oldest placeholder of the week that still waits
out["catch-up from"] = [textlink._catchup_from_us() >= us + 9_000_000]
con = db.connect()
con.execute("INSERT INTO messages (channel, account, provider_id, thread_id, ts, direction, body, ingested_at) VALUES ('sms', 'sms', 'gl:77:rp9', 'gl:77', ?, 'in', ?, ?)",
            [dt.datetime.fromtimestamp((us - 3_600_000_000) / 1e6), "[media message, no text]", dt.datetime.now()])
con.close()
out["catch-up from"].append(textlink._catchup_from_us() < us - 3_600_000_000)
# full size: a picture received with only its thumbnail (as most came in at 36-112 KB), the same again, then with its media id, then again
from connections import _store
th = {"messageID": "fp1", "messageStatus": {"status": "INCOMING_COMPLETE"}, "timestamp": str(us + 12_000_000), "conversationID": "77",
      "participantID": "9", "messageInfo": [{"actionMessageID": "fp1-a", "mediaContent": {"mimeType": "image/jpeg", "thumbnailMediaID": "th-3"}}], "type": 1}
fu = dict(th, messageInfo=[{"actionMessageID": "fp1-a", "mediaContent": {"mimeType": "image/jpeg", "thumbnailMediaID": "th-3", "mediaID": "full-3"}}])
fk4 = subprocess.Popen([textlink.EXE, "--test"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=textlink.HIDDEN)
got4, err4 = fk4.communicate(("\n".join(json.dumps({"cmd": "fake", "rid": str(i), "conv": conv, "msg": x}) for i, x in enumerate([th, th, fu, fu])) + "\n").encode(), timeout=30)
rows4 = [json.loads(x)["row"] for x in got4.decode().splitlines() if x.strip() and json.loads(x).get("type") == "message"]
log4 = err4.decode("utf-8", "replace")
out["full size handed over"] = [[(r["id"], r["thumbnail"], [f["full"] for f in r["media"]]) for r in rows4],
                                log4.count("full size") == 1 and "part_id=fp1-a" in log4 and "asked (not sent: not connected)" in log4]
def give(row, size, full=True, drop_full=False):
    raw = json.loads(json.dumps(row))
    for f in raw["media"]:
        f["path"] = os.path.join(textlink.MEDIA, row["id"] + "_0.jpg")
        f["full"] = full
        if drop_full:
            del f["full"]               # a row from the companion before this build
        with open(f["path"], "wb") as fh:
            fh.write(bytes(size))
    return raw
def held(pid):
    con = db.connect(read_only=True)
    got = con.execute("SELECT a.saved_path FROM attachments a JOIN messages m ON m.id = a.message_id WHERE m.provider_id = ?", [pid]).fetchall()
    con.close()
    return [os.path.getsize(p) for (p,) in got], [p for (p,) in got]
s1 = textlink.store([give(rows4[0], 60_000, full=False)])
a1 = held("gl:77:fp1")
s2 = textlink.store([give(rows4[1], 900_000)])
a2 = held("gl:77:fp1")
textlink.store([give(rows4[0], 60_000, full=False)])         # a thumbnail again (a catch-up after a restart): not over the full one
a3 = held("gl:77:fp1")
out["full size stored"] = [s1, s2, a1[0], a2[0], a3[0], a1[1] == a2[1] == a3[1]]
old = dict(rows4[0], id="fp2", ts_us=us + 14_000_000)          # stored at thumbnail size by the build before this one, then caught up
textlink.store([give(old, 50_000, drop_full=True)])
textlink.store([give(dict(rows4[1], id="fp2", ts_us=us + 14_000_000), 700_000)])
both = [give(dict(rows4[0], id="fp3", ts_us=us + 15_000_000), 40_000, full=False)]
both.append(give(dict(rows4[1], id="fp3", ts_us=us + 15_000_000), 800_000))
out["full size older and one batch"] = [held("gl:77:fp2")[0], textlink.store(both), held("gl:77:fp3")[0], _store.upgraded[0]]
failed = dict(rows4[1], id="fp4", ts_us=us + 16_000_000, media=[{"name": "", "mime": "image/jpeg", "path": "", "error": "timeout", "full": True}])
textlink.store([give(dict(rows4[0], id="fp4", ts_us=us + 16_000_000), 45_000, full=False), failed])
out["full size older and one batch"].append(held("gl:77:fp4")[0])
req = [e for e in events if e.get("rid") == "4"][0]["request"]
pl = req["messagePayload"]
out["send request"] = [req["conversationID"], pl["participantID"], pl["messageInfo"][0]["messageContent"]["content"], req["tmpID"],
                       pl["tmpID"], pl["tmpID2"], req.get("SIMPayload"), req.get("forceRCS", False)]

# 4. one taker per text
import texts_cache; texts_cache.ON = False
now = common.now().isoformat(timespec="seconds")
common.write_json(textlink.STATUS, {"state": "connected", "paired": True, "signed_in_once": True, "beat": now, "state_since": now})
c = texts.conversations()["rows"][0]
q = texts.queue_send(c["id"], "On my way")
out["queued"] = q["ok"]
took = texts.next_send(for_link=True)
out["link took it"] = [bool(took), took and took["gl"], took and took["phone"]]
out["status lines when connected"] = textlink.problems()

# 5. the page
common.write_json(textlink.STATUS, {"state": "unpaired", "say": "Your phone is no longer paired with this computer.", "paired": False,
                                    "signed_in_once": True, "beat": now, "state_since": now})
import local_site
srv = local_site.start()
port = srv.server_address[1]
local_site.time.sleep = lambda s: None
def req(path, body=None, host=None):
    h = {"Host": host or f"127.0.0.1:{port}", "Content-Type": "application/json", "Cookie": ck, "X-Brief-Csrf": csrf}
    if host:
        h["Origin"] = "https://" + host                 # the page at its own private https address
    rq = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=None if body is None else json.dumps(body).encode(), method="GET" if body is None else "POST", headers=h)
    try:
        with urllib.request.urlopen(rq, timeout=30) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, None
tok = secrets.token_urlsafe(48); csrf = secrets.token_hex(32)
local_site._save("sessions", {hashlib.sha256(tok.encode()).hexdigest(): {"made": int(time.time()), "seen": int(time.time()), "exp": int(time.time()) + 3600, "len": 3600, "csrf": csrf}})
ck = f"{local_site.cookie_name()}={tok}"
s, lst = req("/api/texts")
out["texts section"] = [s, lst["link"]["state"], lst["problem"]]
s, st = req("/api/texts/status")
out["errors box line"] = st["problem"]
s, lk = req("/api/texts/link")
out["link door"] = [s, lk["link"]["state"]]
s, r = req("/api/texts/link/signin", {"cookies": "curl 'https://messages.google.com/web/config' -H 'Cookie: SID=a1; HSID=b2'"})
out["signin missing"] = r
cur = "curl 'https://messages.google.com/web/config' -H 'User-Agent: x' -H 'Cookie: SID=s1; HSID=h2; OSID=o3; SSID=s4; APISID=a5; SAPISID=sa6; __Secure-1PSIDTS=sidts-7; NID=n8'"
out["cookies from cURL"] = textlink.parse_cookies(cur)
win = cur.replace("'", '^"')
out["cookies from Windows cURL"] = textlink.parse_cookies(win)[1]
# the page at its own private https address (reached from anywhere): the sign-in and its status door answer there too
sp = os.path.join(local_site.publish.HOME, "personal", "settings.json")
st0 = local_site.publish.read_json(sp) or {}
local_site.publish.write_json(sp, dict(st0, page_reach={"how": "tailscale", "address": "https://desk-made-up.tail0000.ts.net:8443"}))
far = "desk-made-up.tail0000.ts.net:8443"
s1, lk2 = req("/api/texts/link", host=far)
s2, r2 = req("/api/texts/link/signin", {"cookies": "curl 'https://messages.google.com/web/config' -H 'Cookie: SID=a1; HSID=b2'"}, host=far)
out["outside"] = [s1, bool(lk2 and lk2.get("ok")), s2, bool(r2) and r2.get("ok") is False and "OSID" in str(r2.get("error"))]
local_site.publish.write_json(sp, st0)
# Take it back now: his press, with the page's check, reaches the link's take-back; without the check it is refused
real_call = textlink._call
asked = []
textlink._call = lambda cmd, timeout=30: asked.append(cmd.get("cmd")) or {"ok": True, "taken": True}
s3, r3 = req("/api/texts/link/takeback", {})
h4 = {"Host": f"127.0.0.1:{port}", "Content-Type": "application/json", "Cookie": ck}
rq4 = urllib.request.Request(f"http://127.0.0.1:{port}/api/texts/link/takeback", data=b"{}", method="POST", headers=h4)
try:
    with urllib.request.urlopen(rq4, timeout=30) as r4:
        s4 = r4.status
except urllib.error.HTTPError as e:
    s4 = e.code
textlink._call = real_call
out["take back now"] = [s3, bool(r3 and r3.get("ok")), asked, s4]
srv.shutdown()
# each picture seen is logged with its conversation, time and sources; the picture catch-up runs again for a new companion build
out["picture seen logged"] = [("picture seen" in log2 and "conversation=77" in log2 and "inline_bytes=5" in log2 and "media_id=false" in log2)]
common.write_json(textlink.STATUS, dict(textlink.status(), pictures_catchup_build="an-older-build"))
out["picture catch-up again for a new build"] = [len(textlink.build()), textlink.status().get(textlink.PICTURES_BUILD) != textlink.build()]
print(json.dumps(out, default=str))
'''


RENDER = r"""
const src = require('fs').readFileSync(process.argv[1], 'utf8');
const grab = (name) => { const i = src.indexOf('function ' + name + '('); let d = 0;
  for (let k = src.indexOf('{', i); k < src.length; k++) { if (src[k] === '{') d++; else if (src[k] === '}') { d--; if (!d) return src.slice(i, k + 1); } } };
const decl = src.match(/var TX_SIGNIN = [^;]+;/)[0];
let toasted = false;
const f = new Function('S', 'h', 'toast', decl + grab('txLinkSet') + grab('txLinkHtml') + 'return {set: txLinkSet, html: txLinkHtml};');
const S = {tx: {link: {}, linkOpen: false, linkBusy: false, linkErr: '', linkWatch: 0}};
const h = (x) => String(x).replace(/[&<>"]/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'})[c]);
const p = f(S, h, () => { toasted = true; });
const fox = String.fromCodePoint(0x1F98A), out = {};
p.set({state: 'signed_out'}); out.signed_out = /Sign in to Google Messages/.test(p.html());
p.set({state: 'unpaired', signed_in_once: true}); out.unpaired = />Sign in to Google Messages</.test(p.html());
S.tx.linkOpen = true; out.steps = p.html().indexOf('Copy as cURL (POSIX)') > 0 && p.html().indexOf('AccountChooser') > 0; S.tx.linkOpen = false;
S.tx.linkWatch = Date.now(); p.set({state: 'pairing', emoji: fox}); out.pairing = p.html().indexOf(fox) > 0;
p.set({state: 'connecting'}); out.connecting = /Paired with your phone/.test(p.html());
p.set({state: 'connected'}); out.connected = p.html() === ''; out.toast = toasted;
console.log(JSON.stringify(out));
"""


def main():
    exe = os.path.join(LINK, "messages-link.exe")
    check("the shipped companion is there", os.path.isfile(exe), True)
    go = shutil.which("go") or (r"C:\Program Files\Go\bin\go.exe" if os.path.isfile(r"C:\Program Files\Go\bin\go.exe") else None)
    if go:
        tmpd = tempfile.mkdtemp(prefix="ml-build-")
        r = subprocess.run([go, "build", "-trimpath", "-buildvcs=false", "-ldflags", "-s -w -H=windowsgui", "-o", os.path.join(tmpd, "m.exe"), "."],
                           cwd=LINK, capture_output=True, text=True, timeout=110, env=dict(os.environ, CGO_ENABLED="0"))
        check("the companion builds from its source", [r.returncode, r.stderr.strip()[-300:]], [0, ""])
        import hashlib
        same = lambda f: hashlib.sha256(open(f, "rb").read()).hexdigest() if os.path.isfile(f) else ""      # noqa: E731
        check("the shipped companion is built from this source", same(os.path.join(tmpd, "m.exe")) == same(exe), True)
        shutil.rmtree(tmpd, ignore_errors=True)
        deps = subprocess.run([go, "list", "-deps", "."], cwd=LINK, capture_output=True, text=True, timeout=60).stdout
        check("nothing of Matrix in it", [d for d in deps.split() if "maunium" in d or "bridgev2" in d], [])
        mod = open(os.path.join(LINK, "go.mod"), encoding="utf-8").read()
        check("libgm pinned, unmodified (no replace)", ["ed5dc19eb2b4" in mod, "replace" in mod], [True, False])
    live = os.path.join(PKG, "engine", "System", "live")
    tmp = tempfile.mkdtemp(prefix="tl-")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=os.path.join(tmp, "Live"))
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live], capture_output=True, text=True, env=env, timeout=100, encoding="utf-8")
    sys.path.insert(0, HERE)
    import _cleanup
    _cleanup.remove(tmp)
    try:
        out = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        print("the engine part did not run:", (r.stderr or r.stdout)[-3000:])
        return 1
    check("started with the server", out["started"], True)
    check("signed out with no sign-in, no window", [out["state with no sign-in"], out["no window"]], ["signed_out", True])
    check("stopped with the server", out["stopped"], True)
    check("handed over once (a later status of the same text and a send under way are not)", out["handed over"],
          [["77", "m1", "in", "Hello from the made-up phone", "+15550100199"]])
    check("stored once", [out["stored first time"], out["stored again"]], [[1, 0], [0, 1]])
    check("a text whose picture is not ready yet (a small inline preview only) is handed over as its placeholder and logged, then once with it",
          out["picture handed over when ready"], [[["pm1", "out", 0, True], ["pm1", "out", 1, False]], True, True])
    check("a picture still downloading on the phone: held while auto-downloading, a placeholder on complete with only a preview, again with its media id, once",
          out["downloading picture handed over"], [[["rp1", "in", 0, True], ["rp1", "in", 1, False]], True, True])
    check("stored once as its placeholder, then its full picture filled into that same text (no new row)",
          [out["downloading picture stored"], out["downloading picture in the database"]], [[[1, 0], [0, 1]], [["gl:77:rp1", "[media message, no text]", 1]]])
    check("the next catch-up starts at the oldest placeholder of the week still without its picture", out["catch-up from"], [True, True])
    check("a picture with only its thumbnail is handed over with it, its full size asked for once, and handed over again with its media id",
          out["full size handed over"], [[["fp1", True, [False]], ["fp1", False, [True]]], True])
    check("the full picture replaces the thumbnail in the same file (one attachment); a thumbnail afterwards does not replace it",
          out["full size stored"], [[1, 0], [0, 1], [60_000], [900_000], [900_000], True])
    check("a picture stored at thumbnail size before this build is replaced; a thumbnail and its full picture in one batch store the full one once; a full one that failed to download leaves the thumbnail",
          out["full size older and one batch"], [[700_000], [1, 0], [800_000], 2, [45_000]])
    check("every picture seen is logged with its conversation, its time and which of its sources it has", out["picture seen logged"], [True])
    check("the picture catch-up runs again when the companion is a new build", out["picture catch-up again for a new build"], [12, True])
    check("stored as a text of the person", out["in the database"], [["gl:77:m1", "gl:77", "in", "Hello from the made-up phone", "Alex Example"]])
    check("send request formed as the bridge forms it", out["send request"],
          ["77", "5", "On my way", "tmp-1", "tmp-1", "tmp-1", {"two": 1, "SIMNumber": 2}, False])
    check("the link takes the queued text", [out["queued"], out["link took it"]], [True, [True, "77", "5550100199"]])
    check("no false line while connected", out["status lines when connected"], [])
    line = ("Google Messages: texts are disconnected. Your phone is no longer paired with this computer. To get them back, sign in again: "
            "press Sign in to Google Messages in the Texts section.")
    check("Texts section says disconnected", out["texts section"], [200, "unpaired", line])
    check("Errors box line says disconnected", out["errors box line"], line)
    check("link door", out["link door"], [200, "unpaired"])
    check("sign-in says what is missing", [out["signin missing"]["ok"], "OSID" in out["signin missing"]["error"]], [False, True])
    check("Take it back now: his press reaches the link's take-back once; without the page's check it is refused",
          out.get("take back now"), [200, True, ["take_back"], 403])
    check("at the page's own private https address the link's status answers and the sign-in reaches the pairing (missing cookies said)",
          out.get("outside"), [200, True, 200, True])
    check("cookies read from a cURL copy", out["cookies from cURL"],
          [{"SID": "s1", "HSID": "h2", "OSID": "o3", "SSID": "s4", "APISID": "a5", "SAPISID": "sa6", "__Secure-1PSIDTS": "sidts-7"}, []])
    check("and from the Windows form", out["cookies from Windows cURL"], [])
    js = open(APPJS, encoding="utf-8").read()
    check("the page has the sign-in steps and the emoji", [w in js for w in (
        ">Sign in to Google Messages<", "Ctrl+Shift+P", "accounts.google.com/AccountChooser?continue=https://messages.google.com/web/config",
        "Copy as cURL (POSIX)", "Do not sign out of Google there", "tx-emoji", "Tap this emoji on your phone")], [True] * 7)
    node = shutil.which("node")
    if node:        # the sign-in part of the Texts section, run (not only read) in each state, with the page's helpers stubbed
        r = subprocess.run([node, "-e", RENDER, APPJS], capture_output=True, text=True, timeout=60, encoding="utf-8")
        try:
            got = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            got = r.stderr[-500:]
        check("the sign-in part draws in each state", got,
              {"signed_out": True, "unpaired": True, "steps": True, "pairing": True, "connecting": True, "connected": True, "toast": True})
    bad = [x for x in results if not x[1]]
    for name, ok, got, want in results:
        print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"\n     got:  {got}\n     want: {want}"))
    print(f"{len(results) - len(bad)} of {len(results)} checks passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
