"""UserPromptSubmit and SessionStart hook: one or two lines of context for the two sessions the roadmap arrangement is made of, so each
keeps its job after a long conversation is summarised. A hook cannot open the roadmap page, so for the main session it
names the page to check for answered questions, marked checks and notes written on rows; this is a reminder, not an automatic check. Other sessions, helpers
and projects that are not set up get nothing."""
import datetime, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roadmap_blocks as rb


def lines(data, cfg):
    sid = data.get("session_id")
    if not sid or data.get("agent_id") or data.get("agent_type"):
        return []
    writer = cfg.get("writer") or {}
    if writer.get("claude_session_id") and sid == writer.get("claude_session_id"):
        return ["You are this project's Roadmap writer: you only write the roadmap from what the main session sends "
                "(skill assistant:roadmap-writer). Your end-of-turn summary is the receipt; send no messages."]
    if sid != cfg.get("director_session_id"):
        return []
    out = []
    if rb.direct(cfg):
        out.append("You are this project's main session for the roadmap (skill assistant:roadmap-director, part \"Writing the roadmap "
                   "yourself\"): you write the roadmap's rows yourself, in your own turn, from plans, decisions, starts and helper "
                   "reports, in one short step and without mentioning it in the chat. Helpers never write it.")
    elif rb.active(cfg):
        out.append("You are this project's main session for the roadmap (skill assistant:roadmap-director): send the Roadmap writer "
                   "every plan, decision and start before starting or messaging a helper, and forward every helper report to it.")
    else:
        out.append("The roadmap setup is not finished: no Roadmap writer is recorded. Run /assistant:roadmap-start-writer.")
    url = cfg.get("page_url")
    if url and data.get("hook_event_name") != "SessionStart":          # at a start or resume there is no message to answer yet
        out.append("After answering this message: check the roadmap for answers, marks and notes (ArtifactData, url " + url + ": "
                   "action query, collection 'questions', where status == 'answered'; action list, collection 'marks'; "
                   "action query, collection 'notes', where status == 'open'; "
                   "action list, collection 'board', and act on any document whose id starts with 'ask-' and whose status is 'open', a settings request from the page). "
                   "Opening the page itself does not show them. Never let this delay or replace the answer to the user.")
    return out


READERS_FILE = os.path.join("Roadmap page", "readers.json")
PLAIN_FILE = os.path.join("Roadmap page", "roadmap.json")


def reader_lines(data, cfg, project):
    """A reader listed in readers.json that has no plain copy yet, or asked after the last one was written: the main
    session is told to have the writer write it now, so a roadmap just connected to a page shows there at once."""
    if data.get("session_id") != cfg.get("director_session_id") or data.get("agent_id") or data.get("agent_type"):
        return []
    try:
        got = rb.load_json(os.path.join(project, READERS_FILE), {})
    except ValueError:
        return []
    if not (isinstance(got, dict) and isinstance(got.get("readers"), dict) and got["readers"]):
        return []
    plain = os.path.join(project, PLAIN_FILE)
    if os.path.isfile(plain) and os.path.getmtime(plain) >= os.path.getmtime(os.path.join(project, READERS_FILE)):
        return []
    if rb.direct(cfg):
        return ["A reader has asked for this roadmap's plain copy (Roadmap page/readers.json) and it is not written yet. Before "
                "anything else, write the plain copy and the full copy now, as your skill says for a reader that has just asked."]
    return ["A reader has asked for this roadmap's plain copy (Roadmap page/readers.json) and it is not written yet. Before "
            "anything else, send the Roadmap writer: \"A reader was just added to Roadmap page/readers.json. Write the plain "
            "copy and the full copy now, as your skill says for a reader that has just asked.\""]


PRESS_FILE = os.path.join("Roadmap page", "from-page.json")
PRESS_HEAD = "Press from the live page on the roadmap"
PRESS_TAIL = "Send these to the Roadmap writer as you do for a mark on the page. Ids already sent before: ignore."
PRESS_TAIL_DIRECT = "Write these on the roadmap yourself, as the page would have (skill: a press from another program's page). Ids already given before: ignore."
KEEP_SENT = 2000


def sent_path(project):
    return os.path.join(project, ".claude", "roadmap", "presses-sent.json")


def press_lines(data, cfg, project):
    """Presses made on another program's page that reached the project's queue but not this session, as the lines to
    send the writer; each press id is given to this session once and never again. A listener's own message that names
    ids is noted too, so the same press is not given a second time from the queue."""
    if data.get("session_id") != cfg.get("director_session_id") or data.get("agent_id") or data.get("agent_type"):
        return []
    path = sent_path(project)
    try:
        got = rb.load_json(path, {})
    except ValueError:
        got = {}
    sent = got.get("sent") if isinstance(got, dict) and isinstance(got.get("sent"), dict) else {}
    now = datetime.datetime.now().isoformat(timespec="seconds")
    out, said = [], str(data.get("prompt") or "")
    told = []
    if PRESS_HEAD in said:
        told = re.findall(r"^\[([^\]\s]+)\]", said, re.M)
        again = [i for i in told if i in sent]
        if again:
            out.append("Press ids already given to you before, forward nothing for them: " + ", ".join(again) + ".")
        for i in told:
            sent.setdefault(i, now)
    try:
        queue = rb.load_json(os.path.join(project, PRESS_FILE), {})
    except ValueError:
        queue = {}
    presses = queue.get("presses") if isinstance(queue, dict) and isinstance(queue.get("presses"), dict) else {}
    waiting = [(i, p) for i, p in presses.items()
               if isinstance(p, dict) and p.get("words") and not p.get("sent") and i not in sent]
    if waiting:
        name = str(cfg.get("title") or "roadmap")
        out.append(PRESS_HEAD + ' "' + name + '": ' + str(len(waiting)) + " to put on the roadmap, as if pressed on the roadmap page.")
        out.extend("[" + str(i) + "] " + " ".join(str(p["words"]).split()) for i, p in waiting)
        out.append(PRESS_TAIL_DIRECT if rb.direct(cfg) else PRESS_TAIL)
        for i, _ in waiting:
            sent[i] = now
    if told or waiting:
        rb.save_json({"about": "Press ids already given to the main session; written only by the Roadmap plugin's reminder.",
                      "sent": dict(list(sent.items())[-KEEP_SENT:])}, path)
    return out


if __name__ == "__main__":
    try:
        import working_copy
        working_copy.sync()
    except Exception:
        pass
    try:
        data = json.load(sys.stdin)
        cfg = rb.load_json(rb.config_path(rb.project_dir(data)), {})
        for line in lines(data, cfg):
            print(line)
        if rb.active(cfg):
            for line in reader_lines(data, cfg, rb.project_dir(data)) + press_lines(data, cfg, rb.project_dir(data)):
                print(line)
    except Exception:
        pass                                                   # a reminder must never get in the way of a message
    sys.exit(0)
