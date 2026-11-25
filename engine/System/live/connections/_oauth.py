r"""Signing in to a provider the owner already has an account with.

The owner signs in on the provider's own page in their own browser. The
assistant never sees, asks for or stores a password: the provider hands back a
long-lived sign-in (a refresh token) which goes straight into the locked key
store. Each pass trades it for a short-lived pass (an access token) that is
kept only in memory.

    sign_in(...)     opens the browser, waits for the owner, returns the provider's answer
    access(...)      a fresh short-lived pass for one connection, saving a renewed sign-in if one came back
"""
import base64
import hashlib
import http.server
import secrets
import threading
import urllib.parse
import webbrowser

from . import _http

WAIT_SECONDS = 600
DONE_PAGE = ("<html><body style='font-family:sans-serif;margin:3em'><h2>{}</h2>"
             "<p>You can close this tab and go back to the setup window.</p></body></html>")


class SignInFailed(RuntimeError):
    pass


def sign_in(auth_url, token_url, client_id, scopes, client_secret=None, extra=None, say=print):
    """The provider's standard sign-in for a program on the owner's own computer: the browser
    opens the provider's page, the owner signs in and agrees, and the provider sends a one-time
    code back to this computer only. Returns the provider's token answer (a dict)."""
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    state = secrets.token_urlsafe(24)
    got = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            if q.get("state", [""])[0] != state:
                self.send_response(400)
                self.end_headers()
                return
            got["code"] = q.get("code", [None])[0]
            got["error"] = q.get("error_description", q.get("error", [None]))[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(DONE_PAGE.format("Signed in." if got["code"] else "The sign-in did not finish.").encode())

        def log_message(self, *_a):     # never write the address (it carries the code) anywhere
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    server.timeout = 1
    redirect = f"http://localhost:{server.server_address[1]}"
    params = {"client_id": client_id, "response_type": "code", "redirect_uri": redirect, "scope": " ".join(scopes),
              "state": state, "code_challenge": challenge, "code_challenge_method": "S256", **(extra or {})}
    url = auth_url + "?" + urllib.parse.urlencode(params)
    say("Your browser is opening the provider's sign-in page. Sign in there and agree; this window waits.")
    threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()
    waited = 0
    try:
        while "code" not in got and waited < WAIT_SECONDS:
            server.handle_request()
            waited += 1
    finally:
        server.server_close()
    if not got.get("code"):
        raise SignInFailed(got.get("error") or "nobody finished signing in within ten minutes")
    answer = _http.post_form(token_url, {"grant_type": "authorization_code", "code": got["code"],
                                         "redirect_uri": redirect, "client_id": client_id,
                                         "client_secret": client_secret, "code_verifier": verifier})
    if not answer.get("refresh_token"):
        raise SignInFailed("the provider did not hand back a lasting sign-in; sign in again and agree to every box")
    return answer


_PASSES = {}                    # (token url, client, scope, a fingerprint of the sign-in) -> (good until, short-lived pass)
PASS_MARGIN = 120               # seconds before its end a kept pass is no longer handed out


def access(conn, token_url, client_id, client_secret=None, scope=None):
    """A short-lived pass for this connection, kept in this process until shortly before it runs out, so each call to
    the mail service does not first ask for a new one. A renewed sign-in, when the provider sends one, replaces the
    stored one."""
    import connections
    import time
    held = connections.secret(conn, "refresh")
    if not held:
        raise SignInFailed("this account has not been signed in on this computer yet (open Setup and connect it)")
    kept = _PASSES.get((token_url, client_id, scope, hashlib.sha256(held.encode()).hexdigest()))
    if kept and time.time() < kept[0]:
        return kept[1]
    try:
        answer = _http.post_form(token_url, {"grant_type": "refresh_token", "refresh_token": held,
                                             "client_id": client_id, "client_secret": client_secret, "scope": scope})
    except _http.Refused as e:
        if e.status in (400, 401):
            raise SignInFailed("the provider no longer accepts this sign-in; open Setup and sign this account in again") from None
        raise
    if answer.get("refresh_token") and answer["refresh_token"] != held:
        connections.put_secret(conn, "refresh", answer["refresh_token"])
    if not answer.get("access_token"):
        raise SignInFailed("the provider gave no pass for this sign-in")
    if answer.get("scope"):
        connections.note_granted(conn, answer["scope"])
    try:
        life = float(answer.get("expires_in") or 0)
    except (TypeError, ValueError):
        life = 0
    if life > PASS_MARGIN:
        now_held = answer.get("refresh_token") or held
        _PASSES[(token_url, client_id, scope, hashlib.sha256(now_held.encode()).hexdigest())] = (
            time.time() + life - PASS_MARGIN, answer["access_token"])
    return answer["access_token"]
