r"""Acceptance (quick): an email shown as it was sent. A made-up Gmail email (plain and HTML parts, a picture by Content-ID) and
a made-up Outlook email (HTML only, an inline picture) are stored through the real connectors with a stand-in service: the
plain text stays the body the assistant reads, the HTML is kept apart with its pictures mapped to their stored attachments.
The cleaned document leaves out scripts, forms, frames, event handlers and javascript: links, holds back pictures from the
internet until asked, and opens links in a new tab. The history reload gives an email stored earlier its HTML.

    python tests\mail_html_acceptance.py
"""
import base64
import datetime as dt
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(os.path.dirname(HERE), "engine", "System", "live")
os.environ["ASSISTANT_LIVE_HOME"] = tempfile.mkdtemp(prefix="mailhtml-")
sys.path.insert(0, LIVE)
sys.path.insert(0, os.path.join(LIVE, "core"))

import db  # noqa: E402
import mail  # noqa: E402
import mailhtml  # noqa: E402
from connections import _http, _store, google_mail, microsoft_mail  # noqa: E402

db.init_schema()
results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


PIC = bytes(range(256)) * 160          # 40 KB: a real picture, not signature furniture
PIC2 = bytes(range(255, -1, -1)) * 170  # another one (a repeat of the same picture is furniture)
b64u = lambda b: base64.urlsafe_b64encode(b).decode()  # noqa: E731
HTML = ('<html><head><style>.h{color:#123}</style><meta http-equiv="refresh" content="0;url=https://x.example"></head>'
        '<body bgcolor="#fafafa"><p class="h" onclick="steal()">Hello <b>there</b></p><img src="cid:pic1@x.example">'
        '<img src="https://track.example/p.gif"><a href="https://shop.example/a">Shop</a><a href="javascript:alert(1)">bad</a>'
        '<script>alert(1)</script><form action="https://x.example"><input name="pw"><button>Go</button></form>'
        '<iframe src="https://x.example"></iframe><div style="background:url(https://track.example/b.gif)">x</div></body></html>')
GMAIL = {"id": "18c0a1b2c3d4e5f6", "threadId": "t1", "internalDate": str(int(dt.datetime(2026, 1, 5, 9).timestamp() * 1000)),
         "labelIds": ["INBOX"], "payload": {"mimeType": "multipart/related", "headers": [
             {"name": "From", "value": "news@x.example"}, {"name": "To", "value": "me@mail.example"},
             {"name": "Subject", "value": "News"}, {"name": "Message-ID", "value": "<n1@x.example>"}], "parts": [
             {"mimeType": "multipart/alternative", "headers": [], "parts": [
                 {"mimeType": "text/plain", "headers": [], "body": {"data": b64u(b"Hello there")}},
                 {"mimeType": "text/html", "headers": [], "body": {"data": b64u(HTML.encode())}}]},
             {"mimeType": "image/png", "filename": "photo.png", "headers": [{"name": "Content-ID", "value": "<pic1@x.example>"},
                                                                           {"name": "Content-Disposition", "value": "inline"}],
              "body": {"attachmentId": "A1", "size": len(PIC)}}]}}
OUTLOOK = {"id": "AAMk1", "subject": "Numbers", "receivedDateTime": "2026-01-05T17:00:00Z", "conversationId": "c1",
           "parentFolderId": "IN", "hasAttachments": False, "isRead": True, "categories": [], "internetMessageId": "<q1@y.example>",
           "from": {"emailAddress": {"address": "jo@y.example"}}, "toRecipients": [{"emailAddress": {"address": "me@work.example"}}],
           "body": {"contentType": "html", "content": "<p>The <b>numbers</b> are in.</p><img src=\"cid:image001.png@01D\">"}}


def get(url, token=None, params=None, headers=None):
    if url.endswith("/attachments/A1"):
        return {"data": b64u(PIC)}
    if url.endswith("/attachments"):
        return {"value": [{"name": "chart.png", "contentId": "image001.png@01D", "isInline": True, "size": len(PIC2),
                           "contentBytes": base64.b64encode(PIC2).decode()}]}
    if "/messages/18c0a1b2c3d4e5f6" in url:
        return GMAIL
    raise AssertionError(url)


_http.get_json = get
w = _store.MailWriter("me@mail.example")
google_mail._one("t", GMAIL["id"], "me@mail.example", w, {})
w.commit()
w = _store.MailWriter("me@work.example")
microsoft_mail._one("t", OUTLOOK, "me@work.example", w, {"inbox": "IN"})
w.commit()
con = db.connect(read_only=True)
rows = {r[0]: r[1:] for r in con.execute("SELECT m.subject, m.body, h.html IS NOT NULL, h.cids FROM messages m"
                                         " LEFT JOIN mail_html h ON h.message_id = m.id").fetchall()}
ids = dict(con.execute("SELECT subject, id FROM messages").fetchall())
con.close()
check("Gmail: the plain part is the body, the HTML kept apart", [rows["News"][0], rows["News"][1]], ["Hello there", True])
check("Gmail: its picture is mapped to its stored attachment", list(json.loads(rows["News"][2]).keys()), ["pic1@x.example"])
check("Outlook: plain text taken from the HTML is the body", rows["Numbers"][0], "The numbers are in.")
check("Outlook: its inline picture is mapped", list(json.loads(rows["Numbers"][2]).keys()), ["image001.png@01D"])

doc, remote = mail.body_doc(ids["News"], pictures=False)
low = doc.lower()
check("nothing that runs or sends is left",
      [x for x in ("<script", "onclick", "javascript:", "<form", "<input", "<iframe", "<button", "http-equiv", "alert(") if x in low], [])
check("hidden (Settings: Hide), pictures from the internet are held back, and said so", [remote, "track.example" in low], [True, False])
check("the email's own picture is put back in place", "/api/mail/file?ref=att:" in doc, True)
check("links open in a new tab, without the page's address",
      'href="https://shop.example/a" target="_blank" rel="noopener noreferrer"' in doc, True)
check("its formatting stays", ['<b>there</b>' in doc, ".h{color:#123}" in doc, 'bgcolor="#fafafa"' in doc], [True, True, True])
doc2, _ = mail.body_doc(ids["News"])
check("pictures from the internet show by default", ["https://track.example/p.gif" in doc2, "track.example/b.gif" in doc2], [True, True])
t = mail.thread(ids["News"])["messages"][0]
check("the thread says the email has HTML and pictures from the internet", [t["html"], t["remote"], t["text"]], [True, True, "Hello there"])

# an email stored before HTML was kept gains it in the history reload
with db.transaction() as c:
    c.execute("DELETE FROM mail_html WHERE message_id = ?", [ids["News"]])
check("lacking its HTML", _store.lacking_html("me@mail.example", [GMAIL["id"]]), {GMAIL["id"]})
google_mail._html_only("t", GMAIL["id"], "me@mail.example")
check("the reload gives it back, picture mapped to the same attachment", [_store.lacking_html("me@mail.example", [GMAIL["id"]]),
      "/api/mail/file?ref=att:" in mail.body_doc(ids["News"])[0]], [set(), True])

bad = [r for r in results if not r[1]]
for name, ok, got, want in results:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"\n   got  {got!r}\n   want {want!r}"))
print(f"{len(results) - len(bad)} of {len(results)} passed")
sys.exit(1 if bad else 0)
