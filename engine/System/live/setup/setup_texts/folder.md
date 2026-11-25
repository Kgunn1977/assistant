# Choosing the assistant's folder

Used by /assistant:setup (when the assistant is not on this computer yet) and by /assistant:adopt (where a moved assistant will live). Talk as `interview.md` "How you talk" says, with two exceptions: the suggestion C:\Assistant may be named as it is written, and in step 4 the folder's full place is said back once, exactly as Windows writes it, so they can check it.

`CHECK "<folder>"` below means: `python "${CLAUDE_PLUGIN_DATA}/engine/System/live/setup/setup_home.py" folder-check "<folder>"`. It answers whether that folder is kept in step by a cloud service (`synced`, `service`, `why`), whether it exists and is empty, whether an assistant is already in it, and where their Documents really is (`documents`).

## 1. Say what the folder is for

In your words, short: "I need one folder of my own on this computer. It holds my program and everything I keep about you: your messages, your cards, your sign-ins and my history. Pick a place where it can stay. Moving it later means setting me up again."

## 2. Work out the suggestions

Before offering anything, check each candidate with CHECK, quietly:
- **A new folder called Assistant in their Documents**: run `CHECK` with no folder first to learn where their Documents really is (`documents`), then `CHECK "<that>\Assistant"`.
- **C:\Assistant** (a folder at the top of the C: drive, outside every cloud service).
- **The folder this session is open in**, only if it is empty or is already the assistant's (the manual has some people make it before setup).
- For /assistant:adopt only: **where it is now**, and only folders on the same drive as where it is now (the move must be quick and copy nothing large); a folder that is not empty is not offered, apart from where it is now. `CHECK` where it is now: if its `other_things` is empty, offer "where it is now" first. If it holds other things too (other projects or files), put **a new folder called Assistant inside it** first instead, and say why in one line: "Staying where it is would make that whole folder mine, so Claude would follow my rules in everything else kept there too." Offer "where it is now" after it only if they still want it.

Leave out any candidate that is synced. If their Documents is synced, say so in one line: "Your Documents folder is kept in step with <service>, so I'm not suggesting it. <service> uploads every file and gets in the way when I change my own files."

## 3. Ask

"Where would you like it? 1 <first suggestion, plainly>, 2 <second>, ... , <n> somewhere else." At most three suggestions, then "somewhere else". Their choice decides.

For "somewhere else" (the last number): ask them to open the folder they want in File Explorer, click the address bar at the top, copy it and paste it here (or type it); then `CHECK` it. If it does not exist yet it will be made.

If the folder they chose is synced: say plainly, from `service` and `why`: "That folder is kept in step with <service>. <service> uploads every file and may lock or bring back old copies of them, which gets in the way when I change my files. I suggest a folder outside it, such as C:\Assistant." Then "1 choose another place (suggested), 2 use it anyway". Only on 2, and only after that warning, use it. On 1, ask step 3's question again with the same suggestions, without repeating what you already said about their Documents.

If it is not empty and not already the assistant's: say so and ask them to choose an empty or new folder.

## 4. Say the full place back

"I'll live here: <the full place, exactly as CHECK's `folder` gives it, for example C:\Assistant>. Is that right? 1 yes, 2 no, choose again." Go on only on yes.

If it is not the folder this session is open in, add: "From now on, open Claude in that folder when you want me."
