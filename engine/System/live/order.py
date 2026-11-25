r"""The order cards are in, how they group, and the one plain line at the top of the page.

ITEMS.md ("Design round 3") is the contract. Called by the page's data builder (publish.py) every time it
builds, so a press changes the line and the order at once. Nothing here calls Claude or opens the database.

    annotate(cards)   rank (true order) on every card; group on every card when the setting is on
    top(cards, done)  the line, the counts and the card that comes next
"""
import datetime as dt

import common

GROUP_BY = ("nothing", "sender", "area", "conversation")
# the bar at the top of Cards (page.html SORTS): Due date, Newest first, Oldest first, Waiting longest, Importance, Recently active
SORT_BY = ("due_first", "newest_first", "oldest_first", "waiting_longest", "important_senders_first", "recently_active")
NEED_YOU = ("answer", "approval", "do")


def settings():
    page = (common.settings().get("page") or {}) if isinstance(common.settings().get("page"), dict) else {}
    return (page.get("group_by") if page.get("group_by") in GROUP_BY else "nothing",
            page.get("sort_by") if page.get("sort_by") in SORT_BY else "due_first")


def _when(it):
    for k in ("source_when", "created_at", "updated_at"):
        try:
            return dt.datetime.fromisoformat(str(it.get(k))[:19]).timestamp()
        except (ValueError, TypeError):
            continue
    return 0.0


def _from(it):
    """When the card is from (items.stamp_from): what Newest first and Oldest first go by."""
    try:
        return dt.datetime.fromisoformat(str(it.get("from_at"))[:19]).timestamp()
    except (ValueError, TypeError):
        return _when(it)


def _stamp(it, k):
    try:
        return dt.datetime.fromisoformat(str(it.get(k))[:19]).timestamp()
    except (ValueError, TypeError):
        return None


def _waited(it):
    """Since when the card has sat where it is (state_changed_at, as comeback.py counts a wait): what Waiting longest goes by."""
    got = _stamp(it, "state_changed_at")
    return _from(it) if got is None else got


def _last(it):
    """The latest message on the card (items._extras last_at), else when it is from: what Recently active goes by."""
    got = _stamp(it, "last_at")
    return _from(it) if got is None else got


def _due(it):
    try:
        return dt.date.fromisoformat(str(it.get("due_date"))[:10])
    except (ValueError, TypeError):
        return None


def _put_off(it):
    """An older Snooze or Not now whose day has not come yet: it is put off like a card on the shelf."""
    if not str(it.get("status") or "").startswith(("Snoozed", "Not now")):
        return False
    try:
        return dt.date.fromisoformat(str(it.get("checkback_date"))[:10]) > dt.date.today()
    except (ValueError, TypeError):
        return False


def _closed(it):
    return it.get("state") == "done" or bool(it.get("shelf")) or _put_off(it)


def key_for(it, sort, today):
    closed = _closed(it)
    due = _due(it)
    import card as card_mod
    # what asks something of him comes before what only waits on others, which comes before what needs nothing
    need = {"waiting": 1, "nothing": 2}.get(it.get("needs") or card_mod.needs(it), 0)
    strength = -int(((it.get("contact") or {}) if isinstance(it.get("contact"), dict) else {}).get("level") or 0)
    importance = -(it.get("importance") or 0)
    # Due date: the soonest due date first (late ones are the soonest), then important, then how often he is in touch, then age
    due_first = (need, 0 if due else 1, due or dt.date.max, importance, strength, _when(it))
    # whatever the order, what asks something of him comes before what only waits or only informs: the line names the first
    # (the page's Group by kind off mixes the kinds by the same keys without this, page.html sortKey)
    if sort == "newest_first":
        return (closed, need, -_from(it))
    if sort == "oldest_first":
        return (closed, need, _from(it))
    if sort == "waiting_longest":
        return (closed, need, _waited(it))
    if sort == "recently_active":
        return (closed, need, -_last(it))
    if sort == "important_senders_first":         # Importance: the most important first, then the newest
        return (closed, need, importance, -_from(it))
    return (closed,) + due_first


def group_of(it, by):
    if by == "sender":
        who = it.get("sender") if isinstance(it.get("sender"), dict) else {}
        label = " ".join(str(it.get("source_who") or "").split())
        if label.split(":", 1)[0] in common.sender_kinds() - {"text"} and ":" in label:
            label = label.split(":", 1)[1]              # a sender known only by address reads as the address
        if who.get("address") or label:
            return {"key": "sender:" + (who.get("address") or label.lower()), "label": label or who.get("address")}
    elif by == "area":
        if it.get("area"):
            return {"key": "area:" + str(it["area"]), "label": str(it["area"])}
    elif by == "conversation":
        t = it.get("thread") if isinstance(it.get("thread"), dict) else {}
        if t.get("key"):
            return {"key": "conversation:" + str(t["key"]), "label": " ".join(str(t.get("label") or it.get("title") or "").split())}
    return {"key": "none", "label": "Other"}


def annotate(cards, today=None):
    """rank on every card (1 is first); group on every card only when the owner chose to group. Changes in place."""
    today = today or dt.date.today()
    by, sort = settings()
    ordered = sorted(cards, key=lambda it: key_for(it, sort, today))
    for n, it in enumerate(ordered, 1):
        it["rank"] = n
        if by != "nothing":
            it["group"] = group_of(it, by)
        else:
            it.pop("group", None)
    return cards


def top(cards, done_for_you=0, today=None):
    """The top of the page: {"line", "need_you", "late_or_due", "clear", "next", "waiting_on_others", "done_for_you"}."""
    import card as card_mod
    import dates
    today = today or dt.date.today()
    open_ = [it for it in cards if not _closed(it)]
    need = [it for it in open_ if (it.get("needs") or card_mod.needs(it)) in NEED_YOU]
    waiting = [it for it in open_ if (it.get("needs") or card_mod.needs(it)) == "waiting"]
    need.sort(key=lambda it: it.get("rank") or 10 ** 6)
    late = [it for it in need if _due(it) is not None and _due(it) <= today]
    n = len(need)
    if n == 0:
        line = "Nothing needs you." + (f" {len(waiting)} {'waits' if len(waiting) == 1 else 'wait'} on others." if waiting else "")
        nxt = None
    else:
        first = need[0]
        head = " ".join(str(first.get("header") or first.get("title") or "").split())
        line = f"{n} thing{'s' if n != 1 else ''} {'needs' if n == 1 else 'need'} you."
        if late:
            line += f" {len(late)} {'is' if len(late) == 1 else 'are'} late or due today."
        line += f" Next: {head}" + ("" if head[-1:] in ".?!" else ".")
        nxt = {"id": first.get("id"), "header": head}
    if done_for_you:
        line += f" {done_for_you} done for you today."
    return {"line": dates.show(line, today), "need_you": n, "late_or_due": len(late), "clear": n == 0, "next": nxt,
            "waiting_on_others": len(waiting), "done_for_you": int(done_for_you or 0)}
