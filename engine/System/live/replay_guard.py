r"""The replay's hard stop on everything that goes out.

While the day-by-day rebuild (replay.py) runs, ASSISTANT_REPLAY is "1" in its process and in every program it starts. Every
function that sends, posts, alerts, answers an invite, changes the owner's mail at the provider, or starts or takes over the
texts link calls refuse() first, and refuse() raises while the flag is on. The flag belongs to the replay's own process
tree only: the owner's own presses on his page (another process) are never blocked by it.
"""
import os

FLAG = "ASSISTANT_REPLAY"


class Refused(RuntimeError):
    """Raised by an outbound function while a replay runs."""


def on():
    return os.environ.get(FLAG) == "1"


def refuse(what):
    """Raise when a replay is running; nothing otherwise."""
    if on():
        raise Refused(f"refused during the replay: {what}. Nothing goes out while the history is being rebuilt.")


def _running_file():
    import paths
    return os.path.join(paths.STATE, "replay", "running.json")


def home_running():
    """True from the replay's prepare until it reaches today: a mark in the home that every program on the computer sees."""
    return os.path.isfile(_running_file())


def import_blocked():
    """True in any program other than the replay itself while a replay is under way: nothing is imported beside it (the
    page's Refresh, a search at the mail service, the texts link). The owner's own sends and answers are not imports."""
    return home_running() and not on()


def mark_running(running):
    path = _running_file()
    if running:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"why": "the day-by-day rebuild is under way: nothing is imported beside it"}')
    elif os.path.isfile(path):
        os.replace(path, path + ".ended")


def install():
    """Under the replay flag, this program's web opener refuses every call that sends or changes something (anything but a
    plain read, and a sign-in's token renewal, which reading needs). It sits under every caller, so a mod or any other
    addition that posts on its own is refused too, without naming it. Done once, by common at import."""
    if not on():
        return
    import urllib.parse
    import urllib.request
    opener = urllib.request.urlopen
    if getattr(opener, "replay_guarded", False):
        return

    def guarded(url, *a, **k):
        req = url if isinstance(url, urllib.request.Request) else None
        full = req.full_url if req else str(url)
        data = req.data if req else (a[0] if a else k.get("data"))
        method = (req.get_method() if req else ("POST" if data is not None else "GET")).upper()
        if method not in ("GET", "HEAD") and not urllib.parse.urlsplit(full).path.endswith("/token"):
            refuse(f"a {method} to {urllib.parse.urlsplit(full).netloc}")
        return opener(url, *a, **k)
    guarded.replay_guarded = True
    urllib.request.urlopen = guarded
