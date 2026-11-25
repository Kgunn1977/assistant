# Connections: the shape of a connection type, and how to add one

A connection type is one Python file that knows how to reach one kind of account. The types that ship are in this folder:

| File | What it reaches | Kind |
|---|---|---|
| microsoft_mail.py | Microsoft 365 work or school mail | email |
| google_mail.py | Gmail and Google Workspace mail | email |
| google_calendar.py | Google Calendar | calendar |

## Where things live

- **General (ships):** the type files here. They name no person, address or company.
- **Personal (stays with the owner):** `<home>\personal\connections.json` lists which accounts are connected: for each, an id (`c1`, `c2`, ...), its type, its label or address, and whether it is on. It also holds the owner's own registration ids with each provider (`apps`). It never holds a secret.
- **Secrets:** every sign-in, token and app secret is in the locked key store `<home>\personal\keys.dat`, written and read only through `connections.put_secret` and `connections.secret`. Windows locks it to the owner's account on that computer.
- **A type made for one owner** goes in `<home>\taught\connections\<type>.py`. It is found and run exactly like the ones here.

## What a type file must have

```python
TYPE = "example_mail"          # the file's own name without .py
NAME = "Example mail"          # plain words, shown in the setup interview
KIND = "email"                 # what it brings in: email, calendar, sms, or a kind of its own (see "Kinds" below)
CAN_SEND = False               # True only for mail types that also have send()
ASKS = [                       # what Setup asks the owner to type for each account; may be []
    {"key": "token", "label": "Access token", "secret": True, "help": "Where to find it."},
    {"key": "folder", "label": "Folder", "folder": True},     # a folder picker instead of a box
]
SETUP = """Plain steps a non-programmer can follow click by click..."""

def connect(conn, say=print, answers=None):
    """Sign the account in or check what was typed. Store every secret with
    connections.put_secret(conn, "name", value). Fill in conn["label"] (and conn["address"] for
    mail). Return conn. Raise with a plain sentence when it did not work."""

def check(conn):
    """One harmless read. Return one plain line. Raise when the connection does not work."""

def gather(conn, ctx):
    """Read what is new and store it through connections._store. Return one plain line
    such as "3 new". A line starting "DEGRADED: " is shown to the owner as a warning, not a failure."""
```

Optional:

```python
APP = "provider"               # accounts of this provider share one registration the owner makes once
APP_ASKS = [...]               # what that registration needs, same shape as ASKS; asked only once
def send(conn, to, cc, subject, html, files=()):   # mail types with CAN_SEND: a plain new email (older types)
def people(conn):              # {id: {"name", "email", "is_bot", "deleted"}} so messages can name their author
def calendars(conn):           # calendar types: [(calendar name, True if it is the account's own)]
```

Mail types, for the page's Mail part (each is optional; a missing one makes the page say plainly that this mailbox cannot do it):

```python
CAN_ACT = ("archive", "trash", "label", "read")   # the changes this type can make on the owner's press
ACT_SCOPE = "permission name"  # the sign-in permission those changes need; when the provider says the sign-in lacks it, the page says so
def send_mime(conn, raw, thread_id=None):   # send one complete email the engine built (To, Cc, Bcc, reply headers, files); preferred over send()
def sync(conn, ctx, end):   # the slow work after every mailbox's new mail, until time `end`: changes made elsewhere (Gmail history, Graph delta), the folder list, the backfill of state; returns a plain line
# act(...) also takes what == "move" (label = the destination folder or label id): Graph /move, or Gmail add that label and remove INBOX
# gather() stores the OLDEST emails not yet held, at most ctx.limit; the mark moves only to the newest fetched (never past mail not fetched)
def act(conn, provider_id, what, label=None, thread_id=None):   # archive | trash | read | unread | label | unlabel; returns the email's id afterwards
def labels(conn):              # the owner's label (or category) names
def search(conn, words, most=25):   # the service's own search over the whole mailbox: provider ids
def fetch(conn, provider_ids):      # store those emails the way gather does
def headers(conn, provider_id):     # {"header_id", "refs", "cc", "from_name", "thread"} for a reply or forward
def attachment(conn, provider_id, name):   # one attachment's bytes, or None
```

For the setup's envelope catalog and Contacts (each optional; a type without them reaches back only as far as it downloads):

```python
def envelopes(conn, since, cursor, end):   # one portion of the catalog (catalog.py): headers only, no body, until time `end`;
                                            # returns {"rows": [{"provider_id", "ts", "direction", "from_key", "from_name", "to", "subject", "thread_id"}],
                                            #          "cursor": where to go on next time or None, "done": True when the span is all read}
def envelope_text(conn, provider_id):       # one message's plain text, read when a look-back needs it (never stored as a new message)
def address_book(conn):                     # the account's own contacts: [{"name", "emails", "phones"}]; raises when not allowed
```

For the day-by-day rebuild (replay.py), a type outside mail and calendar (an add-on chat type, say) reads its own day (optional; a type without it is left out of the rebuild):

```python
def replay_day(conn, start, end):   # store what falls in [start, end) through the shared writers; only read, never change anything;
                                    # returns (how many stored, [plain words for each part it could not read]); raises when the
                                    # service cannot be reached, so the day stops and is read again on continue
```

`act` raises an exception named `NotAllowed` when the sign-in lacks the permission; trash is always the service's own trash, never a deletion for good. `MailWriter.add(..., state={...})` keeps what the service says about each email (unread, inbox, trashed, labels, cc, the sender's name, its Message-ID and References).

`ctx` carries `run_id`, `dry_run` (fetch but store nothing), `limit` (most messages per account per pass) and `events` (calendar types append their rows here; the caller stores the whole window at once).

## Storing what was read (connections._store)

A type fetches; the shared writers store, so every source obeys the same rules (nothing stored twice, signature pictures left out, local wall-clock times).

- `since(name, days)`: how far back to read. Mail uses the name `email:<address>`.
- `MailWriter(address)`: `.add(provider_id, when, "in" or "out", from, to, subject, body, folder=, thread_id=, attachments=[(file name, bytes)])` for each message, then `.commit()`. Filter attachments with `is_decoration` first.
- `chat_messages(channel, account, rows, watermark_name)` for chat-style sources.
- `calendar_events(rows, prune)` is called for you; calendar types only append to `ctx.events`.
- `text_messages(rows)` for texts (from the Messages extension) and their pictures.

## Web calls and sign-in

- `connections._http`: `get_json`, `post_form`, `post_json`. https only. Never log a header, token or body.
- `connections._oauth.sign_in(...)` opens the provider's own sign-in page in the owner's browser and returns the provider's answer; store its `refresh_token` with `put_secret(conn, "refresh", ...)`. `connections._oauth.access(conn, token_url, client_id, ...)` trades it for a short-lived pass at each run and saves a renewed sign-in if the provider sends one.
- The assistant never asks for, sees or stores a password.

## Kinds

`KIND` decides when the type is read and where its messages land. The pass reads each kind the owner has on, one kind at a time (`run.py --kind <kind>`), every connection of that kind on its own so one failing never stops the rest. A new type should use the existing kind closest to it: `email` for anything with a subject, sender and body; a kind of its own for chat rooms and direct messages (with WORD and TITLE, as below); `sms` for short person-to-person messages; `calendar` for events. A genuinely new kind also needs a seconds limit in `limits.SOURCE` (it gets 120 seconds otherwise).

## Rules every type keeps

1. Read only, except `send()` and `send_mime()`, which are called only by `send.py` for an email the owner sent themself, and `act()`, which is called only for the owner's own Archive, Delete, Label or Mark read press on the page.
2. No secret in `connections.json`, in a returned line, in an exception's words, in a log or in anything printed.
3. One account failing raises; it never guesses, retries forever, or reports success.
4. `SETUP` is complete: what to create at the provider, every click, where each value goes, and what the common failures mean.

## Trying a type

```
python run.py --check                      one harmless read on every connection
python run.py --kind email --dry-run       fetch and report, store nothing
python run.py --kind email --only c3       one connection
```
