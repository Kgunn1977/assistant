r"""Acceptance (quick) of the Card button in the Email part (mail_card.py), on a scratch home with made-up mail; no Claude run (the
card writer is stood in for, and shown exactly what the real one is shown):

- Card on two old emails about the same topic (no card yet, judged as needing nothing) makes one card holding both, at once,
  through the press the page sends; the writer is told the owner asked for them, and may not pass them over;
- Card on an email already on a card makes no new card, and the result names that card;
- no rule book row is written;
- the page shows Card beside Archive, Delete and Junk on selected emails and inside an opened email.

    python tests\mail_card_acceptance.py
"""
import datetime as dt
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(os.path.dirname(HERE), "engine", "System", "live")
PAGE = os.path.join(os.path.dirname(HERE), "engine", "System", "live_page", "page.html")
home = tempfile.mkdtemp(prefix="mailcard-")
os.environ["ASSISTANT_LIVE_HOME"] = home
sys.path.insert(0, LIVE)
sys.path.insert(0, os.path.join(LIVE, "core"))

results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


def page_checks():
    with open(PAGE, encoding="utf-8") as f:
        page = f.read()
    bulk = page[page.index("function mailBulkHtml()"):page.index("function mailBulk(")]
    one = page[page.index("'<button class=\"btn\" type=\"button\" data-a=\"mail-draft\" data-t=\"forward\""):]
    one = one[:one.index("</div>';")]
    near = lambda part: [x in part for x in ('data-a="mail-card"', ">Card</button>", "'Archive'" if part is bulk else ">Archive</button>",
                                             ">Delete</button>", "'Junk'" if part is bulk else ">Junk</button>")]
    check("selected emails: Card sits in the same row as Archive, Delete and Junk", near(bulk), [True] * 5)
    check("an opened email: Card sits in the same row as Archive, Delete and Junk", near(one), [True] * 5)
    check("a press on Card is handled", bool(re.search(r"a === 'mail-card'\) \{.*mailCard\(", page)), True)


def main():
    import common
    import db
    import items
    db.init_schema()
    items.ensure()
    old = dt.datetime.now() - dt.timedelta(days=200)
    con = db.connect()
    for mid, thread, subject, body in ((40001, "t:a", "Trailer hitch quote", "Made-up: the hitch for the trailer is $310."),
                                       (40002, "t:b", "Re: trailer hitch", "Made-up: we can fit the hitch on Friday."),
                                       (40003, "t:c", "Garden club", "Made-up: the garden club meets Tuesday.")):
        con.execute("INSERT INTO messages (id, channel, account, thread_id, ts, direction, from_key, to_keys, subject, body, ingested_at)"
                    " VALUES (?, 'email', 'me@one.example', ?, ?, 'in', 'email:shop@hitch.example', '[]', ?, ?, ?)",
                    (mid, thread, old + dt.timedelta(hours=mid - 40000), subject, body, old))
        con.execute("INSERT INTO answered (domain, key, verdict, source, answered_at) VALUES ('judged', ?, 'noise', 'test', ?)",
                    (f"msg:{mid}", old))
    con.close()

    import ai_steps
    import answers
    import think
    seen = []

    def writer(prompt, model, expect, **k):         # the card writer, stood in for: every loose email on one card, by topic
        payload = common.read_json(os.path.join(common.paths.STATE, "live_items_payload.json"), {})
        loose = payload.get("loose_messages") or []
        seen.append(sorted((m["id"], bool(m.get("asked_for_card"))) for m in loose))
        ids = [m["id"] for m in loose]
        common.write_json(expect, {"items": [], "loose": [], "new_items": [{
            "messages": ids, "kind": "task", "area": "Personal", "title": "Trailer hitch: quote and fitting",
            "header": "Trailer hitch", "why": "Made-up.", "detail": "Made-up: a quote and a fitting day for the hitch.",
            "recommended": None, "asks": [], "evidence": f"Emails {', '.join(str(i) for i in ids)}.", "state": "yours"}]})
        return ai_steps.Result(True)
    ai_steps.agent = writer

    book = os.path.join(common.PERSONAL, "rule_book.jsonl")
    count = lambda: len(items.rows("1=1"))
    press = lambda n, ids, all_=True: answers.act_on_answer({"id": f"mail-card:{n}", "action": "answer", "at": dt.datetime.now().isoformat(),
                                                             "text": json.dumps({"mail_card": {"messages": ids, "all": all_}})})
    before = count()
    out = press(1, [40001, 40002])
    cards = [r for r in items.rows("state <> 'done'") if {"40001", "40002"} & set(r["source_messages"])]
    check("two old emails on one topic: one card holding both", [count() - before, len(cards), sorted(cards[0]["source_messages"]) if cards else None],
          [1, 1, ["40001", "40002"]])
    check("the writer was told the owner asked for both", seen, [[(40001, True), (40002, True)]])
    check("the result says a card was made and carries it for the page", [out.get("ok"), out.get("result"), [i.get("id") for i in out.get("items") or []]],
          [True, "I made a card from those emails.", [cards[0]["id"]] if cards else None])
    skip = think._commit_items({"items": [], "new_items": [], "loose": [{"message": 40003, "skip": "nothing needed"}]},
                               {"items": [], "loose_messages": [{"id": 40003, "asked_for_card": True}]}, {})
    check("a picked email may not be passed over by the writer", [bool(skip), "asked_for_card" in " ".join(skip)], [True, True])

    n = count()
    out = press(2, [40002], all_=False)
    check("an email already on a card: no new card, and that card comes back to be opened",
          [count() - n, len(seen), out.get("result"), [i.get("id") for i in out.get("items") or []]],
          [0, 1, "That email is already on a card.", [cards[0]["id"]] if cards else None])
    check("no rule book row is written", [os.path.exists(book) and os.path.getsize(book) > 0], [False])
    check("the pass lock is let go", os.path.exists(common.LOCK), False)
    page_checks()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        results.append(("ran to the end", False, repr(e), "no error"))
    finally:
        shutil.rmtree(home, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    sys.exit(0 if results and all(r[1] for r in results) else 1)
