r"""First-time setup: a window that walks a new owner from nothing to a working assistant.

Double-click this file. It can be opened again any time to add an account, sign one in again,
or change an answer. Every step is carried out by setup_steps.py; this file is only the window.
A secret is typed into a box that shows dots and goes straight to the locked store on this
computer; it is never shown again, here or anywhere.
"""
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import setup_steps as steps  # noqa: E402

W, H = 860, 640
PAGES = ("Start", "You", "Accounts", "Your calendar", "What matters", "What it may do", "Your page", "Roadmaps", "Turn it on")


class Setup:
    def __init__(self, show=True):
        self.root = tk.Tk()
        self.root.title("Set up your assistant")
        self.root.geometry(f"{W}x{H}")
        if not show:
            self.root.withdraw()
        self.at = 0
        self.busy = False
        self.todo = queue.Queue()       # work threads hand the window things to do; only the window's own thread touches it
        self.root.after(50, self.poll)
        head = tk.Frame(self.root)
        head.pack(fill="x", padx=18, pady=(14, 0))
        self.title = tk.Label(head, font=("Segoe UI", 16, "bold"), anchor="w")
        self.title.pack(side="left")
        self.where = tk.Label(head, fg="#666", anchor="e")
        self.where.pack(side="right")
        self.body = tk.Frame(self.root)
        self.body.pack(fill="both", expand=True, padx=18, pady=8)
        self.status = tk.Label(self.root, anchor="w", fg="#225", wraplength=W - 40, justify="left")
        self.status.pack(fill="x", padx=18)
        foot = tk.Frame(self.root)
        foot.pack(fill="x", padx=18, pady=12)
        self.back = ttk.Button(foot, text="Back", command=lambda: self.go(self.at - 1))
        self.back.pack(side="left")
        self.next = ttk.Button(foot, text="Next", command=self.forward)
        self.next.pack(side="right")
        self.go(0)

    # --- plumbing -------------------------------------------------------------------
    def poll(self):
        try:
            while True:
                self.todo.get_nowait()()
        except queue.Empty:
            pass
        self.root.after(50, self.poll)

    def say(self, text):
        self.todo.put(lambda: self.status.config(text=str(text)))

    def work(self, fn, then=None):
        """Run something slow off the window's own thread; show what went wrong in plain words."""
        if self.busy:
            return
        self.busy = True
        self.next.state(["disabled"])

        def run():
            try:
                out, err = fn(), None
            except Exception as e:  # noqa: BLE001
                out, err = None, str(e) or type(e).__name__
            def done():
                self.busy = False
                self.next.state(["!disabled"])
                if err:
                    self.status.config(text="That did not work: " + err)
                elif then:
                    then(out)
            self.todo.put(done)
        threading.Thread(target=run, daemon=True).start()

    def go(self, n):
        self.at = max(0, min(n, len(PAGES) - 1))
        for w in self.body.winfo_children():
            w.destroy()
        self.status.config(text="")
        self.title.config(text=PAGES[self.at])
        self.where.config(text=f"Step {self.at + 1} of {len(PAGES)}")
        self.back.state(["!disabled"] if self.at else ["disabled"])
        self.next.config(text="Close" if self.at == len(PAGES) - 1 else "Next")
        self.leave = lambda: True
        getattr(self, "page_" + PAGES[self.at].lower().replace(" ", "_"))(self.body)

    def forward(self):
        if self.at == len(PAGES) - 1:
            self.root.destroy()
            return
        try:
            if self.leave() is not False:
                self.go(self.at + 1)
        except Exception as e:  # noqa: BLE001
            self.status.config(text=str(e))

    def text(self, parent, words, **kw):
        tk.Label(parent, text=words, justify="left", anchor="w", wraplength=W - 60, **kw).pack(fill="x", pady=(0, 8))

    def choice(self, parent, words, variable, value, command=None):
        """One choice among several, its words wrapped inside the window however long they are."""
        b = tk.Radiobutton(parent, text=words, variable=variable, value=value, command=command, anchor="nw",
                           justify="left", wraplength=W - 110)
        b.pack(anchor="w", fill="x", pady=2)
        return b

    def field(self, parent, label, value="", secret=False, width=60):
        row = tk.Frame(parent)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label, width=26, anchor="w").pack(side="left")
        e = ttk.Entry(row, width=width, show="•" if secret else "")
        e.insert(0, value or "")
        e.pack(side="left")
        return e

    # --- the pages ---------------------------------------------------------------------
    def page_start(self, f):
        self.text(f, "This sets up your own assistant on this computer. It reads your mail, messages and calendar "
                     "every 15 minutes, works out what needs you, and keeps one page up to date where you answer it.\n\n"
                     "Everything about you stays on this computer in your own folder. You sign in to each account on "
                     "that account's own website; this program never sees a password.\n\n"
                     "You can stop at any step and open this window again later. Nothing is lost.")
        self.checks = tk.Label(f, justify="left", anchor="w", font=("Segoe UI", 10))
        self.checks.pack(fill="x", pady=8)
        self.fix = ttk.Button(f, text="Install the missing parts", command=lambda: self.work(
            lambda: steps.install_parts(self.say), lambda _o: self.go(0)))
        missing = steps.parts_missing()
        ok, where = steps.claude_ready()
        lines = ["Parts this needs: " + ("all here." if not missing else "missing " + ", ".join(missing) + "."),
                 "Claude (what it thinks with): " + ("found." if ok else
                 "not found. Install the Claude desktop app from https://claude.ai/download, sign in, then open this window again.")]
        self.checks.config(text="\n".join(lines))
        if missing:
            self.fix.pack(anchor="w")

        def leave():
            if steps.parts_missing():
                raise ValueError("Press \"Install the missing parts\" first.")
            steps.make_home()
        self.leave = leave

    def page_you(self, f):
        me = steps._me()
        self.text(f, "Who is this assistant for? It uses these to speak to you and to judge what matters.")
        first = self.field(f, "Your first name", "" if me.get("owner") == "the owner" else me.get("owner", ""))
        full = self.field(f, "Your whole name", me.get("full_name", ""))
        self.text(f, "\nIn a sentence or two: what do you do, and who are the people closest to your work and home?")
        about = tk.Text(f, height=4, width=90, wrap="word")
        about.insert("1.0", me.get("about", ""))
        about.pack(anchor="w")
        self.text(f, "\nThe parts of your life your items should sort into, one per line (for example: Work, Family, "
                     "Church). \"Personal\" and \"System\" are always there.")
        areas = tk.Text(f, height=5, width=40)
        areas.insert("1.0", "\n".join(a for a in me.get("areas") or [] if a not in ("Personal", "System")))
        areas.pack(anchor="w")
        self.w = {"first": first, "full": full, "about": about, "areas": areas}
        self.leave = lambda: steps.you(first.get(), full.get(), about.get("1.0", "end"),
                                       areas.get("1.0", "end").splitlines())

    def page_accounts(self, f):
        self.text(f, "Connect each account you want read. Pick a kind, follow its steps on the right, then connect. "
                     "Add as many as you have. You can come back and add more later.")
        top = tk.Frame(f)
        top.pack(fill="both", expand=True)
        left = tk.Frame(top)
        left.pack(side="left", fill="y")
        tk.Label(left, text="Kinds of account", anchor="w", font=("Segoe UI", 10, "bold")).pack(fill="x")
        self.types = steps.connection_types()
        self.kinds = tk.Listbox(left, height=6, width=42, exportselection=False)
        for _t, name, _k, _s in self.types:
            self.kinds.insert("end", name)
        self.kinds.pack()
        self.kinds.bind("<<ListboxSelect>>", lambda _e: self.show_type())
        self.form = tk.Frame(left)
        self.form.pack(fill="x", pady=6)
        tk.Label(left, text="Connected now", anchor="w", font=("Segoe UI", 10, "bold")).pack(fill="x", pady=(8, 0))
        self.have = tk.Listbox(left, height=6, width=42, exportselection=False)
        self.have.pack()
        across = ttk.Scrollbar(left, orient="horizontal", command=self.have.xview)   # a long address can be slid into view
        across.pack(fill="x")
        self.have.config(xscrollcommand=across.set)
        self.picked = tk.Label(left, anchor="w", justify="left", wraplength=270, fg="#333")     # the chosen one, in full
        self.picked.pack(fill="x")
        self.have.bind("<<ListboxSelect>>", lambda _e: self.show_picked())
        row = tk.Frame(left)
        row.pack(fill="x", pady=4)
        ttk.Button(row, text="Sign in again", command=self.again).pack(side="left")
        ttk.Button(row, text="Remove", command=self.remove).pack(side="left", padx=6)
        ttk.Button(row, text="Test all", command=self.test_all).pack(side="left")
        self.steps_box = scrolledtext.ScrolledText(top, wrap="word", width=58, font=("Segoe UI", 9))
        self.steps_box.pack(side="right", fill="both", expand=True, padx=(12, 0))
        self.refresh_have()

    def refresh_have(self):
        self.conns = steps.connected()
        self.have.delete(0, "end")
        for _id, _kind, label in self.conns:
            self.have.insert("end", label)
        self.show_picked()

    def show_picked(self):
        at = self.have.curselection()
        self.picked.config(text="{2}\n{1}".format(*self.conns[at[0]]) if at else "")

    def show_type(self):
        if not self.kinds.curselection():
            return
        type_name, _name, _kind, setup = self.types[self.kinds.curselection()[0]]
        self.steps_box.config(state="normal")
        self.steps_box.delete("1.0", "end")
        self.steps_box.insert("1.0", setup)
        self.steps_box.config(state="disabled")
        for w in self.form.winfo_children():
            w.destroy()
        self.entries = {}
        reg = steps.registration_asks(type_name)
        for a in reg + steps.connection_asks(type_name):
            if a.get("folder"):
                row = tk.Frame(self.form)
                row.pack(fill="x", pady=3)
                var = tk.StringVar()
                ttk.Button(row, text="Choose folder", command=lambda v=var: v.set(filedialog.askdirectory() or v.get())).pack(side="left")
                tk.Label(row, textvariable=var, anchor="w").pack(side="left", padx=6)
                self.entries[a["key"]] = var
            else:
                tk.Label(self.form, text=a["label"], anchor="w").pack(fill="x")
                e = ttk.Entry(self.form, width=44, show="•" if a.get("secret") else "")
                e.pack(anchor="w")
                self.entries[a["key"]] = e
        needs_browser = hasattr(steps.connections.module(type_name), "APP")
        ttk.Button(self.form, text="Sign in" if needs_browser else "Connect",
                   command=lambda: self.connect(type_name, bool(reg))).pack(anchor="w", pady=6)

    def answers(self):
        got = {k: e.get().strip() for k, e in self.entries.items()}
        for e in self.entries.values():          # a typed secret does not stay in the window
            if isinstance(e, ttk.Entry) and e.cget("show"):
                e.delete(0, "end")
        return got

    def connect(self, type_name, with_registration, conn_id=None):
        got = self.answers()

        def do():
            if with_registration:
                steps.save_registration(type_name, got)
            return steps.add_connection(type_name, got, self.say, conn_id)

        def done(_conn):
            self.refresh_have()
            self.show_type()
        self.work(do, done)

    def again(self):
        if not self.have.curselection():
            return self.say("Pick a connected account first.")
        conn_id = self.conns[self.have.curselection()[0]][0]
        conn = steps.connections.get(conn_id)
        asks = steps.connection_asks(conn["type"])
        if asks:
            for i, (t, *_r) in enumerate(self.types):
                if t == conn["type"]:
                    self.kinds.selection_clear(0, "end")
                    self.kinds.selection_set(i)
                    self.show_type()
            return self.say("Fill in the box on the left again and press Connect; it replaces the old one.")
        self.entries = {}
        self.connect(conn["type"], False, conn_id)

    def remove(self):
        if not self.have.curselection():
            return self.say("Pick a connected account first.")
        conn_id, _kind, label = self.conns[self.have.curselection()[0]]
        if messagebox.askyesno("Remove", f"Stop reading {label} and forget its sign-in on this computer?"):
            steps.remove_connection(conn_id)
            self.refresh_have()

    def test_all(self):
        self.work(steps.check_connections, lambda rows: self.status.config(
            text="\n".join(("OK: " if ok else "PROBLEM: ") + line if ok else f"PROBLEM: {label}: {line}"
                           for label, ok, line in rows) or "Nothing is connected yet."))

    def page_your_calendar(self, f):
        self.text(f, "Which calendars should show under \"Today\" on your page? The others are still read, so the "
                     "assistant knows when you are busy.")
        self.cal_vars = []
        box = tk.Frame(f)
        box.pack(fill="both", expand=True, anchor="w")

        def fill(rows):
            if not rows:
                self.text(box, "No calendar is connected. Go back to Accounts to add one, or press Next to go on without.")
            for name, on in rows:
                v = tk.BooleanVar(value=on)
                tk.Checkbutton(box, text=name, variable=v, anchor="w", justify="left", wraplength=W - 110).pack(anchor="w")
                self.cal_vars.append((name, v))
        self.work(steps.calendar_choices, fill)
        self.leave = lambda: steps.show_calendars([n for n, v in self.cal_vars if v.get()])

    def page_what_matters(self, f):
        self.text(f, "What should never wait? Write one kind of thing per line, in your own words. These are what the "
                     "assistant marks important. Examples:\n"
                     "   Anything from my boss or my spouse that asks me a question\n"
                     "   A bill or payment due within 3 days\n"
                     "   A meeting today that moved or was cancelled")
        box = tk.Text(f, height=9, width=96, wrap="word")
        box.insert("1.0", "\n".join(steps.common.important_lines()))
        box.pack(anchor="w")
        on = tk.BooleanVar(value=steps.status()["alerts"])
        ttk.Checkbutton(f, text="Also send my phone a notification when something important arrives", variable=on).pack(anchor="w", pady=(12, 2))
        self.alert_note = tk.Label(f, justify="left", anchor="w", wraplength=W - 60, fg="#333")
        self.alert_note.pack(fill="x")
        self.w = {"lines": box, "alerts": on}

        def leave():
            steps.what_matters(box.get("1.0", "end").splitlines())
            topic = steps.phone_alerts(on.get())
            if topic and not getattr(self, "told_topic", False):
                self.told_topic = True
                self.alert_note.config(text="On your phone: install the free app \"ntfy\" from your app store, open it, tap +, "
                                            f"and type this channel name exactly:\n\n      {topic}\n\nThen press Next again.")
                return False
        self.leave = leave

    def page_what_it_may_do(self, f):
        offered = [("sending", steps.SENDING_SAYS)]
        self.text(f, "One thing the assistant does only if you say yes. It starts switched off. You can change "
                     "your answer later by opening this window again.")
        now = steps.allowed()
        self.may = {}
        for key, words in offered:
            box = tk.LabelFrame(f, padx=10, pady=8)
            box.pack(fill="x", pady=8)
            tk.Label(box, text=words, justify="left", anchor="w", wraplength=W - 100).pack(fill="x")
            v = tk.StringVar(value={True: "yes", False: "no"}.get(now[key], ""))
            row = tk.Frame(box)
            row.pack(anchor="w", pady=(6, 0))
            ttk.Radiobutton(row, text="Yes, turn it on", variable=v, value="yes").pack(side="left")
            ttk.Radiobutton(row, text="No, leave it off", variable=v, value="no").pack(side="left", padx=16)
            self.may[key] = v
        self.w = self.may

        def leave():
            pick = {k: {"yes": True, "no": False}.get(v.get()) for k, v in self.may.items()}
            steps.allow(pick["sending"])
        self.leave = leave

    def page_your_page(self, f):
        have = steps.page_address()
        self.text(f, "Where should your page live? It is locked with a password you choose either way, and the "
                     "assistant's own key to it is made for you and never shown.")
        how = tk.StringVar(value=steps.hosting() or "own_pc")
        for value, words in (("own_pc", "On this computer. Nothing to buy and nothing to upload. You open it in a browser on this "
                                        "computer; tick the box below to open it from your phone as well."),
                             ("hosted", "On my own website, so I can open it from my phone. Needs a website host that runs "
                                        "PHP 8.1 or newer and has https (see SETUP.md beside this program)."),
                             ("both", "Both.")):
            self.choice(f, words, how, value, command=lambda: show_choice())
        site = tk.Frame(f)
        addr = self.field(site, "Your website page's address", have or "https://")
        out = scrolledtext.ScrolledText(site, height=9, wrap="word", font=("Segoe UI", 9))
        local = tk.Label(f, justify="left", anchor="w", wraplength=W - 60, fg="#333")
        # being reached from anywhere: this computer's own page, handed to the internet by Tailscale (setup_steps.reach_*)
        far = tk.BooleanVar(value=steps.reach()["how"] == "tailscale")
        far_box = tk.Checkbutton(f, text="Also reachable from anywhere (phone, another computer)", variable=far, anchor="w",
                                 command=lambda: show_choice())
        reach = tk.Frame(f)
        tk.Label(reach, justify="left", anchor="w", wraplength=W - 60, text=(
            steps.REACH_SAYS + "\n"
            f"1. Install Tailscale from {steps.TAILSCALE_GET} and sign in to it. You do this yourself, once.\n"
            "2. Press \"Switch it on\" here.\n"
            "3. If your browser opens a Tailscale page asking you to approve, approve it there once, then press \"Switch it on\" again.\n"
            "4. Open the address shown below on your phone and sign in with your page's password.")).pack(fill="x")
        told = tk.Label(reach, justify="left", anchor="w", wraplength=W - 60, fg="#225")
        told.pack(fill="x", pady=(6, 2))
        row = tk.Frame(reach)
        row.pack(fill="x")
        shown = tk.Entry(row, font=("Segoe UI", 14, "bold"), relief="flat", readonlybackground=self.root.cget("bg"), width=44)
        # what a button here did is said right under the buttons: the window's own status line can sit below the fold
        copy = ttk.Button(row, text="Copy", command=lambda: (self.root.clipboard_clear(), self.root.clipboard_append(shown.get()),
                                                             result.config(text="Copied. Paste it into a message to your phone.")))
        note = tk.Label(reach, justify="left", anchor="w", wraplength=W - 60, fg="#555", font=("Segoe UI", 8),
                        text="The first time, the address can take up to 10 minutes to start working. Your page cannot be "
                             "opened while this computer is off or asleep; everything waits and catches up when it is back.")
        acts = tk.Frame(reach)
        acts.pack(fill="x", pady=(4, 0))
        b_on = ttk.Button(acts, text="Switch it on", command=lambda: self.work(lambda: steps.reach_on(self.say), show_reach))
        b_look = ttk.Button(acts, text="Look again", command=lambda: self.work(steps.reach_status, show_reach))
        def check_it():
            if self.busy:
                result.config(text="Still finishing the last thing. Press \"Check it\" again in a moment.")
                return
            result.config(text="Checking: opening your address the way a phone would. This can take half a minute.")
            self.work(steps.reach_check, lambda got: result.config(text=got[1]))
        b_check = ttk.Button(acts, text="Check it", command=check_it)
        b_off = ttk.Button(acts, text="Switch it off", command=lambda: self.work(lambda: steps.reach_off(self.say), show_reach))
        result = tk.Label(reach, justify="left", anchor="w", wraplength=W - 60, fg="#225")
        result.pack(fill="x", pady=(4, 0))

        def show_reach(now):
            """The words and buttons for where it stands: not installed, signed out, no free port, ready, or on."""
            told.config(text=now["says"])
            result.config(text="")
            for w in (shown, copy, note, b_on, b_look, b_check, b_off):
                w.pack_forget()
            if now["state"] == "on":
                shown.config(state="normal")
                shown.delete(0, "end")
                shown.insert(0, now["address"])
                shown.config(state="readonly")
                shown.pack(side="left")
                copy.pack(side="left", padx=8)
                note.pack(fill="x", before=acts)
                b_check.pack(side="left")
                b_off.pack(side="left", padx=8)
            elif now["state"] == "ready":
                b_on.pack(side="left")
                b_look.pack(side="left", padx=8)
            else:
                b_look.pack(side="left")
            self.w["reach_now"] = now

        def show_choice():
            site.pack_forget()
            local.pack_forget()
            far_box.pack_forget()
            reach.pack_forget()
            if how.get() in ("own_pc", "both"):
                local.config(text="On this computer your page's address will be " + steps.local_page_address(preview=True)
                                  + ". At the last step your browser opens once so you can choose its password.")
                local.pack(fill="x", pady=(8, 0))
                far_box.pack(fill="x", pady=(4, 0))
                if far.get():
                    reach.pack(fill="x", pady=(2, 0))
                    show_reach(steps.reach_status())
            if how.get() in ("hosted", "both"):
                site.pack(fill="both", expand=True, pady=(8, 0))

        def make():
            address = addr.get()
            replace = bool(have) and messagebox.askyesno(
                "Replace", "Make new keys for the page? The old page stops updating until the new config file is uploaded.")
            self.work(lambda: steps.page(address, replace=replace), show)

        def show(got):
            out.delete("1.0", "end")
            out.insert("1.0",
                       "Four things to do now, in this order:\n\n"
                       f"1. Upload everything inside this folder to the folder on your host that matches the address above:\n   {got['upload']}\n\n"
                       f"2. Upload this one file into the same folder on your host, replacing the file of the same name that step 1 put there (it is made for your address):\n   {got['access']}\n\n"
                       f"3. Upload this one file into that folder's \"data\" folder, and rename it there to config.php:\n   {got['config']}\n\n"
                       f"4. Open this address in your browser within 7 days and choose your page password (10 characters or more):\n   {got['open']}\n\n"
                       "That address works once. It is not saved anywhere; copy it now if you are not doing step 4 right away.")
        ttk.Button(site, text="Make my page files", command=make).pack(anchor="w")
        out.pack(fill="both", expand=True, pady=8)
        if have:
            out.insert("1.0", f"A website page is already set up at {have}. Press Next to keep it.")
        self.w = {"how": how, "address": addr, "out": out, "make": make, "show_choice": show_choice, "far": far}
        show_choice()

        def leave():
            if how.get() in ("hosted", "both") and not steps.page_address():
                raise ValueError("Type your website page's address and press \"Make my page files\" first, or choose "
                                 "\"On this computer\".")
            if how.get() == "hosted" and steps.reach()["how"] == "tailscale":
                raise ValueError("Your page is still reachable from anywhere on this computer. Choose \"On this computer\", "
                                 "press \"Switch it off\", then choose your website again.")
            steps.set_hosting(how.get())
        self.leave = leave

    def page_roadmaps(self, f):
        self.text(f, steps.ROADMAP_SAYS)
        top = tk.Frame(f)
        top.pack(fill="x", pady=(0, 6))
        in_claude = tk.Label(top, anchor="w", justify="left", wraplength=W - 260, text="Checking whether Claude has the Roadmap plugin...")
        in_claude.pack(side="left")
        add = ttk.Button(top, text="Add the Roadmap plugin to Claude")
        tk.Label(f, text="Projects the roadmap is applied to", anchor="w", font=("Segoe UI", 10, "bold")).pack(fill="x")
        box = tk.Listbox(f, height=6, exportselection=False)
        box.pack(fill="x")
        across = ttk.Scrollbar(f, orient="horizontal", command=box.xview)
        across.pack(fill="x")
        box.config(xscrollcommand=across.set)
        picked = tk.Label(f, anchor="w", justify="left", wraplength=W - 60, fg="#333")
        picked.pack(fill="x", pady=(2, 4))
        said = tk.Label(f, anchor="w", justify="left", wraplength=W - 60, fg="#225")
        rows = []

        def show_picked(_e=None):
            at = box.curselection()
            picked.config(text="{0}\n{1}".format(*rows[at[0]]) if at else "")

        def refresh():
            rows[:] = steps.roadmaps_applied()
            box.delete(0, "end")
            for folder, _line in rows:
                box.insert("end", folder)
            if not rows:
                picked.config(text="None. Nothing about roadmaps shows on your page.")

        def claude_has(yes):
            in_claude.config(text="Claude has the roadmap: it comes with the assistant plugin." if yes else
                             "Claude does not have the assistant plugin, which brings the roadmap. Add it the way its README "
                             "says. Roadmaps you already have can be applied below without it.")
            add.pack_forget()

        def apply(folder=None):
            folder = folder or filedialog.askdirectory(title="Choose the project's folder")
            if folder:
                self.work(lambda: steps.apply_roadmap(folder), lambda line: (refresh(), said.config(text=line)))

        def take_off(folder=None):
            if folder is None:
                if not box.curselection():
                    return self.say("Pick a project in the list first.")
                folder = rows[box.curselection()[0]][0]
                if not messagebox.askyesno(
                        "Take the roadmap off",
                        f"Stop showing this project's roadmap on your page?\n\n{folder}\n\nThe roadmap itself, its own "
                        "page and everything on it stay as they are."):
                    return None
            self.work(lambda: steps.take_roadmap_off(folder), lambda lines: (refresh(), said.config(text=" ".join(lines))))

        add.config(command=lambda: self.work(lambda: steps.add_roadmap_to_claude(self.say), lambda _o: claude_has(True)))
        box.bind("<<ListboxSelect>>", show_picked)
        row = tk.Frame(f)
        row.pack(fill="x", pady=4)
        ttk.Button(row, text="Apply to a project folder", command=apply).pack(side="left")
        ttk.Button(row, text="Take off", command=take_off).pack(side="left", padx=8)
        said.pack(fill="x", pady=(4, 0))
        refresh()
        self.w = {"list": box, "apply": apply, "take_off": take_off, "said": said, "in_claude": in_claude, "add": add}
        self.work(steps.roadmap_in_claude, claude_has)

    def page_turn_it_on(self, f):
        s = steps.status()
        where = {"own_pc": "on this computer", "hosted": s["page"] or "website not set up", "both": "this computer and " + (s["page"] or "a website")}
        if s["reach"]["how"] == "tailscale" and s["hosting"] in ("own_pc", "both"):
            where[s["hosting"]] += ", and from anywhere at " + s["reach"]["address"]
        self.text(f, f"Accounts connected: {len(s['connections'])}.   Page: {where.get(s['hosting'], 'not chosen')}.   "
                     f"Phone notifications: {'on' if s['alerts'] else 'off'}.   " +
                     f"Sending email: {'on' if s['may']['sending'] else 'off'}.")
        self.text(f, "\"Turn it on\" makes one background job on this computer, hidden and yours to remove: it "
                     "reads your accounts every 15 minutes and acts on your page answers the moment you give them"
                     " (and shows your page, when it lives on this computer). It runs only while you are signed in to Windows.")
        log = scrolledtext.ScrolledText(f, height=14, wrap="word", font=("Segoe UI", 9))
        log.pack(fill="both", expand=True, pady=8)
        add = lambda line: self.todo.put(lambda: (log.insert("end", str(line) + "\n"), log.see("end")))  # noqa: E731

        def run():
            ok, lines = steps.first_pass(add)
            for ln in lines:
                add(ln)
            if not ok:
                add("\nThe first pass had a problem, so the background job was not turned on. Fix what it names "
                    "(the Accounts step has a \"Test all\" button) and press the button again.")
                return
            steps.turn_on(add)
            here = steps.open_local_page(add)       # nothing when the page does not live on this computer
            if any(ln.startswith("Problem") for ln in lines):
                add("\nIt is on and reading your accounts, but fix the problem named above (a page problem "
                    "usually means the upload in the \"Your page\" step is not finished).")
            else:
                far = steps.reach()
                add("\nDone. Your page: " + " and ".join(x for x in (here, far.get("address") if here else "",
                                                                    steps.page_address() if s["hosting"] != "own_pc" else "") if x))
        ttk.Button(f, text="Run the first pass and turn it on", command=lambda: self.work(run)).pack(anchor="w")
        self.w = {"log": log, "run": lambda: self.work(run)}
        add(f'This copy\'s background job is named: "{steps.job_names()[1]}"')
        if s["jobs"]:
            add("Already on: " + ", ".join(s["jobs"]))


if __name__ == "__main__":
    Setup().root.mainloop()
