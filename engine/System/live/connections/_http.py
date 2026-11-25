"""Small web calls for connections: https only, JSON in and out, a few patient retries.

Nothing here logs or prints a header, a token or a body."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 60


def _no_change(url):
    """While a replay runs, only reading is allowed: every call that sends or changes something at a service is refused here,
    below every connection type. The one form post kept is a sign-in's token renewal, which reading needs."""
    import os
    import sys
    if os.environ.get("ASSISTANT_REPLAY") != "1":
        return
    if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import replay_guard
    replay_guard.refuse(f"a change at {urllib.parse.urlsplit(url).netloc}")


class Refused(RuntimeError):
    """The service answered with an error. .status is its number; the text never holds a token."""

    def __init__(self, status, text):
        super().__init__(f"{status}: {text[:300]}")
        self.status = status


def _open(req, tries=3):
    if not req.full_url.startswith("https://"):
        raise ValueError("connections only call https addresses")
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            body = e.read()
            if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                wait = e.headers.get("Retry-After")
                time.sleep(min(int(wait), 30) if wait and wait.isdigit() else 2 * (attempt + 1))
                continue
            raise Refused(e.code, body.decode("utf-8", "replace")) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt == tries - 1:
                raise RuntimeError(f"could not reach {urllib.parse.urlsplit(req.full_url).netloc}: {e}") from None
            time.sleep(2 * (attempt + 1))


def _headers(token, extra=None):
    h = {"Accept": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    h.update(extra or {})
    return h


def get_json(url, token=None, params=None, headers=None):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(
            {k: v for k, v in params.items() if v is not None}, doseq=True)
    _status, body = _open(urllib.request.Request(url, headers=_headers(token, headers)))
    return json.loads(body.decode("utf-8")) if body else {}


def post_form(url, fields):
    if not urllib.parse.urlsplit(url).path.endswith("/token"):     # a sign-in's token renewal is the one post a read needs
        _no_change(url)
    data =urllib.parse.urlencode({k: v for k, v in fields.items() if v is not None}).encode()
    req = urllib.request.Request(url, data=data, headers=_headers(None, {"Content-Type": "application/x-www-form-urlencoded"}))
    _status, body = _open(req, tries=2)
    return json.loads(body.decode("utf-8")) if body else {}


def post_json(url, token, obj, ok=(200, 201, 202, 204)):
    """Post JSON once (never retried: a send must not go twice). Returns (status, parsed body or {})."""
    _no_change(url)
    req =urllib.request.Request(url, data=json.dumps(obj).encode("utf-8"),
                                 headers=_headers(token, {"Content-Type": "application/json"}))
    status, body = _open(req, tries=1)
    if status not in ok:
        raise Refused(status, body.decode("utf-8", "replace"))
    try:
        return status, json.loads(body.decode("utf-8")) if body else {}
    except ValueError:
        return status, {}


def call_json(method, url, token, obj=None, ok=(200, 201, 202, 204), headers=None):
    """One PATCH, POST or DELETE with a JSON body, never retried (a change to the owner's mail is made once).
    Returns (status, parsed body or {})."""
    _no_change(url)
    data = json.dumps(obj).encode("utf-8") if obj is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers=_headers(token, dict({"Content-Type": "application/json"}, **(headers or {}))))
    status, body = _open(req, tries=1)
    if status not in ok:
        raise Refused(status, body.decode("utf-8", "replace"))
    try:
        return status, json.loads(body.decode("utf-8")) if body else {}
    except ValueError:
        return status, {}


def post_raw(url, token, data, content_type, ok=(200, 201, 202, 204)):
    """Post bytes once (never retried: a send must not go twice). Returns (status, parsed body or {})."""
    _no_change(url)
    req =urllib.request.Request(url, data=data, headers=_headers(token, {"Content-Type": content_type}))
    status, body = _open(req, tries=1)
    if status not in ok:
        raise Refused(status, body.decode("utf-8", "replace"))
    try:
        return status, json.loads(body.decode("utf-8")) if body else {}
    except ValueError:
        return status, {}
