r"""Acceptance test of the guard hook against the real rule book, on a scratch copy laid down from the built package.

    python tests\guards_acceptance.py [--keep]

Lays down a scratch copy (own folder, port 47893, sending off, no jobs) from the package's working copy, then sends
tool calls through hooks\rulebook_guard.py exactly as Claude Code would, in the two ways it runs: a normal session
(the plugin's hook, finding the copy through roots.json) and a hidden run (the settings file lay-down wrote, with
--root). Then changes one rule in the scratch copy's rule book only and shows the hook enforcing the change. Removes
everything at the end unless --keep. Prints one line per check and a count.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)                                      # the plugin: this repository
results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


def main(keep=False):
    tmp = tempfile.mkdtemp(prefix="guards-")
    # laid out as the owner's: the assistant's folder inside a workspace folder, beside his other projects and an
    # older program, so the guards' "assistant's folder" is shown to be that folder alone
    ws = os.path.join(tmp, "ClaudeOS")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(ws, "Assistant")
    home = os.path.join(root, "Live")
    sys.path.insert(0, os.path.join(PKG, "hooks"))
    import assistant_copy
    assistant_copy.sync(data)
    r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--root", root,
                        "--port", "47893", "--sending", "no"], capture_output=True, text=True)
    check("lay-down of the scratch copy", r.returncode, 0)
    settings = json.load(open(os.path.join(home, "personal", "guard_settings.json"), encoding="utf-8"))
    hook = settings["hooks"]["PreToolUse"][0]["hooks"][0]
    check("settings file holds only the guard hook", (list(settings), len(settings["hooks"]["PreToolUse"])), (["hooks"], 1))
    me = os.path.join(home, "personal", "personal.json")
    p = json.load(open(me, encoding="utf-8"))
    p.update({"owner": "Morgan", "full_name": "Morgan Hale"})
    json.dump(p, open(me, "w", encoding="utf-8"))
    project = os.path.join(ws, "Projects", "Other project")
    os.makedirs(project)
    old_prog = os.path.join(ws, "System", "live", "old.py")
    os.makedirs(os.path.dirname(old_prog))

    def normal(tool, ti, cwd=root):
        env = dict(os.environ, CLAUDE_PLUGIN_DATA=data)
        r = subprocess.run([sys.executable, os.path.join(PKG, "hooks", "rulebook_guard.py")], env=env, capture_output=True,
                           text=True, input=json.dumps({"tool_name": tool, "tool_input": ti, "cwd": cwd}))
        return r.returncode, r.stderr

    def hidden(tool, ti):
        r = subprocess.run([sys.executable, *hook["args"]], capture_output=True, text=True,
                           input=json.dumps({"tool_name": tool, "tool_input": ti, "cwd": os.path.join(home, "state")}))
        return r.returncode, r.stderr

    prog = os.path.join(root, "System", "live", "items.py")
    taught = os.path.join(home, "taught", "rules", "extra.json")
    # reading
    check("normal: reading the program is let through", normal("Read", {"file_path": prog})[0], 0)
    check("hidden: reading is let through", hidden("Read", {"file_path": prog})[0], 0)
    # (b) sends
    code, why = normal("mcp__mail__send_email", {"to": "a@example.com"})
    check("(b) normal, in the assistant's folder: a connector's send is refused", code, 2)
    check("(b) the refusal names rule B1", "rule B1" in why, True)
    check("(b) hidden: a command that sends is refused", hidden("Bash", {"command": "python System\\live\\send.py"})[0], 2)
    # (b) a command is refused only when it would send; a sending name that is only text goes through
    for c in ("sed -n '1,40p' engine/System/live/send.py",
              "git diff a024c3f -- engine/System/live/send.py",
              "grep -n send_standing engine/System/live/*.py",
              """python -c "import json; print(json.load(open('rulebook.json'))[0])"  # B1 is in send.py""",
              """python -c "import json; print([r for r in json.load(open('rulebook.json')) if 'send.py' in str(r)])" """,
              'git commit -m "rename wording in send.py"',
              "git commit -m \"$(cat <<'EOF'\nB1 wording: send.py, smtplib and ntfy.sh named as text\n1) only text\nEOF\n)\""):
        check(f"(b) text that only names a send goes through: {c[:60]}", normal("Bash", {"command": c})[0], 0)
    # one compound command that reads the send program, writes a scratch file elsewhere, removes it and searches a doc
    sendpy = os.path.join(root, "System", "live", "send.py")
    scratch = os.path.join(tmp, "scratch-note.txt")
    combo = f"sed -n '1,40p' \"{sendpy}\" && echo made-up note > \"{scratch}\" && rm \"{scratch}\" && grep -n send docs/changes.md"
    check("(b)/(c) reading the send program while writing and removing a scratch file elsewhere goes through",
          normal("Bash", {"command": combo})[0], 0)
    code, why = normal("Bash", {"command": "echo 'import smtplib' > made_up.py && python made_up.py"})
    check("(b) a file written and then run in the same command, naming a send, is still refused", (code, "rule B1" in why), (2, True))
    # 11/25/26: a script written here and run, whose strings name the send log (replacement text it writes into
    # another file), only edits a file: judged by what it imports and calls, not by words in its data
    for c in ('cd "/c/made/up/Assistant/Development/worktrees/rebuild-45-levels/engine/System/live" && S=/c/made/up/temp/42780a6f68779269/cf834cd0-839f-4ac7-ba3b-d8c3e89410a3/scratchpad && cat > $S/s4.py <<\'EOF\'\nimport json,sys\njson.dump([\n[\'\'\'                    if r.get("result") == "sent":\n                        out.append((dt.datetime.fromisoformat(r["at"]), _subject(r.get("subject")), r.get("item")))\'\'\',\n\'\'\'                    if r.get("result") == "sent":\n                        out.append((dt.datetime.fromisoformat(r["at"]), _subject(r.get("subject")), r.get("item"), r.get("level")))\'\'\'],\n[\'\'\'    """[(when, subject, card id)] for each send the page made (send.py\'s own log of sends)."""\'\'\',\n\'\'\'    """[(when, subject, card id, level)] for each send the page made (send.py\'s own log of sends); level: sent by me on my\n    own at learning level 2 or 3 (levels.py), else None."""\'\'\'],\n[\'\'\'        from_page = next((item for when, s, item in page if subj and s == subj\n                          and abs((when - ts).total_seconds()) <= PAGE_SEND_HOURS * 3600), False) if channel == "email" else False\'\'\',\n\'\'\'        hit = next(((item, lv) for when, s, item, lv in page if subj and s == subj\n                    and abs((when - ts).total_seconds()) <= PAGE_SEND_HOURS * 3600), None) if channel == "email" else None\n        if hit and hit[1]:\n            continue                # I sent it on my own at a learning level: not something he did\n        from_page = hit[0] if hit else False\'\'\'],\n],open(sys.argv[1]+\'/s4.json\',\'w\'))\nEOF\npython $S/s4.py $S && python $S/rep.py offpage.py $S/s4.json',
              "python $S/rep.py offpage.py $S/s4.json",
              # importing the send module (or smtplib) and calling nothing that sends is not a send
              'python -X utf8 -c "import common, items, ready, answers, send, voice, db; con = db.connect(); ready.make(1); print(answers._row(con, 3))"',
              'python -c "import send; print(send.status())"',
              'python -c "from send import prepare; print(prepare({}))"'):
        check(f"(b) a script written and run that only edits text goes through: {c[:60]}", normal("Bash", {"command": c})[0], 0)
    for c in ("python engine/System/live/send.py",
              'python -c "import send; send.send_owner_email({})"',
              """python -c "import smtplib; smtplib.SMTP('x').sendmail('a','b','c')" """,
              "curl -X POST https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
              "curl -d hi ntfy.sh/topic",
              'git commit -m "$(python engine/System/live/send.py)"',
              "python - <<'EOF'\nfrom connections import send\nsend('a', ['b'], [], 's', 'x')\nEOF",
              'bash -c "python engine/System/live/send.py"',
              'F=engine/System/live/send.py; python "$F"',
              "python $(find . -name send.py)",
              "python <(cat engine/System/live/send.py)",
              "cat > x.py <<'EOF'\nimport smtplib\nsmtplib.SMTP('h').sendmail('a','b','c')\nEOF\npython x.py",
              "S=/tmp/q; cat > $S/s.py <<'EOF'\nfrom connections import send\nsend('a', ['b'])\nEOF\npython $S/s.py",
              "cat > r.sh <<'EOF'\npython engine/System/live/send.py\nEOF\nbash r.sh",
              "python $S/send.py",
              'python -c "import send as s; s.send_standing(1, 2)"',
              'python -c "from send import send_owner_email as go; go({})"',
              'python -c "import connections as c; c.send(1)"',
              "python -c \"from smtplib import SMTP; SMTP('h')\"",
              "python - <<'EOF'\nfrom send import (\n  prepare,\n  send_owner_email as go,\n)\ngo({})\nEOF"):
        code, why = normal("Bash", {"command": c})
        check(f"(b) a command that would send is refused, naming B1: {c[:60]}", (code, "rule B1" in why), (2, True))
    # (b) PowerShell: reading the send program goes through; a PowerShell command that sends is refused
    for c in ('Select-String -Path "C:\\made\\up\\System\\live\\send.py" -Pattern "def "',
              "Get-Content .\\send.py | Select-String smtplib",
              "gc send.py -TotalCount 20",
              "sls -Pattern send_owner_email -Path send.py | ForEach-Object { $_.LineNumber }",
              'findstr /n "def" send.py',
              'rg "send_standing" engine\\System\\live\\send.py',
              'Get-Content send.py | Where-Object { $_ -match "smtp" }',
              '$f = "C:\\made\\up\\send.py"; Get-Content $f | Select-Object -First 30',
              'Select-String -Path (Join-Path $root "send.py") -Pattern x',
              # the 11/25/26 false alarm: a search that prints each hit with $( ) values is reading, not sending
              r'''cd "C:\made\up\worktrees\rebuild-1\engine\System\live"; Select-String -Path send.py,ready.py,mail_compose.py,texts.py -Pattern 'jsonl|SENT_LOG|sent_log|provider_id' | % { "$($_.Filename):$($_.LineNumber): $($_.Line.Trim().Substring(0,[Math]::Min(200,$_.Line.Trim().Length)))" } | Select -First 25''',
              'Get-Content send.py | ForEach-Object { "$($_.Length): $_" }',
              'Select-String -Path send.py -Pattern smtp | % { $_.Line.Trim().Substring(0, [Math]::Min(80, $_.Line.Length)) }'):
        check(f"(b) PowerShell reading the send program goes through: {c[:60]}", normal("PowerShell", {"command": c})[0], 0)
    for c in ('python send.py --to pat@example.com',
              '$p = "C:\\made\\up\\send.py"; & $p',
              'python "$env:ROOT\\send.py"',
              '& python "C:\\made\\up\\send.py"',
              'Invoke-RestMethod -Uri https://gmail.googleapis.com/gmail/v1/users/me/messages/send -Method Post',
              'Invoke-WebRequest https://graph.microsoft.com/v1.0/me/sendMail -Method POST',
              'Send-MailMessage -To pat@example.com -From lee@example.com -Subject hi -SmtpServer smtp.example.com',
              'Get-ChildItem -Filter send.py | ForEach-Object { python $_.FullName }',
              '$f = "send.py"; & python $f'):
        code, why = normal("PowerShell", {"command": c})
        check(f"(b) a PowerShell command that would send is refused, naming B1: {c[:60]}", (code, "rule B1" in why), (2, True))
    check("(b) normal, another project (agreed scope: b to e only in the assistant's folder): a send goes through",
          normal("mcp__mail__send_email", {"to": "a@example.com"}, cwd=project)[0], 0)
    # scope keys on the assistant's own folder, not the workspace around it
    check("scope: a send from another project in the same workspace goes through",
          normal("mcp__mail__send_email", {"to": "a@example.com"}, cwd=project)[0], 0)
    check("scope: a send from the workspace folder itself (outside the assistant's folder) goes through",
          normal("mcp__mail__send_email", {"to": "a@example.com"}, cwd=ws)[0], 0)
    check("scope: an edit to the older program beside it, from another project, goes through (not the assistant's program)",
          normal("Write", {"file_path": old_prog, "content": "x"}, cwd=project)[0], 0)
    check("scope: an edit to the assistant's program from another project is still refused",
          normal("Write", {"file_path": os.path.join(root, "System", "live", "new.py"), "content": "x"}, cwd=project)[0], 2)
    # (c) program edits
    code, why = normal("Edit", {"file_path": prog, "old_string": "import", "new_string": "import"})
    check("(c) normal: an edit to the program with no agreed change is refused, naming C1", (code, "rule C1" in why), (2, True))
    check("(c) normal: a command writing into the program is refused",
          normal("Bash", {"command": f'copy x "{prog}"'})[0], 2)
    check("(c) normal: python that only reads a program file goes through",
          normal("Bash", {"command": f'''python -c "print(open(r'{prog}').read()[:80])"'''})[0], 0)
    check("(c) normal: reading the program and writing in another project goes through",
          normal("Bash", {"command": f'type "{prog}" > "{os.path.join(project, "copy.txt")}"'})[0], 0)
    check("(c) normal: python that writes a program file is refused",
          normal("Bash", {"command": f'''python -c "open(r'{prog}', 'w').write('x')"'''})[0], 2)
    check("(c) hidden: a write into the program is refused", hidden("Write", {"file_path": prog, "content": "x"})[0], 2)
    check("(c)/(e) normal: a taught add-on written with no change is refused",
          normal("Write", {"file_path": taught, "content": "{}"})[0], 2)
    # an agreed change with a clear go and its undo copy: the same edit goes through
    cid = "test-1"
    undo = os.path.join(home, "changes", cid, "before")
    kept = os.path.join(undo, os.path.splitdrive(os.path.normcase(os.path.abspath(prog)))[1].lstrip("\\/"))
    os.makedirs(os.path.dirname(kept), exist_ok=True)
    shutil.copy2(prog, kept)
    mod_file = os.path.join(home, "mods", "header", "mod.py")       # an owner's change is a mod: written there, never in the program
    os.makedirs(os.path.dirname(mod_file), exist_ok=True)
    kept_mod = os.path.join(undo, os.path.splitdrive(os.path.normcase(os.path.abspath(mod_file)))[1].lstrip("\\/"))
    os.makedirs(os.path.dirname(kept_mod), exist_ok=True)
    open(kept_mod + ".new", "w").close()
    rec = {"id": cid, "asked": "make the header shorter", "agreed": "I will make a mod with one change.", "part": "mods",
           "files": [prog, mod_file], "go": {"at": "2026-11-17T12:00:00", "words": "yes"}, "undo": undo, "state": "go"}
    json.dump(rec, open(os.path.join(home, "changes", cid + ".json"), "w", encoding="utf-8"))
    check("(c) normal: under an agreed change with a go and its undo copy, a mod file is written",
          normal("Write", {"file_path": mod_file, "content": "x = 1\n"})[0], 0)
    code, why = normal("Write", {"file_path": prog, "content": open(prog, encoding="utf-8").read()})
    check("(c) normal: even under an agreed change, the program's own file is refused, naming C1", (code, "rule C1" in why), (2, True))
    check("(c) normal: a mod file the change does not name is still refused",
          normal("Write", {"file_path": os.path.join(home, "mods", "header", "other.py"), "content": "x"})[0], 2)
    # the rebuild tool: its own commands run from the program's folder, nothing else there
    live = os.path.join(root, "System", "live")
    lv = live.replace(chr(92), "/")
    for c in ("erase", "run-week", "continue", "status", "report", "dry-run"):
        check(f"(c) replay.py {c} from System/live, piped to tail, is let through",
              normal("Bash", {"command": f"python replay.py {c} 2>&1 | tail -25"}, cwd=live)[0], 0)
    check("(c) replay.py erase after a cd to System/live is let through",
          normal("Bash", {"command": f"cd {lv} && python replay.py erase 2>&1 | tail -25"}, cwd=root)[0], 0)
    check("(c) replay.py erase by its full path is let through",
          normal("Bash", {"command": f'python "{os.path.join(live, "replay.py")}" erase'}, cwd=project)[0], 0)
    check("(c) another script whose output is written into System/live is refused",
          normal("Bash", {"command": f"cd {lv} && python other.py erase > out.txt"}, cwd=root)[0], 2)
    check("(c) running a script with words like erase, writing nothing into the program, goes through (judged by where it writes)",
          normal("Bash", {"command": f"cd {lv} && python replay.py erase --bogus"}, cwd=root)[0], 0)
    check("(c) replay.py chained with a write into a program file is refused",
          normal("Bash", {"command": f'python replay.py erase && copy x "{prog}"'}, cwd=live)[0], 2)
    check("(c) replay.py erase redirected into a program file is refused",
          normal("Bash", {"command": f'python replay.py erase > "{prog}"'}, cwd=live)[0], 2)
    check("(c) an edit to replay.py is refused",
          normal("Edit", {"file_path": os.path.join(live, "replay.py"), "old_string": "a", "new_string": "b"}, cwd=live)[0], 2)
    check("(c) a write to a System/live .py file is refused",
          normal("Write", {"file_path": os.path.join(live, "new.py"), "content": "x"}, cwd=live)[0], 2)
    check("(c) a script from another folder that writes into System/live is refused",
          normal("Bash", {"command": f"cd {lv} && python ../replay.py erase > replay.py"}, cwd=root)[0], 2)
    # (d) nothing personal in the general part: nothing is written there at all
    code, why = normal("Write", {"file_path": prog, "content": "# written for Morgan Hale\n"})
    check("(d) normal: the owner's name written into the program is refused", code, 2)
    # (e) hidden runs write only in the home's state folder
    check("(e) hidden: a write outside the home's state folder is refused",
          hidden("Write", {"file_path": os.path.join(home, "personal", "x.json"), "content": "{}"})[0], 2)
    check("(e) hidden: a write in the state folder goes through",
          hidden("Write", {"file_path": os.path.join(home, "state", "note.json"), "content": "{}"})[0], 0)
    # (a) cards: the item writer's output in a hidden run
    out = os.path.join(home, "state", "live_items_out.json")
    code, why = hidden("Write", {"file_path": out, "content": json.dumps({"items": [], "new_items": [{"title": ""}]})})
    check("(a) hidden: a card that breaks the page's rules is refused, naming an A rule", (code, "rule A" in why), (2, True))
    # a rule changed in the rule book only, never in the hook
    book = os.path.join(root, "System", "live", "rules", "rulebook.py")
    text = open(book, encoding="utf-8").read()
    open(book, "w", encoding="utf-8").write(text.replace('(send|post|reply|forward|schedule)', '(post|reply|forward|schedule)', 1))
    check("rule book changed (sending tools no longer named 'send'): the same send now goes through, hook untouched",
          normal("mcp__mail__send_email", {"to": "a@example.com"})[0], 0)
    open(book, "w", encoding="utf-8").write(text)
    check("rule book put back: refused again", normal("mcp__mail__send_email", {"to": "a@example.com"})[0], 2)
    # fail closed
    os.rename(book, book + ".away")
    check("no rule book: a write into the assistant goes through (only sends are held back)",
          normal("Write", {"file_path": os.path.join(home, "x.json"), "content": "{}"})[0], 0)
    check("no rule book: a message to a helper goes through",
          normal("SendMessage", {"to": "made-up-helper", "message": "Put the folder back."})[0], 0)
    code, why = normal("mcp__mail__send_email", {"to": "a@example.com"})
    check("no rule book: a connector's send is still refused, naming B1", (code, "B1" in why), (2, True))
    check("no rule book: a command that sends is still refused",
          normal("Bash", {"command": "python engine/System/live/send.py"})[0], 2)
    check("no rule book: unrelated work in another project goes on",
          normal("Write", {"file_path": os.path.join(project, "notes.txt"), "content": "x"}, cwd=project)[0], 0)
    os.rename(book + ".away", book)
    if keep:
        print("kept:", tmp)
    else:
        subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "uninstall", "--root", root,
                        "--remove-data"], capture_output=True, text=True)
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main("--keep" in sys.argv))
