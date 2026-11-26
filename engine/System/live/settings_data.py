r"""Settings sent to the page as data, so the page draws any setting without knowing it beforehand.

ITEMS.md ("Design round 1", "Settings sent as data") is the shape. settings_page.py still holds every
rule and every check of a Save; this file only describes, in plain words, what settings_page.for_page()
already holds: for each setting its group, label, help words (a live line only), explanation (its (i) pop-up), kind of
control, choices, present value and whether a page may change it. A setting added later is one more entry here and the page shows it.
"""
import settings_page

ON_PC = "Paste this into Claude on your computer."


def commands(pc):
    """What is changed only with a command in Claude on the computer: a Tools entry each, its state now, and the exact command
    (each one a real command of the plugin: skills/change with its parts accounts, page and sending; skills/introduce;
    skills/roadmap-setup)."""
    accounts = "; ".join(f"{a.get('name')} ({a.get('health')})" for a in pc.get("accounts") or []) or "None yet"
    return [
        {"id": "accounts", "explain": "Connect, reconnect or remove a mail, calendar or text account. It shows which accounts are connected and whether each is working. Press Show the command, copy it and paste it into Claude on your computer.", "name": "Accounts", "now": "Connected: " + accounts,
         "words": "Connect, reconnect or remove a mail, calendar or text account.", "command": "/assistant:change accounts", "where": ON_PC},
        {"id": "sending", "explain": "Turns sending email from this page on or off. It shows On when email can go out, and email only goes out when you press Send. Press Show the command, copy it and paste it into Claude on your computer.", "name": "Sending email",
         "now": "On. Email goes out only when you press Send." if pc.get("sending") else "Off.",
         "words": "Turn sending email from this page on or off.", "command": "/assistant:change sending", "where": ON_PC},
        {"id": "page", "explain": "Opens this page from your phone, or moves it, and shows where it lives now. Press Show the command, copy it and paste it into Claude on your computer.", "name": "Page location", "now": pc.get("lives") or "This computer",
         "words": "Open this page from your phone, or move it.", "command": "/assistant:change page", "where": ON_PC},
        {"id": "projects", "explain": "Adds, changes or removes a project, and lists the ones added. Press Show the command, copy it and paste it into Claude on your computer.", "name": "Projects", "now": "Added: " + (", ".join(pc.get("projects") or []) or "none yet"),
         "words": "Add, change or remove a project.", "command": "/assistant:introduce", "where": ON_PC},
        {"id": "roadmaps", "explain": "Adds a roadmap page to a project, and lists the roadmaps shown. Press Show the command, copy it and paste it into the project's Claude session, not the one on your computer.", "name": "Roadmaps", "now": "Shown: " + (", ".join(pc.get("roadmaps") or []) or "none"),
         "words": "Add a roadmap page to a project.", "command": "/assistant:roadmap-setup",
         "where": "Paste this into the project's Claude session."},
    ]
GROUPS = (("you", "Profile", True), ("watch", "Sources", True), ("calendar", "Calendar", True), ("alerts", "Notifications", True),
          ("page", "Appearance", True), ("signin", "Sign-in", True),
          ("filter", "Filters", True), ("acting", "Approvals", True), ("voice", "Writing style", True),
          ("review", "Weekly review", True),
          ("learning", "Learning levels", True),
          ("thinking", "AI and usage", True))


def _c(pairs):
    return [{"value": v, "label": w} for v, w in pairs]


def _one(group, sid, label, control, value, help="", choices=None, can_change=True, explain="", **more):
    out = {"group": group, "id": sid, "label": label, "help": help, "explain": explain, "control": control, "value": value,
           "can_change": bool(can_change)}
    if choices is not None:
        out["choices"] = choices
    out.update(more)
    return out


def _kinds():
    import standing
    return standing.KINDS


def _areas():
    import standing
    return standing.areas()


def defs(now=None):
    """{"groups": [...], "settings": [...]} from the present values (now: for_page()'s result, read once)."""
    s = now or settings_page.for_page()
    y, w, cal, al, pg, si, tk, pc = (s[k] for k in ("you", "watch", "calendar", "alerts", "page", "signin", "thinking", "pc_only"))
    f = s.get("filter") or {}
    ac, rv = s.get("acting") or {}, s.get("review") or {}
    vo = s.get("voice") or {}
    cals = cal.get("calendars") or []
    out = [
        _one("you", "first_name", "First name", "text", y["first_name"],
             explain="Your first name. I use it when I talk to you, when I read your mail, and to spot messages about you. It's required and starts the next time I check for messages."),
        _one("you", "full_name", "Full name", "text", y["full_name"],
             explain="Your whole name, so I can tell when a message names you and which text conversation is your notes to yourself. If it's empty, I use your first name. Starts the next time I check for messages."),
        _one("you", "about", "About me", "long_text", y["about"],
             explain="A sentence or two about what you do and who matters to you. I read it whenever I sort new mail, write cards or answer you in Talk to your assistant, so a clearer sentence gives better cards. Starts the next time I check for messages."),
        _one("you", "page_title", "Page title", "text", y["page_title"],
             explain="The big heading at the top of your page and the name on the browser tab. If you leave it empty it reads your first name followed by 's desk'. Changes at once."),
        _one("you", "page_subtitle", "Page subtitle", "text", y["page_subtitle"],
             explain="A short line shown before the date and time under the heading. Leave it empty for none. Changes at once."),
        _one("you", "areas", "Areas", "list", y["areas"],
             explain="The parts of your life every card is filed under, one per line, such as a company or a project. I pick one for each new card, and they are the choices for Group cards by Area and for approvals. Personal and System always stay. Starts the next time I check for messages."),

        _one("watch", "important", "Important topics", "list",
             w["important"],
             explain="The kinds of things that deserve a phone notification, one per line. I mark a card important only if it matches one of these, and strictly, so be specific. An important card goes to the top of the page and sends a notification if Phone notifications are on. Starts the next time I check for messages."),
        _one("watch", "own_domains", "My email domains", "list", w["own_domains"],
             explain="Mail domains that are yours, one per line, such as yourcompany.com. Mail from them is never junk, never ignored and can't be marked junk from a card. I add the domains of your connected work mailboxes myself. Starts the next time I check for messages."),
        _one("watch", "ignore_senders", "Ignored senders", "list", w["ignore_senders"],
             explain="Addresses or whole domains, one per line, whose email makes no card and no notification. Your own domains can't be added here. Starts the next time I check for messages."),
        _one("watch", "keep_words", "Words that keep a mailing", "list", w.get("keep_words") or [],
             explain="Words such as bill, invoice or order. I normally hide a mailing with an unsubscribe link as junk, but I keep and read one whose subject has one of these words or looks like a security or sign-in notice. Starts the next time I check for messages."),
        _one("watch", "paused", "Check for new messages", "choice", bool(w["paused"]),
             choices=_c(((False, "On"), (True, "Off"))), since=w.get("paused_since"),
             explain="On (the normal state): I check for new mail, texts and other messages and read them. Off: nothing new comes in until you turn it back on, though your answers on cards still work. It takes effect at once, and after turning it on I check again within the Check every time."),
        _one("watch", "every_minutes", "Check every", "choice", w["every_minutes"],
             choices=_c(((15, "Every 15 minutes"), (30, "Every 30 minutes"), (60, "Every hour"))),
             explain="How often I check for new mail, texts and messages: every 15 minutes (the default), every 30 minutes or every hour. A longer gap uses less of your Claude plan's limit. Starts the next time I check for messages."),
        _one("watch", "texts_browser", "Google Messages in a browser", "choice", w.get("texts_browser") or "take_back",
             choices=_c((("take_back", "Reconnect right away"), ("let_browser", "Let the browser keep it until I check again"))),
             explain="Only one place at a time can hold your Google Messages sign-in. Reconnect right away (the default): I take it back as soon as a browser takes it. Let the browser keep it: texts pause here until I check again, then I take it back and catch up; this takes effect at once."),

        _one("calendar", "calendars", "Calendars on Today", "checks", [c["name"] for c in cals if c.get("on")],
             "" if cals else "No calendar connected. On your computer, type /assistant:change accounts in Claude.",
             choices=_c((c["name"], c["name"]) for c in cals),
             explain="Which of your calendars show in the Today box. Tick the ones you want; the colored boxes in the Calendar section show or hide calendars there separately. Takes effect at once."),

        _one("alerts", "on", "Phone notifications", "choice", bool(al["on"]),
             choices=_c(((False, "Off"), (True, "On"))),
             explain="Off by default. On: I make a private name for the free ntfy phone app and send one notification for each important card. Off clears that name; either takes effect at once."),
        _one("alerts", "mail", "New mail", "choice", al["mail"],
             choices=_c((("matters", "Important only"), ("every", "All new mail"), ("none", "Off"))),
             explain="Works only while Phone notifications are on. Important only (the default) notifies you of mail from priority senders, mail in a conversation you've written in, and mail on an important card; All new mail notifies you of every new unread inbox email; Off sends none. Several at once make one notification, quiet hours apply, and it takes effect at once."),
        _one("alerts", "topic", "Private name for the phone app", "words", al["topic"],
             "In the ntfy app, tap + and enter this name exactly. Anyone who knows it can read your notifications.", can_change=False,
             explain="The private name to enter in the ntfy phone app. I make it when you turn Phone notifications on, and you can't edit it here. Anyone who knows it could read your notifications."),
        _one("alerts", "quiet_from", "Quiet hours start", "time", al["quiet_from"],
             explain="The time when phone notifications stop, for example 22:00. It works with the end time, so set both or neither. Takes effect at once."),
        _one("alerts", "quiet_to", "Quiet hours end", "time", al["quiet_to"],
             explain="The time when notifications start again. No phone notifications are sent between the start and end times, and important ones that came in meanwhile are sent together as one when the hours end. Both empty means no quiet hours. Takes effect at once."),

        _one("page", "theme", "Theme", "choice", pg["theme"],
             choices=_c((("auto", "Same as device"), ("light", "Light"), ("dark", "Dark"))),
             explain="Light or dark. Same as device (the default) follows your phone or computer setting. Takes effect at once, on every device."),
        _one("page", "look", "Style", "choice", pg.get("look") or "glass",
             choices=_c((("glass", "Glass (Apple Liquid Glass)"), ("workshop", "Workshop (orange)"),
                         ("broadsheet", "Broadsheet (newspaper)"),
                         ("dense", "Dense (Linear)"),
                         ("expressive", "Expressive (Material 3)"), ("tiles", "Tiles (Bento grid)"),
                         ("paper", "Paper (Things 3)"), ("retro", "Retro (Classic Windows)"), ("soft", "Soft (Tactile)"),
                         ("panel", "Panel (Teenage Engineering)"), ("starship", "Starship (Star Trek TNG)"),
                         ("terminal", "Terminal (Severance)"), ("greenscreen", "Green screen (Fallout)"),
                         ("grid", "Grid (Tron: Legacy)"), ("frost", "Frost (The Expanse)"),
                         ("monolith", "Monolith (2001)"), ("haze", "Haze (Blade Runner 2049)"))),
             explain="The colors, fonts and spacing of the whole page: Glass (Apple Liquid Glass, dark, the default), Workshop (orange) or Broadsheet (newspaper), and fourteen more, each named for where it came from: Dense (Linear), Expressive (Material 3), Tiles (Bento grid), Paper (Things 3), Retro (Classic Windows), Soft (Tactile), Panel (Teenage Engineering), Starship (Star Trek TNG), Terminal (Severance), Green screen (Fallout), Grid (Tron: Legacy), Frost (The Expanse), Monolith (2001) and Haze (Blade Runner 2049). Your Theme choice still applies. Takes effect at once, on every device."),
        _one("page", "text_size", "Text size", "choice", pg["text_size"],
             choices=_c((("small", "Small"), ("normal", "Normal"), ("large", "Large"))),
             explain="Small, Normal (the default) or Large for the whole page. Takes effect at once, on every device."),
        _one("page", "order", "Page layout", "order", pg["order"], hidden=pg["hidden"], titles=pg["titles"], open_if_filled=pg["open_if_filled"],
             explain="Where each part of the page sits (top, left, right or bottom) by dragging it, the heading you give it, whether it shows at all, and whether it hides itself while empty. Only Errors hides itself while empty by default. A part holding something marked important always shows. Takes effect at once, on every device."),
        _one("page", "feed_order", "Card order", "rank", pg["feed_order"],
             choices=_c((("needs", "Needs you"), ("waiting", "Waiting and Someday"), ("fyi", "FYI"), ("done", "Done"))),
             explain="Which kind of card comes first under All in Cards: Needs you, Waiting and Someday, FYI or Done, while Group by kind is on at the top of Cards. Within a kind the cards follow Sort by there, and Hidden is always last. Used as soon as you save."),
        _one("page", "done_days", "Keep Done cards for", "choice", pg["done_days"],
             choices=_c(((3, "3 days"), (7, "7 days"), (14, "14 days"), (30, "30 days"))),
             explain="How long cards stay under the Done filter in Cards after they are finished: 3, 7 (the default), 14 or 30 days. Starts the next time I check for messages."),
        _one("page", "snooze_days", "Default snooze date", "choice", pg["snooze_days"],
             choices=_c(((0, "None"), (1, "Tomorrow"), (3, "In 3 days"), (7, "In a week"))),
             explain="The day filled in when you press Snooze on a card: None (the default), Tomorrow, in 3 days or in a week. You can still pick another day on the card. Takes effect at once."),
        _one("page", "clock", "Time format", "choice", pg["clock"],
             choices=_c((("12", "12-hour (3:05 PM)"), ("24", "24-hour (15:05)"))),
             explain="Shows every time on the page as 12-hour (3:05 PM, the default) or 24-hour (15:05). Takes effect at once."),
        _one("page", "mail_pictures", "Load images in email", "choice", pg["mail_pictures"],
             choices=_c((("show", "On"), ("hide", "Off"))),
             explain="On (the default) shows pictures in email. Off hides them until you press Show pictures on that email, because senders can tell when their images load. Takes effect at once."),

        _one("page", "later_offers", "Snooze options", "checks", pg.get("later_offers") or [],
             choices=_c((("today", "Later today"), ("tomorrow", "Tomorrow"), ("next_week", "Next week"), ("date", "A date"),
                         ("someday", "Someday"))),
             explain="Which choices the Snooze button offers: Later today, Tomorrow, Next week, A date and Someday. All five are on by default and at least one must stay on. Takes effect at once."),

        _one("page", "group_by", "Group cards by", "choice", pg.get("group_by"),
             choices=_c((("nothing", "None"), ("sender", "Sender"), ("area", "Area"), ("conversation", "Conversation"))),
             explain="None (the default) keeps one list. Sender, Area or Conversation puts cards under a heading for each, with a count. Takes effect at once."),

        _one("filter", "strict", "Filter strength", "choice", f.get("strict"),
             choices=_c((("show_more", "Show more"), ("balanced", "Balanced"), ("needs_me", "Only what needs me"))),
             explain="How much mail reaches your page as cards. Show more shows anything you might want, including every note a person wrote you, and a new setup starts here; Balanced shows what asks something of you or what you'd plainly want to know (a setup made earlier keeps its choice, Balanced if never changed); Only what needs me shows only what you must decide, answer or do. It starts the next time I check for messages, and anything I hide is under Hidden in Cards, with the reason."),
        _one("filter", "rules", "Rules", "rules", f.get("rules") or [],
             ways=_c((("show_less", "Show less"), ("always_show", "Always show"), ("card_rule", "How cards are written"))),
             explain="Your own rules, one plain sentence each with a line on why (you can change it), saved as Show less, Always show or How cards are written. I follow them when I sort mail and write cards, and rules you approve on a card or give me in chat are saved here; each can be paused or removed. Starts the next time I check for messages."),
        _one("filter", "always_through", "Priority senders", "list", f.get("always_through") or [],
             explain="Names, addresses or domains, one per line, whose messages I never hide. A message from them always becomes a card and counts for important-sender notifications. Starts the next time I check for messages."),
        _one("filter", "nothing_needed", "Mail needing no action", "choice", f.get("nothing_needed"),
             choices=_c((("line", "One line, under FYI"), ("full", "A full card"), ("hide", "Hide (kept under Hidden)"))),
             explain="What happens to cards that only inform you. One line, under FYI (the default) shows a single line, A full card shows them in full, and Hide puts them under Hidden. Starts the next time I check for messages."),
        _one("filter", "first_time", "First-time senders", "choice", f.get("first_time"),
             choices=_c((("show", "Show"), ("ask_once", "Ask first"), ("hold", "Hide"))),
             explain="The first email from someone who has never written to you and isn't in your contacts. Show (the default) treats it normally, Ask first hides it until a card asks you once whether to show their mail, and Hide puts it under Hidden. Starts the next time I check for messages."),
        _one("filter", "newsletters", "Newsletters and promotions", "choice", f.get("newsletters"),
             choices=_c((("never", "Hide"), ("show", "Show"))),
             explain="Show reads it like any other mail. A new setup starts on Show, so nothing is hidden at first. Hide puts mail with an unsubscribe link under Hidden as junk without my reading it, except mail from people you know, your own domains, or a subject with one of your keep words (a setup made earlier stays on Hide until you change it); it starts the next time I check for messages."),
        _one("filter", "kept_mailings", "Kept mailings", "choice", f.get("kept_mailings"),
             choices=_c((("show_each", "Show all"), ("only_due_or_wrong", "Only if due or wrong"))),
             explain="Mailings your keep words saved; it matters only if you have keep words under Sources. Show all (the default) makes a card for each, and Only if due or wrong makes one only when something is due, late, failed or not as expected. Starts the next time I check for messages."),
        _one("filter", "notices", "Automated notices", "choice", f.get("notices"),
             choices=_c((("only_failed", "Only failures"), ("show_each", "Show all"))),
             explain="Messages from apps and systems that no person wrote. Show all makes a card for each, and a new setup starts here; Only failures makes one only when something failed, was refused or needs action (a setup made earlier stays on it until you change it). Starts the next time I check for messages."),
        _one("filter", "copied_only", "Mail where I am only copied", "choice", f.get("copied_only"),
             choices=_c((("only_if_named", "Only if I am named"), ("fyi", "Under FYI"), ("show", "Show"))),
             explain="Mail where none of your addresses is among the To addresses. Show treats it normally, and a new setup starts here; Only if I am named hides it unless it names you (a setup made earlier stays on it until you change it); Under FYI shows it as information only. Starts the next time I check for messages."),
        _one("filter", "unknown_texts", "Texts from unknown numbers", "choice", f.get("unknown_texts"),
             choices=_c((("fyi", "Under FYI"), ("show", "Show"), ("hide", "Hide"))),
             explain="Texts from numbers that aren't in your contacts. Under FYI (the default) shows them as information only, Show treats them normally, and Hide puts them under Hidden. Starts the next time I check for messages."),
        _one("filter", "short_texts", "Texts from short numbers", "choice", f.get("short_texts"),
             choices=_c((("show", "Show"), ("hide", "Hide"))),
             explain="Texts from a short number (6 digits or fewer), the kind used for codes and ads. Show reads them like any other text, and a new setup starts here; Hide puts them under Hidden as junk without my reading them, except one about fraud, security, a payment, a card or an alarm (a setup made earlier stays on Hide until you change it). Starts the next time I check for messages."),
        _one("filter", "show_why", "Show \"Here because\" on cards", "choice", f.get("show_why"),
             choices=_c((("on", "On"), ("off", "Off"))),
             explain="On (the default) shows a short line on each card saying why it's on your page. Off removes that line. Changes when the page next refreshes."),
        _one("filter", "waiting_back_days", "Return waiting cards after", "choice", f.get("waiting_back_days"),
             choices=_c(((2, "2 working days"), (3, "3 working days"), (5, "5 working days"), (7, "7 working days"), (0, "Never"))),
             explain="A card waiting on someone else comes back to you after this many working days with no reply, or sooner if they write: 2, 3 (the default), 5 or 7 days, or Never. Starts the next time I check for messages."),
        _one("filter", "old_card_days", "Ask about old cards after", "choice", f.get("old_card_days"),
             choices=_c(((7, "7 days"), (14, "14 days"), (30, "30 days"), (0, "Never"))),
             explain="After a card sits untouched this long (7, 14 by default, or 30 days, or Never), one card lists the old ones and asks what to do with each; the weekly review uses the same number. I mark nothing Done unless you say so. Starts the next time I check for messages."),

        _one("signin", "days", "Stay signed in for", "choice", si["days"],
             choices=_c(((1, "1 day"), (7, "7 days"), (30, "30 days"), (90, "90 days"))),
             explain="How long a browser stays signed in to your page: 1, 7, 30 or 90 days (the default). A browser you use regularly stays signed in, and one left idle this long must sign in again. It applies to sign-ins made after you save."),

        _one("acting", "ladder", "What I do without asking", "ladder", ac.get("ladder") or [],
             kinds=[{"kind": k, "label": v["label"], "what": v["what"]} for k, v in _kinds().items()],
             areas=_areas(), levels=_c((("ask", "Ask first"), ("tell", "Do it and notify me"), ("quiet", "Do it quietly"))),
             explain="Each line lets me do one kind of thing in one area without asking: mark cards Done that need nothing, or mark waiting cards Done that come back with no reply. Ask first changes nothing; Do it and notify me and Do it quietly start the next time I check for messages, and every use is listed with an Undo in Cards, under Done. Email replies can be paused or removed here but are only added from an offer card, and otherwise I always ask before sending."),
        _one("acting", "offer_after", "Suggest approvals after", "choice", ac.get("offer_after"),
             choices=_c(((3, "3 times"), (5, "5 times"), (10, "10 times"), (0, "Never"))),
             explain="After you do the same kind of thing in the same area this many times (3, 5 by default, or 10), a card asks if I may do it without asking. Never stops the offers. Starts the next time I check for messages."),
        _one("acting", "send_cap", "Daily send limit", "choice", ac.get("send_cap"),
             choices=_c(((1, "1 a day"), (3, "3 a day"), (5, "5 a day"), (10, "10 a day"))),
             explain="The most replies I may send in a day without asking: 1, 3 (the default), 5 or 10. Past it, drafts come to you as usual. Starts the next time I check for messages."),
        _one("review", "review_day", "Day", "choice", rv.get("review_day"),
             choices=_c((("fri", "Friday"), ("mon", "Monday"), ("tue", "Tuesday"), ("wed", "Wednesday"), ("thu", "Thursday"),
                         ("sat", "Saturday"), ("sun", "Sunday"), ("off", "Off"))),
             explain="The day I make your weekly review card, Friday by default, or Off for none. I make it from your own cards and calendar without using AI. It appears the first time I check for messages on or after the chosen day and time."),
        _one("review", "review_time", "Ready from", "time", rv.get("review_time"),
             explain="The time on that day when I make the review card (15:00 by default). Starts the next time I check for messages."),

        _one("voice", "level", "Tone", "choice", vo.get("level"),
             choices=_c((("choose", "Automatic"), ("casual", "Casual"), ("everyday", "Everyday"), ("formal", "Formal"))),
             explain="How formal drafted emails are. Automatic (the default) picks for each recipient: everyday for people you write to often, formal for someone new. Casual, Everyday and Formal fix it for every draft and change the greeting and sign-off that drafts start and end with. Used the next time a draft is written."),
        _one("voice", "learned", "Learned style", "words", vo.get("learned"),
             explain="How many of your sent messages I learned your style from, and when. You can't edit it here: I learn it only when you run it: press Learn style now or use the Writing style builder in Tools. Drafts use the saved voice file until you run it again; what your edits to my drafts taught goes into it then."),
        _one("voice", "greetings", "Greetings", "list", vo.get("greetings") or [],
             explain="How your drafts open, one per line. Only the first line is used, at every tone. If this is empty, I use the greeting I learned from your sent mail. Used the next time a draft is written."),
        _one("voice", "signoffs", "Sign-offs", "list", vo.get("signoffs") or [],
             explain="How your drafts close, one per line. Only the first line is used, at every tone. If this is empty, I use the sign-off I learned from your sent mail. Used the next time a draft is written."),
        _one("voice", "phrases", "Common phrases", "list", vo.get("phrases") or [],
             explain="Phrases you often use, one per line. Drafts use them where they fit. If this is empty, I use the phrases I learned from your sent mail. Used the next time a draft is written."),
        _one("voice", "never", "Phrases to avoid", "list", vo.get("never") or [],
             explain="Phrases drafts must not use, one per line. If this is empty, I avoid the stock phrases you never wrote. Used the next time a draft is written."),
        _one("voice", "styles", "How you write on each channel", "list", vo.get("styles") or [],
             explain="How you write email, texts and any other channel you connected, one line each, learned from what you sent and from how you change my drafts: how formal, about how long, how you open and how you sign off. Change a line and drafts on that channel follow it; empty the box and what was learned is used again. Used the next time a draft is written."),
        _one("voice", "people", "How you write to certain people", "list", vo.get("people") or [],
             explain="The people you write to differently from the rest, one line each, with their address or number in angle brackets and the channel after the comma. Change a line and drafts to them follow it; take a line out to stop it; empty the box and what was learned is used again. Used the next time a draft is written."),

        _one("thinking", "model", "AI model", "choice", tk["model"],
             choices=_c((m["id"], f"{m['words']} ({m['id']})") for m in tk.get("models") or []),
             explain="The AI model I use to sort new mail and write cards, on your Claude plan. Opus (the default) is the most careful; Sonnet is faster and cheaper, and Haiku is the fastest and cheapest. Starts the next time I check for messages."),
        _one("thinking", "daily_limit", "Daily limit", "number", tk["daily_limit"],
             f"AI uses so far today: {tk.get('runs_today', 0)}.", min=0, max=10000,
             explain="The most times I may use AI in a day; 0 (the default) means no limit, and the line under it shows today's count. At the limit I read nothing new until midnight: cards wait, and an answer you type is saved and read first the next day. Takes effect at once."),
        _one("thinking", "fast_sort", "Fast first look for plain junk", "choice", tk.get("fast_sort") or "off",
             choices=_c((("off", "Off"), ("on", "On"))),
             explain="On: a faster, cheaper AI hides what plainly needs nothing before the main AI reads the rest. Up to 150 each time I check, never from people you know or priority senders. Off is the default; On uses less but may hide something you wanted, which Hidden in Cards shows, and it starts the next time I check for messages."),

    ]
    out += learning(s.get("learning") or {})
    for x in out:           # "hidden" travels with the order control: one control on the page, two fields in a Save
        if x["id"] == "order":
            x["saves"] = ["order", "hidden", "titles", "open_if_filled"]
    try:        # each of the owner's mods with a Settings section of its own (mods.py)
        import mods
        groups = list(GROUPS) + [(g, w_, True) for g, w_ in mods.settings_groups()]
        out += mods.settings_defs()
    except Exception:  # noqa: BLE001  a mod's section never costs the page its settings
        groups = list(GROUPS)
    return {"groups": [{"id": g, "label": w_, "can_save": save} for g, w_, save in groups], "settings": out, "commands": commands(pc),
            "rule_book": rule_book(), "contacts": contacts()}


CONTACTS_EXPLAIN = ("Everyone you ever wrote to or heard from, in mail, texts and any other channel you connected, one-time senders "
                    "included, plus everyone in your phone's and your email accounts' address books. Each shows when you were last "
                    "in touch and how often, what is open between you both ways, the history (messages, cards and your decisions), "
                    "your own notes and what the assistant has learned about them. Your notes are saved with Save under them.")


def contacts():
    """Settings, Contacts (contacts_book.py): how many, with the part's (i) words. The people themselves are never sent in this
    block: the page asks for them a page at a time when Contacts is opened (api/contacts). Never costs the page its settings."""
    try:
        import contacts_book
        n = contacts_book.count()
    except Exception:  # noqa: BLE001
        n = 0
    return {"label": "Contacts", "explain": CONTACTS_EXPLAIN, "count": n, "page_size": 50}


RULE_BOOK_EXPLAIN = ("Each answer you give on a card that came from a message is kept here beside what I did with that "
                     "message, and I compare my choices with it. Keep marks an entry as reviewed, Edit sets what the right "
                     "answer was (show it or hide it) with a note if you like, and Don't learn from this stops me using an "
                     "entry. Each takes effect at once.")


def rule_book():
    """Settings, Rule book: the active rows by section in plain words (rule_book.for_settings), with the part's (i) words.
    Never costs the page its settings."""
    try:
        import rule_book as rb
        got = rb.for_settings()
    except Exception:  # noqa: BLE001
        got = {"sections": [], "count": 0, "more": 0}
    return dict(got, label="Rule book", explain=RULE_BOOK_EXPLAIN)


LEVEL_WORDS = ((1, "1 - I suggest, you press"), (2, "2 - I do it and tell you"), (3, "3 - I do it quietly"))
NO_SCORE = "Not enough of your answers yet"
LEARNING_EXPLAIN = ("How much I do on my own in each kind of work. Level 1 (where everything starts): I show my pick on each "
                    "card and you press. Level 2: what I'm good at, I do myself and tell you, with Undo. Level 3: I do it "
                    "quietly and list it in one summary card each morning. Under each one I say exactly what that level does "
                    "before you save it, sending included. The line under it is how often my picks matched what you did, "
                    "and how often my show or hide calls did. Under Reply drafts it also says how much of my drafts you kept, once you have sent one: each sent draft is compared with what went out and kept in the rule book.")


def score_line(section):
    """The section's latest score from the grader's score history (grades of the live rules only, not a draft's), in plain
    words: "I got 91% right, over 34 answers of yours", or NO_SCORE when it has none."""
    try:
        import grader
        got = [x for x in grader.scores(section) if x.get("rules", "live") == "live"]
    except Exception:  # noqa: BLE001  a score never costs the page its settings
        got = []
    last = got[-1] if got else {}
    n, m = last.get("graded"), last.get("matched")
    if not isinstance(n, int) or isinstance(n, bool) or n <= 0 or not isinstance(m, int) or isinstance(m, bool) or not 0 <= m <= n:
        return NO_SCORE
    return f"I got {round(100 * m / n)}% right, over {n} answer{'' if n == 1 else 's'} of yours"


def work_line(section):
    """How often my picks matched what he did in this kind of work, overall and by decisions, wording, timing and urgency,
    worked out now from the rule book (work_rules.score; no AI run, nothing written)."""
    try:
        import grader
        import work_rules
        total, _per = work_rules.score(grader.work_rows(section))
    except Exception:  # noqa: BLE001  a score never costs the page its settings
        return "My picks: " + NO_SCORE
    m, n = sum(v[0] for v in total.values()), sum(v[1] for v in total.values())
    if n <= 0:
        return "My picks: " + NO_SCORE
    parts = ", ".join(f"{work_rules.ASPECT_WORDS[a]} {round(100 * v[0] / v[1])}%" for a, v in total.items() if v[1])
    return f"My picks: I got {round(100 * m / n)}% right, over {n} answer{'' if n == 1 else 's'} of yours ({parts})"


def learning(levels):
    """Settings, Learning levels: a level per kind of work (settings_page.learning_levels), with the words of what each level
    does on its own there (levels.says, shown for the level picked before it is saved), and its scores as the live line:
    my picks by decisions, wording, timing and urgency, then show or hide."""
    import levels as lv
    import rule_book
    out = []
    for f, sec in settings_page.LEARN.items():
        hide = score_line(sec)
        help = work_line(sec) + ". Show or hide: " + hide + "."
        if sec == "replies":
            import writing
            kept = writing.score_line()
            if kept != writing.NO_SCORE:
                help = f"{help}. {kept}"
        out.append(_one("learning", f, rule_book.SECTION_WORDS[sec], "choice", levels.get(f, settings_page.LEARN_DEFAULT),
                        help=help, explain=LEARNING_EXPLAIN,
                        says={str(n): lv.says(sec, n) for n in settings_page.LEARN_LEVELS},
                        choices=[dict(c, disabled=True) if c["value"] not in settings_page.LEARN_LEVELS else c for c in _c(LEVEL_WORDS)]))
    return out
