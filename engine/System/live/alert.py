r"""Phone notifications for important items, through ntfy: one HTTP POST per alert.

    python alert.py            # notification for any important item not yet alerted
    python alert.py --test     # build a test notification and try to send it

Off until a topic is set in Live\settings.json ("alerts": {"server", "topic"}).
With no topic a notification is built, logged as skipped, and nothing leaves the
computer. What counts as important is the list in Important.md, applied by the
think pass; this file only delivers.
"""
import datetime as dt
import json
import sys
import urllib.error
import urllib.request

import common

FRESH_HOURS = 24  # an item marked important longer ago than this is not alerted late


def build(item):
    """The notification for one item, as the JSON ntfy takes."""
    body = item.get("important_reason") or item["title"]
    if item.get("source_ref"):
        body += f"\n{item['source_ref']}"
    return {"title": item["title"][:120], "message": body[:900], "priority": 4,
            "tags": ["rotating_light"]}


def send(alert):
    """(status, detail): 'sent', 'skipped' (no topic set) or 'failed'."""
    import replay_guard
    replay_guard.refuse("a phone notification")
    cfg = (common.settings().get("alerts") or {})
    topic, server = (cfg.get("topic") or "").strip(), (cfg.get("server") or "").strip().rstrip("/")
    if not topic or not server:
        return "skipped", "no notification topic is set"
    req = urllib.request.Request(server, data=json.dumps(dict(alert, topic=topic)).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return ("sent", f"HTTP {r.status}") if r.status == 200 else ("failed", f"HTTP {r.status}")
    except (urllib.error.URLError, OSError) as e:
        return "failed", str(e)[:200]


def enabled():
    cfg = (common.settings().get("alerts") or {})
    return bool((cfg.get("topic") or "").strip())


def alert_important(pass_id):
    """Alert once for each important open item. Returns (sent, skipped, problems)."""
    import replay_guard
    replay_guard.refuse("phone notifications for important cards")
    import items
    sent_log = common.read_json(common.ALERTS_SENT, {})
    cutoff = common.now() - dt.timedelta(hours=FRESH_HOURS)
    sent, skipped, problems = 0, 0, []
    import settings_page
    held = common.read_json(settings_page.ALERTS_HELD, {}) or {}
    waiting = items.rows("importance >= 1 AND state <> 'done' AND source_key NOT LIKE 'live:test-%'")
    if settings_page.in_quiet():
        # quiet hours: nothing is sent; what would have alerted is kept for one alert when the hours end
        new = [it for it in waiting if it["id"] not in sent_log and it["id"] not in held and it["updated_at"] >= cutoff]
        for it in new:
            held[it["id"]] = common.now().isoformat(timespec="seconds")
            common.log_line(common.PASS_LOG, f"alert {it['id']} held: quiet hours: {it['title'][:80]}")
        if new:
            common.write_json(settings_page.ALERTS_HELD, held)
        return 0, len(new), []
    if held:
        # quiet hours are over: one alert for everything held that is still open and important
        still = [it for it in waiting if it["id"] in held and it["id"] not in sent_log]
        status, detail = "skipped", ""
        if still:
            many = len(still) > 1
            status, detail = send({"title": f"{len(still)} important items came in during quiet hours" if many else still[0]["title"][:120],
                                   "message": ("\n".join("- " + it["title"][:150] for it in still[:12]) if many
                                               else build(still[0])["message"])[:900],
                                   "priority": 4, "tags": ["rotating_light"]})
            common.log_line(common.PASS_LOG, f"notification after quiet hours {status}: {detail}: {len(still)} item(s)")
        if status == "failed":
            problems.append(f"the notification held over quiet hours could not be sent: {detail}")
        else:
            if status == "sent":
                sent += 1
                for it in still:
                    sent_log[it["id"]] = {"at": common.now().isoformat(timespec="seconds"), "pass": pass_id}
                common.write_json(common.ALERTS_SENT, sent_log)
            else:
                skipped += len(still)
            held = {}
            common.write_json(settings_page.ALERTS_HELD, held)
    for it in waiting:
        if it["id"] in sent_log or it["id"] in held or it["updated_at"] < cutoff:
            continue
        status, detail = send(build(it))
        common.log_line(common.PASS_LOG, f"alert {it['id']} {status}: {detail}: {it['title'][:80]}")
        if status == "sent":
            sent += 1
            sent_log[it["id"]] = {"at": common.now().isoformat(timespec="seconds"), "pass": pass_id}
        elif status == "skipped":
            skipped += 1
        else:
            problems.append(f"the notification for the card \"{it.get('title') or 'with no title'}\" could not be sent: {detail}")
    if sent:
        common.write_json(common.ALERTS_SENT, sent_log)
    return sent, skipped, problems


def last_sent():
    log = common.read_json(common.ALERTS_SENT, {})
    return max((v["at"] for v in log.values()), default=None)


def main():
    if "--test" in sys.argv:
        alert = build({"title": f"Test notification from {common.owner()}'s assistant",
                       "important_reason": "If you can read this on your phone, notifications work.",
                       "source_ref": f"sent {common.now():%m/%d %I:%M %p}"})
        status, detail = send(alert)
        common.log_line(common.PASS_LOG, f"notification test {status}: {detail}")
        print(json.dumps(alert, indent=1))
        print(f"{status}: {detail}")
        return 0 if status in ("sent", "skipped") else 1
    print("sent %d, skipped %d, problems %s" % alert_important("manual"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
