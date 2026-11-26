# Setting up your assistant for the first time

This takes about an hour, most of it connecting accounts. You do it once. You can stop at any step and pick up later.

## What you are setting up

A program on your own Windows computer that reads your mail, messages and calendar every 15 minutes (you can make it every 30 or 60 later, in Settings on your page), works out what needs you, and keeps one private page up to date where you answer it. Everything about you stays in one folder on your computer. You sign in to each account on that account's own website; the assistant never sees a password.

## What you need before you start

1. **A Windows 10 or 11 computer** that is on and signed in when you want the assistant working. It does nothing while the computer is off or signed out.
2. **Python.** Open https://www.python.org/downloads, click the yellow "Download Python" button, run the file, tick **"Add python.exe to PATH"** on the first screen, then click "Install Now".
3. **Claude.** The assistant thinks with Claude on your own subscription. Install the Claude desktop app from https://claude.ai/download, open it, and sign in with a paid plan. In the app, open the "Code" tab once so its parts finish installing.
4. **The assistant's folder.** Put the folder you were given (it contains a folder named `System`) somewhere permanent, for example inside Documents. Do not move it after setup.
5. **Nothing else.** Your page can live on this computer, which needs no website. To open it from your phone you can add a free program called Tailscale later (see "Reaching your page from anywhere" below); a website of your own also works but is not needed.

## Start

Open the assistant's folder, then `System`, then `live`, and double-click **Setup.pyw**. A window opens. No black command window should appear; if Windows asks what to open the file with, choose Python.

The window has nine steps. "Back" and "Next" move between them, and what you enter is kept.

1. **Start.** Shows whether Python's extra parts and Claude are present. If parts are missing, press "Install the missing parts" and wait for "Installed."
2. **You.** Your first name, whole name, a sentence or two about what you do and who matters to you, and the areas of your life (Work, Family, and so on).
3. **Accounts.** Click a kind of account on the left; its full steps appear on the right. Follow them, fill in any boxes that appear on the left, and press "Sign in" or "Connect". Repeat for each account. The kinds are:
   - Microsoft mail (work, school, or personal Outlook.com and Hotmail)
   - Gmail or Google Workspace mail
   - Google Calendar
   - Text messages from an Android phone
   
   The first Microsoft account and the first Google account each need a one-time registration with that company (free, about 10 to 15 minutes, every click is in the steps). After that, each further account is one sign-in.
   A box that shows dots is for a secret. What you type there is locked to your Windows account on this computer and is never shown again, on your page or anywhere else.
   "Test all" checks every connected account with one harmless read.
4. **Your calendar.** Tick the calendars whose events should show under "Today".
5. **What matters.** In your own words, the kinds of thing that should never wait. Optionally turn on phone notifications (a free app called ntfy).
6. **What it may do.** Sending email stays switched off unless you choose Yes here, and it is explained on the screen: only an email you write on your page and press Send on; nothing is sent automatically. You must pick Yes or No. If you pick No, your page tells you it is off and how to turn it on.
7. **Your page.** See below.
8. **Roadmaps.** Optional; press Next to skip it. See "Roadmaps" below.
9. **Turn it on.** Press "Run the first pass and turn it on". The first pass reads the last 30 days of each account so it knows your recent history; it can take several minutes. When it finishes cleanly the background job is created and your page is live.

## Your page

The "Your page" step asks where your page should live. It is locked with a password you choose either way.

1. **On this computer** (the choice already picked for you). Nothing to buy and nothing to upload. At the last step your browser opens once so you can choose the page's password; after that the page is at the address the window shows (it starts `http://127.0.0.1:`). You open it in a browser on this computer, while you are signed in to Windows. To open it from your phone as well, tick "Also reachable from anywhere"; see "Reaching your page from anywhere" below.
2. **On my own website.** Another way to open the page from your phone, if you already have a website. See "A website page" below.
3. **Both.** The same page in both places.

You can change the choice later by opening Setup again.

### Reaching your page from anywhere

Your page can stay on this computer and still be opened from your phone or any other computer. A free program called Tailscale (free for personal use) gives this computer an encrypted address of its own on the internet and hands each visit to your page. Your page is still locked with your password, and nothing is copied to anyone else's computer.

Steps, in the "Your page" step of the setup window, with "On this computer" (or "Both") chosen and the box "Also reachable from anywhere (phone, another computer)" ticked:
1. Install Tailscale from tailscale.com/download and sign in to it. You do this yourself, once. Your assistant never installs it and never signs in for you.
2. Press "Switch it on".
3. The first time, your browser may open a Tailscale page asking you to approve. Approve it there once, then press "Switch it on" again.
4. The window shows your page's address, starting `https://`. Press "Copy", send it to your phone, open it there and sign in with your page's password.

Good to know:
- The first time, the address can take up to 10 minutes to start working. "Check it" opens the address the way a phone would and tells you whether your page answered.
- Your page cannot be opened while this computer is off, asleep or signed out. Nothing is lost: what you answer on your phone when the computer is back is acted on as usual.
- If Tailscale on this computer is already used for something else, that is left exactly as it is. Your page takes a public port nothing else is using, and its address then ends in `:8443` or `:10000`.
- The address is for you. Anyone who has it sees only the sign-in. After 5 wrong passwords from one visitor, or 20 from all visitors together, sign-in from outside is locked for up to 15 minutes; signing in at this computer itself is never locked by that, and a phone already signed in stays signed in.
- **To switch it off:** open Setup, go to "Your page", and press "Switch it off". The address stops working at once and your page is again reachable from this computer only.

### A website page

What you need:
- **Web hosting that runs PHP (version 8.1 or newer) and has https**, on an Apache server (the ordinary kind at most paid hosts: Bluehost, HostGator, SiteGround, DreamHost and similar). A free static-page host will not work.
- **A way to upload files**: the host's "File Manager" in its control panel is enough.
- **An address for the page**, for example `https://yourname.com/brief`. The last part (`brief`) is a folder you create on the host; it can have any name.

Steps:
1. In your host's File Manager, open the folder that is your website (often `public_html`) and create the folder (`brief`).
2. In the setup window's "Your page" step, choose "On my own website" (or "Both"), type the address (`https://yourname.com/brief`) and press "Make my page files". The window then lists four things to do, with the exact folder and file on your computer:
   - upload everything inside the `site` folder into `brief` (keep the `app` and `data` folders as folders; make sure files whose names start with a dot, like `.htaccess`, are uploaded too: in File Manager turn on "Show hidden files");
   - upload the `.htaccess` file made for your address into `brief`, replacing the one just uploaded (this file is what carries your folder's name);
   - upload the one config file into `brief/data` and rename it there to `config.php`;
   - open the one-time address shown and choose your page password (10 characters or more).

The one-time address works once and for 7 days. If you lose it, press "Make my page files" again and repeat the last two uploads.

## Roadmaps (optional)

**What it is.** A roadmap is a private page for one project. It lists every step of that project and where each one stands, and Claude keeps it up to date while you work on the project in the Claude desktop app. Roadmaps come from a separate Claude plugin named Roadmap. The assistant and the plugin do not need each other: the assistant works the same with or without it, and the plugin works the same with or without the assistant. Until you apply a roadmap here, nothing about roadmaps shows on your page or anywhere else.

**What you get.** For each project you apply it to:
- in the Claude desktop app, that project's own roadmap page (from the plugin), where you mark finished work as Works or Doesn't work and answer Claude's questions;
- on your assistant's page, a "Roadmaps" part that lists every such project: its name, its "What's next" lines, every row with its status, how many checks wait to be tried, how many questions are open, when it last changed, and a link that opens the roadmap's own page. This part is for reading. It shows wherever your page lives, on this computer and on your own website.

**What it needs.** The Roadmap plugin added to Claude (its own README says what the plugin needs and how to add it). If the plugin's folder came alongside this assistant, as a folder named `Roadmap` beside `System`, the setup window can add it to Claude for you.

**How to apply it.**
1. In the setup window go to the "Roadmaps" step.
2. If it says Claude does not have the Roadmap plugin yet: press "Add the Roadmap plugin to Claude" when that button is offered and wait for "Added", or add the plugin the way its README says. Then close the Claude desktop app completely and open it again. You do this once.
3. Press "Apply to a project folder" and choose the project's folder. Do this for each project you want.
4. The window then says the one thing left for that project, if any: in the Claude desktop app's Code tab, open a session in that folder and send `/assistant:roadmap-setup`. Claude asks what to call the roadmap, makes its page and gives you the link.

A project's roadmap shows on your assistant's page after its first change, within about half a minute.

**How to take it off.** In the "Roadmaps" step, pick the project and press "Take off". It leaves your assistant's page. The roadmap itself keeps working in that project; switching a roadmap off is in the plugin's README.

**How it works, and how fresh it is.** The only link between the two is two small files in the project's own `Roadmap page` folder. Applying a project puts the assistant's name in `readers.json` there. While a name is listed, Claude writes every change to the roadmap's own page and, at the same moment, to a plain summary beside it (`roadmap.json`). The assistant's background job reads that summary; nothing new runs on your computer and no Claude usage is spent on refreshing your page. One limit: a check you mark or a question you answer on the roadmap's own page changes the counts on your assistant's page only at Claude's next change to that roadmap.

## Afterward

- **Your page** is where you work: answer cards, type in the box at the top.
- **To change a setting:** press **Settings** near the top of your page. It opens on five groups: General (Profile, Appearance, Calendar, Sign-in), Inbox (Sources, Filters, Notifications, Email), Automation (Approvals, Writing style, Weekly review), AI and usage, and Tools. Sources holds what matters, your own mail domains, ignored senders, words that keep a mailing, Sync (on or off) and Check every; Calendar holds which calendars show in the Today box (also reached by Choose calendars on Today); Notifications holds phone notifications and quiet hours; Appearance the theme, text size, page layout, how cards are grouped and sorted, how long Done cards stay, Snooze options and the time format; Sign-in the password, how long a sign-in lasts and signing out everywhere; Filters the filter strength, your rules and when cards come back; Approvals your standing approvals; AI and usage the AI model, a daily limit and a quick pre-sort. What is changed only with a command in Claude on this computer is listed in Tools. Change what you want and press Save. The page says what was saved and when it takes effect.
- **Mailings and junk:** an email that carries an unsubscribe link is hidden as junk before it is read, unless its subject is about security or a sign-in. If some mailings matter to you (bills, invoices, orders, deliveries), add those words under Settings, "Sources", "Words that keep a mailing"; the list starts empty. On any card that came from someone outside, **Junk** puts that sender on your junk list at once (their mail makes no more cards) and **Never junk** makes sure their mail is always read. Undo takes either back. The lists are the file `Live\Resources\Data\Junk senders.md`, which you can also open and edit.
- **What was hidden:** your page shows how many messages were kept off it today, and the list, with one line each saying why (your junk list, your ignore list, one of your settings, one of your rules, or the sorting step's own reason). Press **I should have seen this** on any row and its card is on your page at once. Nothing is ever kept off your page without being on that list.
- **Teaching it:** on any card, **I did not need this** asks one thing: only this one, this sender, or this kind of message. "This sender" puts them on your ignore list at once. "This kind of message" proposes a rule in one plain sentence, as a card; nothing changes until you approve it. Your rules are in Settings, "Filters", "Rules", where you can add, change, pause or remove any of them.
- **Filters:** the same group of Settings holds how strict the filter is, what happens to newsletters, automated notices, mail you are only copied on, first-time senders, texts from unknown numbers, and the people who always get through.
- **Cards that come back:** a card waiting on someone else returns to you after 3 working days with no word, or as soon as they write (you choose the days in Settings). Cards of yours that have sat untouched for 14 days are asked about once, together, on one card: keep, someday or drop. Nothing is dropped unless you say so.
- **The top of your page and the order of cards:** one plain line says what is left ("3 things need you. Next: ...") or "Nothing needs you." Cards are in true order: late or due today first, then important, then the oldest unanswered. Under Settings, "Appearance", you can group cards by sender, area or conversation (off to start) and choose the order (due first, newest first, oldest first, important first).
- **Standing approvals (what it does for you):** your assistant never acts for you unless you made a standing approval, and every one starts at "Ask first". After you have done the same kind of thing by hand in the same area a few times (5 to start; 3, 10 or never in Settings), a card offers to do it for you: yes and tell me, yes and do it quietly, or no. They are listed in Settings under "Approvals" where you can change a level, pause or remove any of them, and every use is listed on your page with an Undo, quiet ones too. Today they cover closing cards that need nothing and dropping waiting cards that came back with no reply. Sending an email is always your own Send press, with one exception you can say yes to: after you have sent several short replies to the same person, a card offers to send replies like those to that person for you (shown with real examples). It stays limited to that one person, replies to their own message, no copies, attachments or links, short, a few a day (a setting), every one listed on your page, and you can pause or remove it any time in Settings.
- **The weekly review:** one card on Friday afternoon (any day, any time, or off, under Settings, "Weekly review"), made from what your assistant already holds: what waits on you, what is past its date, cards that have sat, next week's calendar, what was hidden, what it learned this week, and what you snoozed to Someday. It costs no Claude usage. Press Done when you have been through it.
- **Reading back the history:** to record what happened to your matters before your assistant started, run it from a date: `python readback.py plan --since 2026-09-01` in `System\live` says how many conversations it would read and what it would cost in Claude usage (one run per 20 conversations, on the fastest model, nothing else); `python readback.py run --since 2026-09-01 --go` does it. It records tasks that came in, the answers you gave and what was completed, makes a card only for what is still open, and one summary card says what it found and what it was unsure about. Running it again adds nothing; running it from an earlier date adds only the older conversations.
- **Projects:** a project introduced to your assistant (with /assistant:introduce) can send it short notes: each new note in `Live\inbox\<project name>` becomes a card in the project's name. If you chose to let answers go back, typing an answer on such a card does not write anything: a second card shows the exact file and where it would go, and only your yes writes it, one file at a time, into that project's `From the assistant` folder. Each write is listed in `personal\projects.json` so an uninstall can find it.
- **Every press is kept:** each button you press on a card is recorded in your assistant's own database, with what happened, so nothing you press is lost.
- **What Settings cannot change:** accounts, sending email, where your page lives, and roadmaps. Those are changed only with a command typed in Claude on this computer (`/assistant:change`, or `/assistant:introduce` for projects and roadmaps), and no page can switch them.
- **Add an account, or sign one in again:** type `/assistant:change accounts` in Claude on this computer.
- **If your page shows a health line about an account** (for example "sign this account in again"): type `/assistant:change accounts` in Claude on this computer and choose to sign it in again.
- **To switch it off:** press the Windows key, type "Task Scheduler", open it, click "Task Scheduler Library", and for the job whose name starts with "Assistant live listener" right-click and choose "Disable" (or "Delete"). It serves your page and runs the 15-minute check. Each copy of the assistant on a computer has its own; the last step of the setup interview shows the exact name of yours.
- **To open your page from your phone, or stop that:** type `/assistant:change page` in Claude on this computer; see "Reaching your page from anywhere".
- **To apply the roadmap to a project, or take it off one:** type `/assistant:introduce` in Claude on this computer.
- **To change what it may do** (sending email): type `/assistant:change sending` in Claude on this computer.
- **Your data** is the folder named `Live` beside `System`. Back it up like any folder. The file `Live\personal\keys.dat` only works on this computer under your Windows account; on a new computer you sign in to each account again.

## What it can and cannot do

- It reads. It never deletes, moves or marks your mail, never posts anywhere, never texts, never changes your calendar.
- The one thing it can send is an email you write on your page and send yourself.
