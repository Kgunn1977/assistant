---
name: setup
description: Set up the assistant for a person, as a friendly interview of about 30 minutes - who they are, which accounts it reads (connecting each one and checking it works), other projects that should feed it, who and what matters and what is junk, how far back to read, where their page lives, and what it may send. Picks up where it stopped if run again. Use when the person types /assistant:setup or asks to set up their assistant.
disable-model-invocation: true
---

# Set up the assistant

Talk to the person in plain words, one thing at a time, numbered choices. No program words (no "path", "command", "PATH", "terminal output").

## First: is Python on this computer?

The assistant is a program written in Python, so this comes before anything else. Run exactly:

```
python --version
```

- It prints "Python 3." and a number: go on to "Then".
- Anything else (an error, "Python was not found", the Microsoft Store opening, or a version starting "Python 2"): say "Your computer needs one free program first, called Python. It takes about five minutes, and I tell you each click." Then walk these steps one at a time, waiting for "done" after each:
  1. In your browser, open python.org/downloads.
  2. Click the button "Download Python install manager".
  3. Open the file you downloaded (it is in your Downloads folder) and click "Install". Wait until it says it is finished.
  4. Open the Start menu, type Terminal, and open it. In the window that opens, type python and press Enter. If it asks a question (for example whether to install Python now, or to add something to your PATH), type y and press Enter, each time. When you see three arrows (>>>), type exit() and press Enter, then close that window.
  5. Close the Claude app completely: right-click the Claude icon near the clock at the bottom right of your screen and choose "Quit". Then open Claude again, open the same project, and type /assistant:setup again. Claude only notices Python after it starts again.
  Say "See you in a minute" and stop here.

Steps 1 to 3 rest on python.org's own pages (python.org/downloads, and "Using Python on Windows" at docs.python.org/3/using/windows.html, read 11/16/26, which name the install manager as the way to get Python and say "python" then works in any new window). Step 4's questions and step 5 are not on those pages; if the screen differs, believe the screen.

## Then

Read the file `${CLAUDE_PLUGIN_DATA}/setup_texts/interview.md` whole and follow it from "Starting, and picking up again". If that file is not there, Claude has not yet finished copying the assistant's parts: ask the person to close the Claude app completely (step 5 above), open it again and type /assistant:setup once more. If it is still not there after that, say plainly that the assistant's parts are missing on this computer and stop.
