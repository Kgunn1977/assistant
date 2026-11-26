# Fix list
These are places the program must change to match Kevin's words; copied word for word from Requirements comparison.md Section 1 (original numbers in brackets).
Kevin's ruling 2026-11-25 followed: where his words and the coordinator's records differ, his words win.

[1] **1. Spec 1.1.** The box is a full interface to the assistant: it can add, move and delete calendar entries and draft and send email, not just talk about them.

- Your words: "It should also be able to draft and send emails."
- Coordinator's records, items A4.42, A4.50, A4.53, A4.115, A4.124 (built, 2026-11-11 to 2026-11-17): "Only two things send mail: the owner's Send press on the page, and a standing approval to send replies he accepted" (A4.115)
  - Difference: Only the owner's press or a standing approval sends; the box cannot send an email just because he told it to.
  - The records disagree with each other: The records disagree on how many kinds of thing may be sent: one, two or four.
- Coordinator's records, items A4.45, A4.49, A4.112, A4.121, A4.122, A4.127 (built, 2026-11-17 to 2026-11-18): "emails the chat writes wait in a Ready to send group at the top of the page, each with Send now, Edit and Discard" (A4.121)
  - Difference: The box never sends; every email it writes waits as a draft for a press.
- Coordinator's records, items A5.21, A5.23, A5.24, A5.25 (built): "goes in the Texts part of their page as a draft for them to edit and send" (A5.24)
  - Difference: A5.21 says sending is only ever the owner's own press of Send, while A5.23 lets the assistant send when his message says so
  - The records disagree with each other: A5.21 allows only the owner's own Send press, while A5.23 and A5.25 let the assistant send when his message asks
- Coordinator's records, items A9.25 (built): "Nothing goes out in the owner's name except a message they wrote and sent themself." (A9.25)
  - Difference: Records forbid sending anything the owner did not write and send himself, while Kevin wants the box to draft and send email for him
- Coordinator's records, items A27.6 (built): "It reads. It never deletes, moves or marks your mail, never posts anywhere, never texts, never changes your calendar." (A27.6)
  - Difference: Says it never changes the calendar or sends, where Kevin wants it to do everything
- Coordinator's records, items A20.26, A20.147 (built, 2026-11-18): "every email still waits for your Send press." (A20.147)
  - Difference: Records say every email waits for his Send press, while Kevin wants the box to send email when told to
- Coordinator's records, items A20.151, A20.167 (built, 2026-11-18 to 2026-11-23): "Some things stay yours alone on purpose: settings, standing approvals, passwords and sign-in." (A20.151)
  - Difference: Records keep settings and approvals out of the box's reach, while Kevin wants the box to do everything
- Other coordinator records match this requirement: items A1.11, A1.15, A1.16, A1.18, A1.31, A1.39, A1.46, A1.47, A1.48, A4.61, A6.10, A6.13, A6.17, A13.81, A20.3, A20.32, A20.33, A20.39, A20.98, A20.122, A20.156, A20.163, B5.4 (see Appendix).

[2] **2. Spec 1.2.** The box can organize mail: move messages between folders and mark them read or unread.

- Your words: "help me organize my emails, which means it has to have full access to move around folders"
- Coordinator's records, items A4.60 (built): "trash is always the service's own trash, never a deletion for good." (A4.60)
  - Difference: Mail changes are limited to the owner's own button press, not done by the assistant when he asks in the box.
- Coordinator's records, items A4.75, A4.108 (built): "changes nothing, and acts only when you answer yes in the next message." (A4.108)
  - Difference: Bulk changes asked in the box wait for a second yes before anything moves.
- Coordinator's records, items A28.10 (built): "Read only, except `send()` and `send_mime()`" (A28.10)
  - Difference: Account changes happen only on the owner's own press, not when the assistant is asked to organize mail.
- Coordinator's records, items A27.6 (built): "It reads. It never deletes, moves or marks your mail, never posts anywhere, never texts, never changes your calendar." (A27.6)
  - Difference: Says it never moves or marks mail, where Kevin wants it to organize mail
- Other coordinator records match this requirement: items A1.6, A1.12, A1.17, A1.49, A1.50, A4.33, A4.93, A20.99, A21.81 (see Appendix).

[3] **3. Spec 1.3.** The box can find cards by topic, close them as done, and list what it closed.

- Your words: "Look through my cards and close and mark as done anything related to"
- Coordinator's records, items A1.1, A1.2, A1.14, A1.19, A1.28, A1.34, A1.36, A1.51 (planned (A1.1, 2026-11-25); built (A1.2, A1.19, A1.28, A1.34, A1.36, A1.51, 2026-11-25); unclear (A1.14, 2026-11-25)): "Ask me how many cards, or which ones, and I search every card, open and closed." (A1.36)
  - Difference: One record says the box is handed only the 8 open cards that best match, while others say it searches every card
  - The records disagree with each other: One record says the box sees only the 8 best-matching open cards; the rest say it searches every card, open and closed
- Other coordinator records match this requirement: items A1.3 (see Appendix).

[4] **4. Spec 1.4.** When Kevin tells the assistant he needs to be somewhere, it puts it on the calendar with reminders 2 hours and 24 hours ahead (his approved rule for anything added to the calendar).

- Your words: "with a reminder 2 hours in advance and one day in advance"
- Coordinator's records: Nothing in the coordinator's records about adding reminders 2 hours and 24 hours ahead when something goes on the calendar.
- Difference: missing on the coordinator's side.

[5] **5. Spec 1.5.** Conversations about a card stay out of the box; each card conversation runs in its own small session.

- Your words: "Each card conversation should open its own small, lightweight session"
- Coordinator's records, items A1.21, A1.42 (built, 2026-11-17): "one Claude session for the day for everything that is a conversation with the owner" (A1.42)
  - Difference: The older record runs typed card answers inside the one daily conversation session instead of a separate session per card
  - The records disagree with each other: The older record puts typed card answers in the one daily session; the newer one gives each card its own small session
- Coordinator's records, items A1.29, A1.33, A1.40, A2.28 (built (A1.29, A1.33, A2.28, 2026-11-18); unclear (A1.40, 2026-11-18)): "A card reply becomes a chat message about that card, going to the same Claude with the same abilities" (A2.28)
  - Difference: Card conversations join the box's one shared conversation instead of staying out of it in their own session
- Coordinator's records, items A3.57, A3.199, A3.264 (built, 2026-11-17 to 2026-11-23): "Typing on a card goes into the same conversation as the box at the top, with the card attached" (A3.264)
  - Difference: Card typing joins the box's conversation instead of each card having its own separate conversation.
- Coordinator's records, items A13.63 (built): "One assistant everywhere: words typed on a card go to the same assistant as the chat at the top" (A13.63)
  - Difference: Records put card words into the same conversation as the box, while Kevin wants each card's conversation kept out of the box in its own session
- Other coordinator records match this requirement: items A3.25, A3.160, A3.278, A3.279 (see Appendix).

[6] **6. Spec 1.7.** A change to how the assistant works is asked for in the box itself; it produces a card with approve, disapprove and discuss, and there is no separate "change how your assistant works" link.

- Your words: "it just had to happen in the Claude desktop app instead of in the site"
- Coordinator's records, items A1.44 (built, 2026-11-19): "A change still goes ahead only when you press yes yourself." (A1.44)
  - Difference: Some steps still have to be finished in the desktop app rather than on the page
- Coordinator's records, items A21.4, A21.29 (dropped (A21.4, 2026-11-23); built (A21.29)): "The banner and its Yes button are gone." (A21.4)
  - Difference: A single Yes button starts the change instead of a card with approve, disapprove and discuss; records disagree on whether it is gone.
  - The records disagree with each other: One record still has the Yes make this change button as the go; the other says it was removed for the change card.
- Coordinator's records, items A21.7 (built, 2026-11-18): "treats any wish to change how your assistant works as a change and starts the walk-through itself" (A21.7)
  - Difference: Starts a talk-through in the chat rather than producing a card to approve, disapprove or discuss.
- Coordinator's records, items A21.36 (built): "Change a setting, or ask for a change to how your assistant works" (A21.36)
  - Difference: Keeps a separate way to ask for a change from Settings Tools, while Kevin wants changes asked only in the box.
- Coordinator's records, items A21.41, A21.73 (built, 2026-11-23): "You can ask for a change to how your assistant works in the page's chat and see it through there" (A21.41)
  - Difference: Records approve a change with a Yes and Cancel banner, while Kevin wants a card with approve, disapprove and discuss
- Coordinator's records, items A21.63 (built, 2026-11-17): "So a program change, and its undo, can be started from the page as well as from the computer." (A21.63)
  - Difference: Records disagree: an earlier answer said changes are made only from the computer, a later one allows the page
- Coordinator's records, items A21.53 (built, 2026-11-17): "New in the package: `/assistant:change` choices 6 and 7, `/assistant:undo`" (A21.53)
  - Difference: Records keep a Change how your assistant works link that Kevin asked to remove
- Other coordinator records match this requirement: items A1.13, A1.27, A1.37, A1.43, A2.12, A3.183, A12.109, A12.111, A20.100, A21.1, A21.2, A21.3, A21.17, A21.25, A21.37, A21.38, A21.42, A21.49, A21.51, A21.60, A21.65, A21.72, A21.74, A21.75, A21.76, A21.78, A21.83, A21.86, A28.16 (see Appendix).

[7] **7. Spec 2.1.** A card, the box and a desktop Claude session behave as the same assistant with the same abilities.

- Your words: "because they should all be the same. If they are not, you need to fix that."
- Coordinator's records, items A2.3, A2.7, A2.32 (built (A2.3, A2.7, 2026-11-19 to 2026-11-23); planned (A2.32, 2026-11-23)): "the desktop session does everything the box does, with the same checks, plus things only your PC can do." (A2.32)
  - Difference: Gives the desktop session abilities the page and cards do not have
- Other coordinator records match this requirement: items A1.29, A1.33, A1.40, A2.6, A2.9, A2.11, A2.15, A2.23, A2.26, A2.28, A2.29, A3.57, A3.199, A3.264, A4.66, A4.150, A10.81, A10.132, A10.133, A13.63, B5.4, B6.29 (see Appendix).

[8] **8. Spec 3.2.** The card's background is called Context, written as a narrative in which every message and paper is a link that opens it; there is no Evidence section.

- Your words: "every paper or message should be linked in the context narrative."
- Coordinator's records, items A3.65, A3.124, A3.230, A3.242 (built (A3.65, A3.124, A3.242, 2026-11-19); planned (A3.230, 2026-11-19)): "The opened card shows only Context, the draft (when there is one) and Conversation." (A3.124)
  - Difference: One record says Context listed the papers and email at the end instead of linking them inside the story.
  - The records disagree with each other: The plan links papers inside the story, but a later record says the built Context lists them at the end.

[9] **9. Spec 3.3.** Links to emails, documents and images open in a pop-up over the page, not by replacing the page; a PDF pop-up offers a download.

- Your words: "I think I would rather have that be a pop-up that is a separate window."
- Coordinator's records, items A3.42, A3.123, A3.267 (built, 2026-11-23): "links on a card (its emails, documents, pictures) open in a separate pop-up window instead of replacing your page" (A3.42)
  - Difference: Some records open links in a separate pop-up window, another opens them over the page.
  - The records disagree with each other: Two records say a separate pop-up window; another says the link opens over the page with Close returning to the card.
- Coordinator's records, items A3.268 (built, 2026-11-23): "If your browser blocks pop-ups, it falls back to today's full-page view." (A3.268)
  - Difference: Falls back to replacing the page, which Kevin asked to stop.
- Coordinator's records, items A3.65, A3.124, A3.230, A3.242 (built (A3.65, A3.124, A3.242, 2026-11-19); planned (A3.230, 2026-11-19)): "The opened card shows only Context, the draft (when there is one) and Conversation." (A3.124)
  - Difference: One record has papers open on the page itself, following Kevin's older words rather than a pop-up.
  - The records disagree with each other: The plan links papers inside the story, but a later record says the built Context lists them at the end.
- Other coordinator records match this requirement: items A3.119, A3.275, A4.1, A4.2, A4.92 (see Appendix).

[10] **10. Spec 3.4.** Every card has something to do (at least Done) and a place to write a response for a discussion with the assistant.

- Your words: "Every card should have something to do with it, even if it's just a done button."
- Coordinator's records, items A3.11 (built, 2026-11-25): "rule change / setting cards refuse Done, Got it, Snooze, Drop and Not needed" (A3.11)
  - Difference: These cards refuse Done, while Kevin wants every card to have at least Done.
- Other coordinator records match this requirement: items A3.67, A3.173, A3.201, A3.238, A3.246 (see Appendix).

[11] **11. Spec 3.8.** A card for something already done, or old news, is not shown as open or urgent.

- Your words: "Currently, there's the top card, the most urgent thing, is something from months ago that's already been done."
- Coordinator's records, items A20.144 (dropped, 2026-11-16): "Ask once. Never drop in silence." (A20.144)
  - Difference: Records drop the idea of clearing old cards automatically, while Kevin wants done or old cards not shown as open or urgent
- Other coordinator records match this requirement: items A3.35, A5.60, A5.63, A5.78, A14.5, A14.6, A14.21, A14.63 (see Appendix).

[12] **12. Spec 3.9.** Junk-ruling cards let him read the messages that were judged junk (all of them, not just one).

- Your words: "Cards judging junk should show all three emails that were judged junk."
- Coordinator's records, items A3.58, A3.59, A3.171, A3.224, A3.274 (built, 2026-11-19 to 2026-11-23): "Reading a sample doesn't mark the email read or change anything in your mailbox." (A3.224)
  - Difference: Opens the newest email and steps through recent ones, rather than showing all the emails that were judged junk.
- Coordinator's records, items A4.166, A4.167 (built, 2026-11-19): "junk and never-junk sender cards let Kevin read a sample message from that sender." (A4.166)
  - Difference: Shows one sample message instead of every message that was judged junk.

[13] **13. Spec 4.1.** All buttons are on the card's front, Done always at the top, no "More" menu, and the same button does the same thing on every card.

- Your words: "let's do away with the more altogether"
- Coordinator's records, items A9.62, A9.68 (built, 2026-11-16 to 2026-11-23): "The first two propose a plain-word rule for you to approve." (A9.62)
  - Difference: The press sits under a More menu on the card
  - The records disagree with each other: One record says the This sender choice proposes a rule to approve; a later one says it puts the sender on the ignored list right away
- Coordinator's records, items A11.82 (built, 2026-11-16): "A card shows its one or two main buttons and" (A11.82)
  - Difference: Keeps a More menu and hides most buttons behind it, where Kevin wants all buttons on the front and no More
- Other coordinator records match this requirement: items A3.64, A3.121, A3.231, A3.232 (see Appendix).

[14] **14. Spec 4.5.** A Save button sits next to the text box at all times; pressing it sends the text and closes the card in one step.

- Your words: "I could just hit save and it sends it and closes the card."
- Coordinator's records, items A3.266 (built, 2026-11-23): "if the answer needs you, for example a proposed rule, the card stays open until you've answered." (A3.266)
  - Difference: The card stays open after Save while a rule awaits an answer instead of always closing.
- Other coordinator records match this requirement: items A3.19, A3.161, A3.256 (see Appendix).

[15] **15. Spec 4.7.** A card with several questions works as nested cards: each question closes when answered, and the main card closes only when all are settled; each answer is acted on.

- Your words: "I should be able to answer all the questions without the card closing."
- Coordinator's records, items A3.62 (built, 2026-11-19): "Answer buttons still close at once." (A3.62)
  - Difference: An answer button closes the card at once, while Kevin wants to answer every question before it closes.
- Other coordinator records match this requirement: items A3.34, A3.117, A3.122, A3.140, A3.141, A3.142, A3.143, A3.152, A3.304, A3.305 (see Appendix).

[16] **16. Spec 4.8.** A question on a card exists to act on the answer: answering it leads to the action (for example a draft reply, a calendar entry).

- Your words: "There's no point in asking me a question if you're not going to do anything useful with it."
- Coordinator's records, items A3.293 (built, 2026-11-25): "A button alone never changes your calendar; that still takes your own words." (A3.293)
  - Difference: A yes button on a card cannot add the calendar entry; only typed words can, so answering yes by button does not act.
- Other coordinator records match this requirement: items A1.30, A3.14, A3.15, A3.16, A3.111, A3.114, A3.115, A3.157, A3.184, A3.291, A3.292, A3.294, A20.143 (see Appendix).

[17] **17. Spec 4.9.** Done and Drop are separate: Done means he did the task; Drop removes the card from consideration unless the matter comes up again.

- Your words: "drop says for one reason or another I don't want this card considered"
- Coordinator's records, items A10.83, A10.136 (built, 2026-11-23): "Done is the state, with Put away and Drop it only as button labels." (A10.136)
  - Difference: Drop is folded into the Done state instead of being its own separate outcome
- Coordinator's records, items A12.11, A12.26, A12.28, A12.90, A12.145 (planned (A12.11, 2026-11-25); built (A12.26, A12.28, A12.90, A12.145, 2026-11-24 to 2026-11-25)): "Done, Got it and Drop are three different answers when matched against the pick." (A12.11)
  - Difference: Records disagree: some treat Done, Got it and Drop as different answers, others count Done and Got it as neutral for scoring.
  - The records disagree with each other: Some records make Done, Got it and Drop three different answers; others make Got it, Done and No all neutral.
- Other coordinator records match this requirement: items A3.4, A3.5, A3.39, A3.40, A3.104, A3.105, A3.155, A3.296 (see Appendix).

[18] **18. Spec 4.10.** A snoozed card has a Next week button that brings it back on Monday.

- Your words: "on a snooze card, add a next week button that brings it back on Monday."
- Coordinator's records, items A3.47 (built, 2026-11-25): "Next week on Snooze already exists (back Monday 6:00 AM): turn it on in Settings, Snooze options." (A3.47)
  - Difference: The Next week choice must first be switched on in Settings rather than simply being on the snooze card.

[19] **19. Spec 5.1.** All cards are in one feed filtered by buttons at the top, not separate collapsible sections; the filter titles are the names used.

- Your words: "All the cards should be in one section that's filterable with the buttons up top."
- Coordinator's records, items A11.35, A11.36, A11.37, A11.53, A11.61, A11.71, A11.87, A11.120 (built (A11.35, A11.36, A11.37, A11.53, A11.61, A11.87, A11.120, 2026-11-18 to 2026-11-19); planned (A11.71, 2026-11-17)): "you can drag every part of the page, each roadmap on its own, into Top, Bottom, Left or Right." (A11.87)
  - Difference: A conflict note says the separate card sections this arranger moved were later replaced by one card feed
- Other coordinator records match this requirement: items A3.32, A3.134, A3.164, A3.249, A3.250, A3.251, A3.252, A3.253, A3.255, A11.48 (see Appendix).

[20] **20. Spec 5.2.** The feed has the kinds Waiting on others, Waiting and Someday.

- Your words: "I want waiting on others. Waiting and someday."
- Coordinator's records, items A3.134, A3.251, A3.255 (built, 2026-11-23): "Each filter button shows its kind of card and its count." (A3.251)
  - Difference: One record lists a single Waiting filter and Held back, another lists Waiting on others, Someday and Hidden with no Waiting button.
  - The records disagree with each other: One record names the filters Waiting and Held back; later ones split Waiting and say Hidden replaces Held back.
- Coordinator's records, items A3.46, A3.158, A3.290 (built, 2026-11-25): "split Waiting into two buttons, Waiting on others and Someday, each with its count." (A3.46)
  - Difference: Waiting is replaced by two buttons, while Kevin listed Waiting on others, Waiting and Someday as three kinds.
- Coordinator's records, items A3.209, A3.288 (built, 2026-11-16 to 2026-11-25): "It stays there until you open it and press Bring back." (A3.288)
  - Difference: One record files Someday cards under Waiting, while another record says Someday is its own button.
  - The records disagree with each other: A record says Someday moves a card to Waiting, while a conflicting record says Waiting is split into Waiting on others and Someday.
- Coordinator's records, items A11.48 (built): "ONE list, with no headings or folds inside it." (A11.48)
  - Difference: The filters have Waiting on others and Someday but no plain Waiting kind

[21] **21. Spec 5.5.** The last card in the feed opens all held-back messages.

- Your words: "have a card that allows you to look at all the held back messages."
- Coordinator's records, items A11.80 (built, 2026-11-16): "one folded line shows everything filtered out today" (A11.80)
  - Difference: Held-back messages show in one folded line, not as a card at the bottom of the feed
- Other coordinator records match this requirement: items A3.33, A3.165 (see Appendix).

[22] **22. Spec 6.2.** When something written on a card looks like a rule, a row of buttons (Approve, Disapprove, Discuss, Cancel) appears under the reply in the card with the proposed rule written out.

- Your words: "writing the proposed rule with approve, disapprove, and discuss, and cancel as buttons"
- Coordinator's records, items A9.11, A9.39, A9.47, A9.50, A9.64 (built (A9.11, A9.39, A9.47, A9.64, 2026-11-18); unclear (A9.50, 2026-11-17)): "a correction he gives becomes his rule, shown back, listed in Settings, obeyed by every card writing, removable" (A9.39)
  - Difference: Earlier records save the correction straight away with a Saved line, with no proposed rule and no Approve step
- Coordinator's records, items A9.18, A9.30, A9.69 (built, 2026-11-23): "Nothing takes effect until you press Approve." (A9.69)
  - Difference: The proposed rule comes as a separate card rather than a row of buttons under the reply inside the same card
- Other coordinator records match this requirement: items A3.27, A3.107, A3.265, A3.266, A3.300, A9.4, A9.6, A9.35, A9.36, A9.48, A9.57, A9.74, A9.75, A9.76, A9.79, A9.83, A9.93, A13.80, A21.77 (see Appendix).

[23] **23. Spec 6.4.** The assistant ships with core rules (how the system works); a user's personal rules (decisions) start from an onboarding interview and grow as he uses it.

- Your words: "Core rules are mostly the rules i make regarding how the SYSTEM works."
- Coordinator's records, items A23.4 (built, 2026-11-24): "Start fresh decides core by the starter's entry numbers" (A23.4)
  - Difference: Core is decided by entry numbers, so Kevin's own rules about how the system works would land among personal rules.
- Other coordinator records match this requirement: items A9.1, A9.2, A9.3, A9.19, A9.28, A9.40, A9.44, A9.51, A9.52, A9.54, A9.55, A9.86, A12.107, A16.5, A16.27, A16.42, A16.87, A16.103, A16.112, B1.9, B1.14, B1.87 (see Appendix).

[24] **24. Spec 6.6.** Each message source keeps its own rule book (email, texts, and any added source such as Slack).

- Your words: "Every message source has it's own rule book. Email, text, slack in my case."
- Coordinator's records, items A9.3, A9.55 (planned, 2026-11-24 to 2026-11-25): "Some sections will have their own special rule sets" (A9.55)
  - Difference: Records keep one general rule book with special sets only for some sections, not a separate rule book for each message source
- Other coordinator records match this requirement: items A12.50, A12.119 (see Appendix).

[25] **25. Spec 7.1.** The loop is built the way the video lays it out; this is the core of the product.

- Your words: "You can't judge your own work."
- Coordinator's records, items A29.1 (built, 2026-11-24): "one step stronger where the graded layer runs on Haiku or Sonnet (first sort, rule writing)." (A29.1)
  - Difference: Records disagree on whether the grader has its own instructions or reuses the instructions of the parts it grades
- Coordinator's records, items A12.109, A12.111 (dropped (A12.109, 2026-11-16); built (A12.111, 2026-11-18)): "once changes work in the chat, those cards have no job left. I'd remove them as part of this build" (A12.111)
  - Difference: One record says self-improvement was ended, while a later record describes a new self-improvement feature as built.
- Coordinator's records, items A19.224 (built, 2026-11-17): "may only be set on a row with at least one check, enforced by the roadmap plugin." (A19.224)
  - Difference: Lets Claude mark its own checked work as done and confirmed, where Kevin says Claude cannot judge its own work.
- Coordinator's records, items B8.10, B8.21, B8.23 (built, 2026-11-19 to 2026-11-20): "The roadmap only asks you for what I truly can't do" (B8.23)
  - Difference: The builder checks its own work before calling it ready, while Kevin says work cannot be judged by whoever made it
- Coordinator's records, items B6.47 (built, 2026-11-21): "Anything that sends gets one real try, asked first." (B6.47)
  - Difference: Relies on the builder's own single look at a change rather than a separate check by someone who did not build it.
- Coordinator's records, items B6.49 (dropped, 2026-11-21): "After a helper builds something, a different session tries it out on a test copy of your page" (B6.49)
  - Difference: This independent tryout was dropped and replaced by one look at the real page, while Kevin's later word is that the builder can't judge its own work.
- Other coordinator records match this requirement: items A12.108, A12.129, A13.2, A13.14, A13.68, B1.5, B2.82, B3.16, B6.7, B6.8, B6.20, B6.24, B6.25, B6.26, B6.27, B6.77, B6.78, B6.80, B6.82, B6.87, B9.20, B9.21 (see Appendix).

[26] **26. Spec 7.3.** The coach proposes one change at a time in a draft beside the live version, never touches the live version, the rule book or the grader, and keeps past versions and rejected drafts with a one-line reason each.

- Your words: "It never touches the answer key or the verifier."
- Coordinator's records, items A20.6 (planned, 2026-11-24): "amending A15 for Level 3, and the new coach-draft guardrail." (A20.6)
  - Difference: Records disagree on whether the coach needs its own guardrail; a build note says none is needed because the coach has no tools
- Other coordinator records match this requirement: items A12.2, A12.20, A12.21, A12.22, A12.35, A12.41, A12.48, A12.49, A12.53, A12.72, A12.74, A12.75, A12.102, A12.126, A12.133, A12.134, A12.135, B1.5, B1.11 (see Appendix).

[27] **27. Spec 7.4.** There is no starting answer key: the rule book is built from what Kevin does, and every miss becomes a new entry.

- Your words: "It is built as the user interacts with the assistant. It learns."
- Coordinator's records, items A13.83 (built, 2026-11-25): "The judge predicts before you act." (A13.83)
  - Difference: Records disagree: one calls it built, a later one the same day puts the judgment rebuild back to unfinished
- Other coordinator records match this requirement: items A9.28, A12.1, A12.15, A12.34, A12.40, A12.47, A12.69, A12.77, A12.78, A12.80, A12.99, A12.112, A12.123, A12.146, A15.51, A25.1, B1.9 (see Appendix).

[28] **28. Spec 7.5.** Each area of the assistant has its own trust level setting (the video's three levels); all areas learn at once and all start at level 1.

- Your words: "I want different aspects of the assistant to individually have settings."
- Coordinator's records, items A12.10, A12.16, A12.17, A12.42, A12.97, A12.118, A12.137, A12.138 (planned (A12.10, A12.118, 2026-11-25); built (A12.16, A12.17, A12.42, A12.97, A12.137, A12.138, 2026-11-24 to 2026-11-25)): "Level settings are per area of the assistant, not per judgment." (A12.137)
  - Difference: An earlier record gives each single judgment its own level; later records set levels per area as Kevin asked.
  - The records disagree with each other: One record puts a level on each judgment; the others put it on each of six areas.
- Other coordinator records match this requirement: items A9.60, A9.94, A12.6, A12.32, A13.19, A13.20, A13.21, A13.23, A13.29, A13.89, A15.9, A15.47, A15.49, A15.73, A15.75, A16.17, A16.40, A20.29, A20.66, A20.86, A20.159, B1.2, B1.12 (see Appendix).

[29] **29. Spec 7.8.** At level 2 the loop proposes a change and shows both scores, the change, and promote or reject; it never promotes on its own. Level 3 (automatic) stops after 10 tries.

- Your words: "it shows you both scores, the change, and one choice: promote or reject"
- Coordinator's records, items A3.12 (built, 2026-11-25): "one open card per section; Undo after Promote, Apply or Reject takes nothing back." (A3.12)
  - Difference: Says a proposal card with Promote, Apply or Reject, but not that it shows the old and new scores.
- Coordinator's records, items A9.60, A9.94, A13.19, A13.20, A13.21, A13.29, A13.89 (built (A9.60, A13.89, 2026-11-16 to 2026-11-25); planned (A9.94, A13.29, 2026-11-25); unclear (A13.19, A13.20, A13.21, 2026-11-25)): "Level 2 does things and tells you, with undo. Level 3 does them quietly, with a daily summary." (A13.89)
  - Difference: Records make level 2 act on its own and tell him with undo, and level 3 act quietly with a daily summary, instead of level 2 proposing a scored change to promote or reject and level 3 looping up to 10 tries
- Coordinator's records, items A10.38 (planned, 2026-11-25): "| Retire | Don't learn from this | Rule book button" (A10.38)
  - Difference: The choice is labeled Approve instead of promote
- Coordinator's records, items A12.8, A12.61, A12.62, A12.66, A12.94 (planned (A12.8, 2026-11-25); built (A12.61, A12.62, A12.66, A12.94, 2026-11-25)): "for things it's good at, it does them itself and tells you, with undo." (A12.8)
  - Difference: Here level 2 means the assistant acts on its own with undo; in Kevin's accepted plan level 2 proposes a change for him to promote or reject.
- Coordinator's records, items A12.9, A12.67 (planned (A12.9, 2026-11-25); built (A12.67)): "it does them quietly, and they show up in a daily summary." (A12.9)
  - Difference: Level 3 here means acting quietly with a daily summary; in Kevin's accepted plan level 3 is the automatic improvement loop capped at 10 tries.
- Coordinator's records, items A12.25, A12.29, A12.60, A12.81, A12.82, A12.127, A12.139, A12.140 (planned (A12.25, A12.127, 2026-11-24 to 2026-11-25); built (A12.29, A12.60, A12.81, A12.82, A12.139, A12.140, 2026-11-16 to 2026-11-25)): "A change goes live on its own only if it scores better and breaks nothing that passed before." (A12.140)
  - Difference: Records disagree whether level 3 is switched on or held off until a guardrail change is approved.
  - The records disagree with each other: One record holds level 3 switched off until a guardrail change is approved; a conflicting record says that was approved on 11/25.
- Coordinator's records, items A12.65 (built): "shown as a Pick change card with Approve at level 1; Approve makes it" (A12.65)
  - Difference: Pick changes get a plain Approve at level 1 instead of a level 2 card with both scores and promote or reject.
- Other coordinator records match this requirement: items A12.2, A12.22, A12.24, A12.35, A12.41, A12.83, A12.85, A12.86, A12.98, A12.102, A12.134, A12.135, A20.4, A20.7, A29.3, B1.6, B1.12 (see Appendix).

[30] **30. Spec 7.9.** The judgment learns from everything he does, including how he writes and the decisions he makes, and only acts on its own with his permission; it learns more than show or hide.

- Your words: "The RSI should be learning a lot more than just show and hide."
- Coordinator's records, items A12.36, A12.46 (unclear (A12.36, 2026-11-25); built (A12.46, 2026-11-25)): "Decisions, wording, timing and urgency all learn this way, not just show or hide." (A12.36)
  - Difference: What is built so far learns only show or hide; the wider learning still waits on a later rebuild.
  - The records disagree with each other: One record says all kinds of decisions learn; another says only show or hide is learned so far.
- Coordinator's records, items A16.102 (planned, 2026-11-25): "Took 3b as: a Card press only makes that card and teaches nothing." (A16.102)
  - Difference: A Card press is kept out of the learning, while Kevin wants the judgment to learn from everything he does.
- Other coordinator records match this requirement: items A9.16, A9.49, A9.58, A9.92, A10.3, A10.63, A10.87, A10.90, A10.94, A10.100, A10.103, A10.104, A10.112, A10.126, A10.139, A10.140, A10.141, A10.142, A12.1, A12.3, A12.4, A12.5, A12.7, A12.8, A12.13, A12.23, A12.30, A12.34, A12.37, A12.38, A12.39, A12.40, A12.55, A12.56, A12.61, A12.62, A12.63, A12.66, A12.69, A12.71, A12.93, A12.94, A12.96, A12.112, A13.1, A13.16, A13.17, A13.26, A13.66, A13.67, A13.87, A16.114, A20.29, A20.66, A20.86, A20.159, B1.4, B1.13 (see Appendix).

[31] **31. Spec 7.11.** People who are often in touch with Kevin and ask for something rank higher than others who ask; judging what matters is central.

- Your words: "people who are frequently in contact with the user and ask for something should be higher in the priority list"
- Coordinator's records, items A3.31, A3.261, A3.262 (built, 2026-11-23): "Priority senders no longer push cards up on their own." (A3.262)
  - Difference: Who sent it no longer raises a card in the Importance sort on its own.
- Coordinator's records, items A20.42 (built): "An important card says why it is important" (A20.42)
  - Difference: Records limit importance to the owner's own list, while Kevin wants frequent contacts who ask for things ranked higher
- Other coordinator records match this requirement: items A3.132, A3.133, A7.9, A7.19, A7.20, A7.23, A7.31, A13.31, A13.52 (see Appendix).

[32] **32. Spec 7.12.** When the assistant is unsure what he means, it asks instead of guessing.

- Your words: "If it was confused, it should have asked."
- Coordinator's records, items A1.35 (built): "Asking me to handle one email by description" (A1.35)
  - Difference: Picks the newest match and acts instead of asking which email he meant
- Coordinator's records, items A3.151, A3.299 (built, 2026-11-25): "when no rule covers a message, the card will say so and show the assistant's best guess" (A3.299)
  - Difference: Shows a best guess when its rules do not cover something, rather than asking.
- Coordinator's records, items A10.20, A10.32 (planned, 2026-11-25): "You haven't told me how to handle this kind yet. My guess:" (A10.32)
  - Difference: When not covered it offers a labeled guess instead of asking first
- Other coordinator records match this requirement: items A9.26, A12.122, A13.10, A13.15, A13.30, A13.40, A13.46, A13.58, A13.82, A14.23 (see Appendix).

[33] **33. Spec 8.1.** A user's changes live apart from the core program, with their own connectors and processes; they override how the core behaves but never edit core code.

- Your words: "User changes supersede core code, but do not change it."
- Coordinator's records, items A28.11, A28.26 (built, 2026-11-17): "Taught connection types load after the general ones; a general type with the same name wins." (A28.26)
  - Difference: On a name clash the core version wins over the user's own, the reverse of user changes overriding the core.
- Coordinator's records, items A9.56 (built, 2026-11-17): "A taught rule may only add: a new rule for guards (a) or (b), or a stricter limit on an existing one" (A9.56)
  - Difference: Taught rules may only add or tighten, so a user's rule can never override a general one, while Kevin says user changes override the core
- Coordinator's records, items A17.65, A17.101, A17.147, A17.148 (built, 2026-11-16 to 2026-11-17): "An update goes through every change you made yourself and asks you what to keep, before anything is written." (A17.101)
  - Difference: Treats the owner's changes as edits inside the core program that an update must merge, instead of keeping them apart from it.
- Coordinator's records, items A17.97 (built): "An update only asks you about a change of yours that truly clashes with it, and says why" (A17.97)
  - Difference: Assumes the owner's changes can clash with the program during an update, rather than sitting apart where updates never reach them.
- Coordinator's records, items A17.130, A17.134, A17.135 (built, 2026-11-17): "asks per file: keep mine, take the update, or combine both" (A17.134)
  - Difference: Expects the owner to have edited the core program's own files, which updates then merge, instead of keeping changes apart.
- Coordinator's records, items A21.44, A21.57 (unclear, 2026-11-17): "What he changes through /assistant:change outside those sessions stays outside the core, on his PC only, and never goes into the repo" (A21.44)
  - Difference: One record keeps his changes out of the core; another says his copy feeds the general part to everyone at release
  - The records disagree with each other: A21.44 keeps his changes outside the core; A21.57 says what he teaches the general part reaches everyone
- Other coordinator records match this requirement: items A8.6, A9.12, A9.66, A11.86, A16.51, A17.19, A17.23, A17.25, A17.56, A17.175, A20.54, A20.55, A20.58, A20.124, A20.146, A20.169, A21.8, A21.11, A21.12, A21.13, A21.15, A21.23, A21.26, A21.34, A21.40, A21.45, A21.46, A21.47, A21.68, A21.87, A21.88, A23.10, A28.16, A28.19, A28.28 (see Appendix).

[34] **34. Spec 8.2.** When a user makes a change, check cards appear on the page to confirm it works.

- Your words: "it should have check cards like this that verify that the mod works."
- Coordinator's records, items A21.71, A21.85 (built (A21.71, 2026-11-20); unclear (A21.85, 2026-11-20)): "the mod is marked proven and its check cards leave." (A21.71)
  - Difference: Records say check cards exist, but his real page had none
  - The records disagree with each other: A21.71 says check cards appear; A21.85 found none on his real page
- Other coordinator records match this requirement: items A21.18, A21.19, A21.22, A21.32, A21.33, A21.39 (see Appendix).

[35] **35. Spec 8.3.** Slack is Kevin's own addition, not part of the core; email and texts are the core channels.

- Your words: "SLACK IS NOT A CORE PART OF THIS PROJECT."
- Coordinator's records, items A8.1, A8.3, A8.5, A8.7, A8.12, A8.14, A8.16, A8.17, A8.26, A8.27, A8.29 (planned (A8.1, A8.3, A8.26, 2026-11-22 to 2026-11-25); built (A8.5, A8.7, A8.12, A8.16, A8.17, A8.27, A8.29, 2026-11-23 to 2026-11-25); dropped (A8.14)): "Slack is one of your own additions, not part of the core assistant everyone gets." (A8.5)
  - Difference: Older records describe Slack as a full built-in part of the page, while later ones make it an add-on
  - The records disagree with each other: One older record makes Slack a full built-in part of the page; the rest make it an add-on outside the core
- Other coordinator records match this requirement: items A8.28, A17.173 (see Appendix).

[36] **36. Spec 8.4.** In Kevin's Slack addition, a maintenance request card says what the issue is.

- Your words: "Maintenance request from Slack should show on the card what the issue is."
- Coordinator's records: Nothing in the coordinator's records about a Slack maintenance request card naming the issue.
- Difference: missing on the coordinator's side.

[37] **37. Spec 8.6.** In Kevin's Ramp addition (receipts only): a receipt photo is matched to the purchase, categorized, memo written and finalized on its own; when the category is unclear he gets a card with where and when and one button per category.

- Your words: "this is only for recording reciepts. that's all I want it to do."
- Coordinator's records, items A1.52 (built, 2026-11-17): "Your words count as the go." (A1.52)
  - Difference: Records disagree on whether the chat may touch receipt records at all
- Coordinator's records, items A28.28 (unclear, 2026-11-17): "just make sure the assistant is able to absorb new connectors." (A28.28)
  - Difference: Receipts always ask first and only later offer to act alone, instead of filing on their own unless the category is unclear.
- Other coordinator records match this requirement: items A3.310, A20.165, A21.88, A28.29, A28.30, A28.32, A28.33 (see Appendix).

[38] **38. Spec 9.1.** The page is a full email client, enough that Kevin can stop using his other mail programs, reading all his accounts.

- Your words: "you should have WAY more than 2 email addresses you're reading"
- Coordinator's records, items A16.63 (built): "mailbox is not covered by the assistant yet" (A16.63)
  - Difference: Some personal mail accounts cannot be read at all, while Kevin wants every one of his accounts read.
- Other coordinator records match this requirement: items A4.9, A4.14, A4.15, A4.16, A4.23, A4.30, A4.32, A4.62, A4.63, A4.72, A4.73, A4.99, A4.100, A4.103, A4.105, A4.113, A4.132, A4.133, A4.138, A4.139, A4.146, A4.168, A4.169, B1.49 (see Appendix).

[39] **39. Spec 9.3.** From a card, the right kind of email is offered (reply, forward, new), with attaching emails and files.

- Your words: "A forward, a new email. Like, I should have those options in the card."
- Coordinator's records, items A3.179, A3.200 (built (A3.179); planned (A3.200, 2026-11-17)): "Cards made from a message have a Reply button among their main buttons, when sending is switched on." (A3.179)
  - Difference: Offers only Reply, and the records disagree on whether it landed.
  - The records disagree with each other: One record says the Reply button is built, while a conflicting note says it had not landed.
- Coordinator's records, items A4.114 (built, 2026-11-17): "A draft goes only to people in the card's own messages or the one person on file" (A4.114)
  - Difference: Drafts carry no copy and no added attachment, so attaching files from a card is ruled out.
- Coordinator's records, items A4.118 (built, 2026-11-17): "No blind copy; at most 20 recipients, each a plain address; subject and message not empty" (A4.118)
  - Difference: Attachments are limited to files already held for that card; the records also disagree on whether blind copy is allowed.
- Coordinator's records, items A4.170 (dropped, 2026-11-18): "It goes out as a brand-new email, without the original message history or the invoice attachment" (A4.170)
  - Difference: Describes a forward that loses the original and its attachment; marked dropped and replaced by the full email plan.
- Coordinator's records, items A20.38, A20.46 (built): "A draft goes only to people in the card's own messages or the one person on file" (A20.46)
  - Difference: Records keep the assistant from adding any attachment to a draft, while Kevin wants attaching emails and files offered from the card
- Other coordinator records match this requirement: items A4.64, A4.71, A4.101, A4.129, A4.130, A4.171 (see Appendix).

[40] **40. Spec 9.4.** Accounts can be reordered; each account's folder group collapses with the page's line style; an open email can pop out (several at once); the divider between folders and mail can be dragged.

- Your words: "When we open an email, we should have an option to pop it out"
- Coordinator's records, items A11.108 (planned, 2026-11-20): "Mailbox drag, fold, resize and Pop out are not on Kevin's assistant." (A11.108)
  - Difference: Reordering accounts, folding them, resizing and popping out mail are not in the live assistant
- Other coordinator records match this requirement: items A4.8, A4.36, A4.37, A4.38, A4.147, A4.159 (see Appendix).

[41] **41. Spec 9.6.** Emails show as sent, with HTML and pictures; internet pictures are shown by default.

- Your words: "Pictures from the internet on hidden should be off by default. We should show the pictures."
- Coordinator's records, items A4.10, A4.29, A4.95, A4.155 (built, 2026-11-20 to 2026-11-21): "pictures in emails show by default, and hiding them is a setting you can turn on" (A4.10)
  - Difference: One record still has internet pictures wait for a Show pictures press instead of showing by default.
  - The records disagree with each other: One record keeps internet pictures hidden until pressed while the others show them by default.
- Coordinator's records, items A4.27, A4.28, A4.77, A4.106, A4.145, A4.164 (built, 2026-11-20): "An HTML email shows formatted, in a frame without scripts, with links opening in a new tab." (A4.164)
  - Difference: Two of these records block internet pictures until Show pictures is pressed, instead of showing them by default.
- Coordinator's records, items A20.30, A20.64 (built): "this module is the second lock: whatever could run, send or reach out is taken out here before the page ever gets it." (A20.30)
  - Difference: Records hold internet pictures back until asked, while Kevin wants them shown by default

[42] **42. Spec 9.9.** Drafts waiting to go out live inside the mail section: the mail header says mail is ready to send, with a button that opens the drafts.

- Your words: "Ready to send should become drafts."
- Coordinator's records, items A2.16, A2.17, A2.30 (built, 2026-11-19): "They land in Ready to send on your page for you to press Send, the same as from a card or the chat." (A2.30)
  - Difference: Drafts go to a separate Ready to send area rather than Drafts inside the mail section
- Coordinator's records, items A4.45, A4.49, A4.112, A4.121, A4.122, A4.127 (built, 2026-11-17 to 2026-11-18): "emails the chat writes wait in a Ready to send group at the top of the page, each with Send now, Edit and Discard" (A4.121)
  - Difference: Drafts wait in a separate group at the top of the page, not inside the mail section.
- Coordinator's records, items A4.98 (built): "Ready to send is a part of the page like the others" (A4.98)
  - Difference: Keeps a separate always-shown Ready to send part instead of drafts inside the mail section.
- Coordinator's records, items A11.89, A11.121 (built, 2026-11-18): "In Settings you can move it, sort it or turn it off like the other parts." (A11.89)
  - Difference: Keeps Ready to send as a separate page part instead of a notice and button inside the mail section
  - The records disagree with each other: One record says it always shows and can be arranged; the other says it cannot be arranged and shows only with drafts
- Other coordinator records match this requirement: items A4.7, A4.157 (see Appendix).

[43] **43. Spec 9.10.** Send all asks for a second confirmation.

- Your words: "I changed my mind. Leave that second check in."
- Coordinator's records: The records describe a Send all press for drafts (A4.112, A4.121, A4.122) but nothing about a second confirmation before Send all goes out.
- Difference: missing on the coordinator's side.

[44] **44. Spec 9.11.** When told to send several emails, all of them are sent; none is left in Drafts.

- Your words: "because the prompt clearly said send 3 emails"
- Coordinator's records, items A1.7 (built, 2026-11-26): "instead of giving up at once, and if it is still busy says so plainly" (A1.7)
  - Difference: Allows a busy reply that leaves emails unsent instead of making sure every one goes out
- Coordinator's records, items A4.42, A4.50, A4.53, A4.115, A4.124 (built, 2026-11-11 to 2026-11-17): "Only two things send mail: the owner's Send press on the page, and a standing approval to send replies he accepted" (A4.115)
  - Difference: Emails the assistant writes wait for a press instead of all going out when he says send.
  - The records disagree with each other: The records disagree on how many kinds of thing may be sent: one, two or four.
- Coordinator's records, items A4.45, A4.49, A4.112, A4.121, A4.122, A4.127 (built, 2026-11-17 to 2026-11-18): "emails the chat writes wait in a Ready to send group at the top of the page, each with Send now, Edit and Discard" (A4.121)
  - Difference: Told to send several emails, the box leaves them all as drafts.
- Coordinator's records, items A20.26, A20.147 (built, 2026-11-18): "every email still waits for your Send press." (A20.147)
  - Difference: Records hold every email for a Send press, while Kevin expects emails he tells the box to send to go out

[45] **45. Spec 10.1.** Texts (including RCS) are read and sent from the page through a real connection to Google Messages, not by reading and typing into a web page; the old text connection is gone.

- Your words: "We're literally reading a web page and typing into the web page. So that's not I/O."
- Coordinator's records, items A5.9, A5.45, A5.50 (built (A5.9, A5.50, 2026-11-20); dropped (A5.45)): "Texts, RCS chats included, can now be read from your own Google Messages for web tab" (A5.45)
  - Difference: reads texts from a web page in a browser tab instead of a real connection
  - The records disagree with each other: A5.45 is marked dropped because a later record replaced the extension with a direct link, while A5.9 and A5.50 are marked built
- Coordinator's records, items A5.11, A5.57, A5.61, A5.62 (built, 2026-11-20 to 2026-11-22): "type the text the way a person would, wait for the real Send button, press it" (A5.61)
  - Difference: sends by typing into a web page tab rather than through a real connection
  - The records disagree with each other: A5.57 says texts go out through the tab, while a record from 11/20 says the extension was for reading only with no sending
- Other coordinator records match this requirement: items A5.10, A5.12, A5.19, A5.20, A5.29, A5.37, A5.46, A5.80, A5.83, A5.85, A16.64, A16.98 (see Appendix).

[46] **46. Spec 10.5.** Pictures sent in texts show on the page.

- Your words: "So if I send myself a picture, it should show up."
- Coordinator's records, items A5.56 (planned, 2026-11-20): "It only notes that a message had a photo or attachment; it doesn't save the picture itself." (A5.56)
  - Difference: only notes that a picture was sent instead of showing it
- Coordinator's records, items A13.33, A13.49 (built): "They go into a database and become the only record once the image file ages out." (A13.49)
  - Difference: Records keep only a written description once the picture file ages out, rather than the picture itself
- Other coordinator records match this requirement: items A5.5, A5.34, A5.42, A5.90, A5.92, A5.94, A5.95, A5.97 (see Appendix).

[47] **47. Spec 10.8.** Texts no longer come in from phone backups.

- Your words: "That system should have been removed altogether."
- Coordinator's records, items A5.51 (built, 2026-11-20): "kept as they are, as a fallback for plain texts." (A5.51)
  - Difference: keeps phone backups as a source of texts
- Coordinator's records, items A27.18 (built, 2026-11-17): "because that upload function interferes with Claude's use of those files." (A27.18)
  - Difference: Still documents setting up phone backups for texts, which Kevin wanted removed
- Coordinator's records, items A23.5, A23.30, A23.37, A26.2, A26.7, A26.10, A26.23, A26.36 (built (A23.5, A23.30, A26.2, A26.7, A26.10, A26.23, A26.36, 2026-11-22 to 2026-11-25); planned (A23.37, 2026-11-21)): "erase the data, go back about 3 months, read forward making cards, close them where the record shows they got done" (A23.30)
  - Difference: The rebuild also pulled texts from phone backups, a source Kevin said should be gone.
- Coordinator's records, items A26.18 (built, 2026-11-22): "Your phone's full backup from November 3 plus the hourly backups should cover September onward." (A26.18)
  - Difference: Reads texts from phone backups, which Kevin said should be removed altogether.
- Coordinator's records, items A16.95 (built, 2026-11-16): "But it should guide to use ready built as much as possible." (A16.95)
  - Difference: Offers reading texts from phone backups, which Kevin wants removed altogether.
- Other coordinator records match this requirement: items A5.47, A5.75 (see Appendix).

[48] **48. Spec 11.1.** The page has its own calendar viewer fed by the connected calendars, with a New event button and no click-an-empty-slot entry.

- Your words: "I don't want this function. the new event button is enough"
- Coordinator's records, items A6.3, A6.30 (dropped (A6.3, 2026-11-22); built (A6.30, 2026-11-22)): "queued removing the empty-slot press, as you asked." (A6.30)
  - Difference: An earlier record says an empty-slot press opens the form; later records say it was removed
  - The records disagree with each other: An earlier record has the empty-slot press opening the form; later ones say it was removed
- Other coordinator records match this requirement: items A6.2, A6.5, A6.6, A6.9, A6.11, A6.16, A6.20, A6.25, A6.28 (see Appendix).

[49] **49. Spec 11.4.** The calendar header has no settings link.

- Your words: "Remove the settings hyperlink from the calendar. From the calendar header."
- Coordinator's records, items A15.10, A15.45 (built, 2026-11-23): "A Calendar part in Settings holds Calendars on Today (moved from Inbox > Sources)" (A15.10)
  - Difference: Puts a Settings link on the calendar, which Kevin asked to remove from its header
- Other coordinator records match this requirement: items A6.32 (see Appendix).

[50] **50. Spec 12.1.** The page has a Contacts section that tracks every contact.

- Your words: "We need a contacts section and tracker."
- Coordinator's records, items A7.3, A7.28, A7.34 (planned (A7.3, A7.28, 2026-11-25); built (A7.34, 2026-11-25)): "in Settings, next to what the assistant has learned about you" (A7.34)
  - Difference: Puts Contacts inside Settings rather than as its own section on the page
- Other coordinator records match this requirement: items A7.1, A7.2, A7.4, A7.6, A7.7, A7.10, A7.15, A7.22, A7.25, A7.26, A7.27, A7.33, A16.23, A16.113, A16.114 (see Appendix).

[51] **51. Spec 13.1.** A voice builder reads the user's own writing, learns his phrases, greetings and sign-offs, uses Kevin's humanize-text skill, and is run on demand (not weekly) to produce a voice file.

- Your words: "I just want to be able to run it and then have a voice file."
- Coordinator's records, items A10.2, A10.62, A10.85, A10.89, A10.95, A10.98, A10.102, A10.109, A10.124, A10.144 (planned (A10.2, A10.124, A10.144, 2026-11-19 to 2026-11-25); unclear (A10.62, 2026-11-25); built (A10.85, A10.89, A10.95, A10.98, A10.102, A10.109, 2026-11-20)): "Learns the owner's voice from their sent emails, texts and Slack: greetings, sign-offs, typical phrases, formality, and what they never say." (A10.85)
  - Difference: A conflict note shows the records disagree on whether the voice is learned only when asked or keeps learning
  - The records disagree with each other: One record says it keeps learning from edits; a conflict note says another record has it learn only when asked
- Coordinator's records, items A10.101, A10.113, A10.130 (built, 2026-11-20): "The voice builder is being changed so it runs only when you start it" (A10.130)
  - Difference: Records disagree; one has a pass learn the voice by itself daily instead of only on demand
  - The records disagree with each other: Two records say it learns only when started; another says a pass learns the voice by itself at most once a day
- Coordinator's records, items A10.86, A10.125 (built (A10.86, 2026-11-20); planned (A10.125, 2026-11-19)): "You can see and correct it on the page, and it refreshes as you keep writing." (A10.125)
  - Difference: Says the profile refreshes over time on its own instead of only when run
- Coordinator's records, items B1.4, B1.13 (planned, 2026-11-24 to 2026-11-25): "the voice study, drafts, and scoring drafts by your edits." (B1.4)
  - Difference: Leaves open whether voice learning runs on its own, while Kevin wants it run only on demand
- Other coordinator records match this requirement: items A10.81, A10.87, A10.94, A10.96, A10.100, A10.103, A10.104, A10.112, A10.114, A10.126, A10.129, A10.131, A10.132, A10.133 (see Appendix).

[52] **52. Spec 14.3.** The title and search bar stay at the top while scrolling, with visible section headers stacking tightly beneath; blank space at the bottom lets the page scroll far enough for that; left and right columns stack together.

- Your words: "Remove the how your page works link from the bottom."
- Coordinator's records, items A27.5 (built): "The owner's manual is on the page itself" (A27.5)
  - Difference: Keeps the How your page works link Kevin asked to remove
- Coordinator's records, items A11.45, A11.96 (built (A11.45, 2026-11-20); planned (A11.96, 2026-11-20)): "Each column stacks its own headings, so the empty band above your open section on the left goes away." (A11.96)
  - Difference: One record has each column stack its own headings, which Kevin took back
  - The records disagree with each other: One record stacks the columns together in one band, the other stacks each column on its own
- Coordinator's records, items A11.49 (built): "with when accounts were last read, or a pointer to Errors. A link, How your page works, opens the manual. Sign out is at" (A11.49)
  - Difference: Keeps a How your page works link at the bottom of the page, which Kevin asked to remove
- Other coordinator records match this requirement: items A11.43, A11.44, A11.59, A11.63, A11.95, A11.110 (see Appendix).

[53] **53. Spec 14.4.** Header line: no "continue your email" button, Settings just left of the date, the date shows the time, and no "things need you" bar.

- Your words: "Remove the ## things need you bar, it redundant."
- Coordinator's records, items A3.101 (built, 2026-11-16): "With open cards that need him, `top.line` says how many and names the first one in true order" (A3.101)
  - Difference: Keeps a line counting what needs the owner, which Kevin asked to remove.
- Other coordinator records match this requirement: items A11.93 (see Appendix).

[54] **54. Spec 14.6.** A section can be set to show only when it has something in it (the Errors section works this way).

- Your words: "3. the section should disapear."
- Coordinator's records, items A15.27, A15.91 (built, 2026-11-20): "an empty section disappears and comes back when something arrives (Errors ticked by default)" (A15.27)
  - Difference: A conflict note says an early record kept the empty section closed instead of making it disappear
- Other coordinator records match this requirement: items A11.25, A25.23 (see Appendix).

[55] **55. Spec 15.2.** At the top of Settings, on the heading line: Save (saves and returns to the page), Back, and Assistant Manual; "Add to your phone's home screen" is under Tools; Settings shows the version number in its header.

- Your words: "add another button to replace the link for how your page works and call it Assistant Manual"
- Coordinator's records, items A27.5 (built): "The owner's manual is on the page itself" (A27.5)
  - Difference: Keeps a How your page works link instead of an Assistant Manual button
- Coordinator's records, items A15.30, A15.32, A15.94, A15.117 (built, 2026-11-20): "Save, Back and Assistant Manual sit side by side on the Settings line, and no part has its own Save." (A15.117)
  - Difference: One record still calls the second button Discard, which Kevin renamed Back
  - The records disagree with each other: One record names the button Discard, the others Back
- Coordinator's records, items A15.70 (built): "a sticky Settings bar, with Back on the left and Save (still the main button) on the right, set apart from each other." (A15.70)
  - Difference: Back and Save are set apart at opposite ends instead of side by side with the manual
- Other coordinator records match this requirement: items A11.107, A15.20, A15.31, A15.63, A15.97, A27.8, A27.10 (see Appendix).

[56] **56. Spec 15.7.** Tools in Settings start most of the plugin's skills, each with a description; ones that must run in Claude show a pop-up with the command to copy.

- Your words: "it brings up a pop-up that you can copy the command from and paste it into Claude."
- Coordinator's records, items A15.25, A15.60 (built, 2026-11-19): "A step only the desktop can do says so with a direct link." (A15.25)
  - Difference: Gives a link to where the step is finished instead of a pop-up with the command to copy
- Coordinator's records, items A21.54, A21.58 (unclear (A21.54, 2026-11-17); built (A21.58, 2026-11-16)): "Later changes go through skills started from the Settings page; the setup window is retired." (A21.58)
  - Difference: Records disagree on whether the Change this buttons in Settings exist yet
  - The records disagree with each other: A21.54 describes Change this buttons that another record says do not exist yet
- Other coordinator records match this requirement: items A10.128, A15.11, A15.23, A15.24, A15.36, A15.42, A15.54, A15.59, A15.68, A15.79, A15.85, A15.86, A15.104, A19.25, A19.27, A19.39, A19.41, A19.187, A21.36, A21.55 (see Appendix).

[57] **57. Spec 15.8.** A change history in Settings replaces the old "changes to your assistant" section.

- Your words: "I agree, let's make it a change history in the settings."
- Coordinator's records, items A21.21 (built): "What the page shows about changes to the program: the feed document" (A21.21)
  - Difference: Puts the list of changes on the page itself rather than only as a history in Settings.
- Coordinator's records, items A21.53 (built, 2026-11-17): "New in the package: `/assistant:change` choices 6 and 7, `/assistant:undo`" (A21.53)
  - Difference: Records keep a changes section on the page, while Kevin wants a change history in Settings instead
- Other coordinator records match this requirement: items A11.50, A15.109, A20.4, A20.7, A21.6, A21.62 (see Appendix).

[58] **58. Spec 16.1.** Looks are whole-page styles modeled on well-loved interfaces, more than recolorings, and their names say where they came from.

- Your words: "The names of the looks need to allude to where they came from."
- Coordinator's records, items A11.16, A11.17 (built, 2026-11-25): "The names of the looks need to allude to where they came from." (A11.17)
  - Difference: One record gives the looks plain names with no hint of their source, against Kevin's later words
  - The records disagree with each other: One record says plain names, not the source's names; the later one says names allude to the source
- Other coordinator records match this requirement: items A11.1, A11.2, A11.3, A11.4, A11.20, A11.21, A11.114 (see Appendix).

[59] **59. Spec 16.2.** The default look is Glass Dark; Expressive Light and Workshop stay; the other original looks are removed (Broadsheet: see open question 6).

- Your words: "I want to remove all but one of the original designs"
- Coordinator's records, items A11.8, A11.18, A11.29, A11.58, A11.105, A11.113 (planned (A11.8, A11.18, 2026-11-25); built (A11.29, A11.58, A11.105, A11.113, 2026-11-25 to 2026-11-26)): "Build all styles. these will sit along side the ones we have now until I've tested them." (A11.8)
  - Difference: Keeps all six original looks beside the new ones, while Kevin later said to remove the other originals
- Coordinator's records, items A11.9, A11.30, A11.57, A11.106, A11.117 (planned (A11.9, A11.117, 2026-11-25); built (A11.30, A11.106, 2026-11-25 to 2026-11-26); dropped (A11.57)): "Workshop and Broadsheet stay; Studio, Midnight, Poster and Chartroom are removed." (A11.9)
  - Difference: Keeps Broadsheet, which Kevin's list leaves open, and one record says Broadsheet was removed; one record marks the removal dropped
  - The records disagree with each other: One record marks the removal dropped while others call it built, and a conflict note says Broadsheet was removed
- Coordinator's records, items A11.39, A11.40, A11.62, A11.88 (built (A11.39, A11.40, A11.88, 2026-11-18); dropped (A11.62)): "Each works light and dark and on a phone; every color pair passes the readability standard." (A11.40)
  - Difference: An older set of looks with Classic as default, since replaced; Kevin now wants Glass dark as default
  - The records disagree with each other: Some records call the six styles built, one marks them dropped as later records replaced them
- Coordinator's records, items A11.99 (built, 2026-11-21): "Your page will open in Studio until you pick another in Settings, under How the page looks, then Style." (A11.99)
  - Difference: Makes Studio the default, which Kevin later replaced with Glass dark
- Other coordinator records match this requirement: items A11.10, A11.118 (see Appendix).

[60] **60. Spec 17.1.** Every 15 minutes all new messages are pulled into the assistant's store, and what has been read shows on the page right away.

- Your words: "This is supposed to be checking all my emails and updating this every 15 minutes."
- Coordinator's records, items A14.67 (built, 2026-11-21): "the 15-minute check is off, as you asked;" (A14.67)
  - Difference: records the regular check as switched off for now
- Other coordinator records match this requirement: items A4.24, A4.48, A13.3, A14.3, A14.15, A14.16, A14.32, A14.38, A14.45, A14.47, A14.48, A14.50, A14.51, A14.60, A14.77, A14.79, A14.80, A16.67 (see Appendix).

[61] **61. Spec 17.4.** A full rebuild imports every channel one day at a time from a start date, judges each day, closes what was done, then moves to the next day.

- Your words: "open messages and emails and all channels one day at a time"
- Coordinator's records, items A14.20 (built, 2026-11-16): "A conversation already read is skipped, so a second run with the same date adds nothing and uses no Claude." (A14.20)
  - Difference: reads back old conversations from a start date in one run rather than importing, judging and closing one day at a time
- Other coordinator records match this requirement: items A23.5, A23.30, A23.37, A26.2, A26.7, A26.10, A26.15, A26.23, A26.36 (see Appendix).

[62] **62. Spec 17.5.** Updating the program first stops the automatic gathering so they can't collide.

- Your words: "every time you update the program, you first lock the database so that the automatic update doesn't happen"
- Coordinator's records, items A14.57 (built, 2026-11-19): "An install started during an email check now waits up to 10 minutes for it to finish instead of failing." (A14.57)
  - Difference: waits for a check already running but does not say the next check is held off during the update
- Other coordinator records match this requirement: items A17.5, A17.6, A17.47, A17.51, A17.87, A17.107, A17.109, A17.111, A17.166, A17.174, A23.36, B4.16, B4.49, B6.42 (see Appendix).

[63] **63. Spec 18.1.** Onboarding is a series of cards that walk a new user through setup.

- Your words: "Lets make onboarding be a series of cards that walk the user through the settup process."
- Coordinator's records, items A27.14 (built, 2026-11-22): "For Claude: walk these steps one at a time." (A27.14)
  - Difference: Setup is walked by Claude in a session instead of by a series of setup cards
- Coordinator's records, items A16.82, A16.83, A16.92, A16.93, A16.96 (built, 2026-11-16): "It will interview the user and tune the system to the users needs." (A16.92)
  - Difference: Setup is an interview in the Claude app rather than a series of cards on the page.
- Other coordinator records match this requirement: items A16.1, A16.11, A16.12, A16.32, A16.71, A16.81, A16.106, B1.7 (see Appendix).

[64] **64. Spec 18.3.** The back-catalog step asks how far back to go (default one year), includes building the voice guide, and explains that it is fast, fairly cheap, and only catalogs old messages so new ones can be given context later.

- Your words: "the tool should ask how far to go back"
- Coordinator's records, items A16.3, A16.9, A16.19, A16.20, A16.25, A16.31, A16.107 (planned (A16.3, A16.9, A16.19, A16.20, A16.31, 2026-11-25); unclear (A16.25, 2026-11-25); built (A16.107, 2026-11-25)): "So I'd ask new users for a year, and default to it." (A16.107)
  - Difference: One record says it studies a fixed last 3 months before suggesting, while the others ask how far back with a one-year default as Kevin said.
  - The records disagree with each other: One record says it studies the last 3 months; the rest say setup asks, defaulting to one year.
- Coordinator's records, items A16.48, A16.86, A16.94 (built, 2026-11-16): "Before anything is read, Claude tells you the cost: roughly how many messages, how many times Claude has to think, and how long." (A16.86)
  - Difference: Processes past messages into cards and history, where Kevin wants the past only cataloged so new messages can get context.
- Other coordinator records match this requirement: items A7.21, A10.4, A13.86, A16.6, A16.7, A16.14, A16.28, A16.29, A16.30, A16.35, A16.45, A16.46, A16.108, B1.7 (see Appendix).

[65] **65. Spec 18.4.** No new messages are pulled until the back catalog is built, so the first new ones are judged with context.

- Your words: "I want to hold off on pulling in fresh emails, fresh anything, until the back catalog is built"
- Coordinator's records, items A16.4, A16.26 (planned (A16.4, 2026-11-25); unclear (A16.26, 2026-11-25)): "while you start using the page right away" (A16.26)
  - Difference: Has the user working on the page while the past is still being studied, where Kevin holds back all new messages until the back catalog is built.
- Other coordinator records match this requirement: items A16.16, A16.38, A16.47, A16.72, A16.109 (see Appendix).

[66] **66. Spec 18.5.** Onboarding includes an open-ended interview, not yes/no or multiple choice; it can start from a list of things to learn but does not end before the user is done.

- Your words: "Because these are not yes or no or even multiple choice questions."
- Coordinator's records, items A16.55, A16.75 (built): "Talk to the person in plain words, one thing at a time, numbered choices." (A16.75)
  - Difference: Asks with numbered choices, where Kevin wants open questions with free, custom answers.
- Coordinator's records, items A16.82, A16.83, A16.92, A16.93, A16.96 (built, 2026-11-16): "It will interview the user and tune the system to the users needs." (A16.92)
  - Difference: The interview uses numbered choices and a fixed order, where Kevin wants open questions with free answers.
- Other coordinator records match this requirement: items A16.15, A16.36, A16.111, B1.14 (see Appendix).

[67] **67. Spec 18.6.** From day one, every new item from any connected channel becomes a card.

- Your words: "Any channels of information become cards from day one."
- Coordinator's records, items A13.72 (built, 2026-11-17): "Mail judged noise, junk, phishing or evidence never becomes a card." (A13.72)
  - Difference: Records keep mail judged noise, junk, phishing or proof from ever becoming a card
- Other coordinator records match this requirement: items A16.21, A16.101, A20.5, A20.43, A20.157, A20.158 (see Appendix).

[68] **68. Spec 18.7.** A fresh install works for someone who has never used the program; Kevin's own rules can be put aside and brought back.

- Your words: "I just want to put them aside so I can see how the process works."
- Coordinator's records, items A9.17, A9.31, A9.89, A9.91 (built, 2026-11-25): "Only his press of Start fresh in Settings, Rule book, then Yes" (A9.31)
  - Difference: Records disagree whether Start fresh deletes the owner's rules or sets them aside to bring back later
  - The records disagree with each other: Some records say Start fresh deletes the owner's rules; others say it sets them aside, not thrown out
- Coordinator's records, items A15.5, A15.55 (built, 2026-11-24): "It runs on a home only when its owner presses Start fresh in Settings (never run on Kevin's home)." (A15.5)
  - Difference: Start fresh deletes personal rules rather than putting them aside to be brought back
  - The records disagree with each other: One record moves the rules to To Delete; the later one deletes them outright with no To Delete folder
- Coordinator's records, items A12.106 (planned, 2026-11-25): "start fresh, current personal rules don't carry over" (A12.106)
  - Difference: Says current personal rules do not carry over, without saying they are kept aside and can be brought back.
- Other coordinator records match this requirement: items A15.7, A16.22, A16.44, B1.9, B1.49 (see Appendix).

[69] **69. Spec 19.1.** Everything the assistant needs lives in the Assistant folder; deleting the old projects folder does not affect it.

- Your words: "if I were to delete that project folder, nothing bad would happen to the assistant."
- Coordinator's records, items A17.138 (built, 2026-11-17): "the old program is saved first in" (A17.138)
  - Difference: Leaves the assistant inside the old folder, while another record says the owner chose a new folder so the old one can go.
- Other coordinator records match this requirement: items A17.115, A17.129, A17.139, A17.150, A21.79, A23.34, A23.35, B1.1, B9.3, B9.13 (see Appendix).

[70] **70. Spec 19.2.** No more small always-on programs are added; the goal is one server running everything.

- Your words: "I don't want to keep adding more."
- Coordinator's records, items A14.52 (built, 2026-11-17): "after the person says yes to a plain sentence naming both jobs and what they do." (A14.52)
  - Difference: sets up two separate background jobs rather than one program
- Other coordinator records match this requirement: items A2.37, A5.32, A12.52, A12.114, A12.142, A14.41, A14.46, A16.67, A17.38, A24.1, A24.3, A24.5, A24.17, A24.21, A24.22, A24.25, A24.26, A24.27, A24.28, A24.29, A25.1 (see Appendix).

[71] **71. Spec 19.3.** The version number goes up only on a push to GitHub; the project is in 0.x and becomes 1.0 at the final push; the phone version is 2.0.

- Your words: "when we're ready for the final push, it will become 1.0. We're in 0.x right now."
- Coordinator's records, items B4.1, B4.3, B4.8, B4.71 (planned (B4.1, B4.3, B4.8, 2026-11-25); built (B4.71, 2026-11-25)): "Updates stay 0.x (0.1.13, 0.1.14 ...) until everything he wants is done" (B4.1)
  - Difference: One record shows a same-day plan to make the next update 1.0 and count up to 2.0, later corrected.
  - The records disagree with each other: B4.71's record notes that earlier the same day the plan was 1.0 next then 1.1 up to 2.0, before it was corrected.
- Other coordinator records match this requirement: items A17.12, A17.36, A17.68, A17.152, B4.5, B4.21, B4.34, B4.36, B4.40, B4.64 (see Appendix).

[72] **72. Spec 19.4.** The update offers to bring other sessions using the plugin up to date.

- Your words: "offer to push the appropriate updates to each"
- Coordinator's records, items A19.200 (built, 2026-11-17): "The roadmap's update stays per project" (A19.200)
  - Difference: Lists projects that are behind and leaves each update to its own project, and the records disagree on whether each gets a card; Kevin wants the update to offer to update each.
- Other coordinator records match this requirement: items A17.14, A17.15, A17.16, A17.32, A17.33, A17.70, A17.84, A17.93, A17.158, A17.159, A17.179 (see Appendix).

[73] **73. Spec 19.5.** Things the program deletes are deleted outright; the plugin has no "To Delete" holding folder.

- Your words: "My point is the deleted stuf should just get deleted."
- Coordinator's records, items A5.33, A5.93 (built, 2026-11-22): "over once (a later status of the same text and a send under way are" (A5.33)
  - Difference: removed duplicates are saved to a holding folder instead of deleted outright
- Coordinator's records, items A9.43, A9.90 (dropped (A9.43); built (A9.90, 2026-11-25)): "To Delete is gone from the assistant entirely, so deleted things are just deleted" (A9.90)
  - Difference: An earlier record moved rules to a To Delete folder on Start fresh; it was dropped and deletion is now outright
- Coordinator's records, items A15.5, A15.55 (built, 2026-11-24): "It runs on a home only when its owner presses Start fresh in Settings (never run on Kevin's home)." (A15.5)
  - Difference: One record moves personal rules to a To Delete folder, which Kevin said the plugin must not have
  - The records disagree with each other: One record moves the rules to To Delete; the later one deletes them outright with no To Delete folder
- Coordinator's records, items A23.9, A23.25, A23.40, A26.16, A26.30 (built, 2026-11-22 to 2026-11-23): "There is no To Delete anywhere now: what you delete is deleted." (A23.25)
  - Difference: Several records set erased or removed data aside in a To Delete folder instead of deleting it outright.
  - The records disagree with each other: Older records move data to To Delete; a later record says there is no To Delete anywhere.
- Coordinator's records, items A17.67, A17.110, A17.136, A17.144, A17.154, A17.156, A17.167 (built, 2026-11-17 to 2026-11-21): "From now on, an update only checks that the new files load and that your page answers." (A17.167)
  - Difference: One record has the update move the old program into a dated To Delete folder instead of deleting it.
  - The records disagree with each other: Some records say an update runs one check pass after writing; later ones say it runs none and a pass is started by hand.
- Coordinator's records, items A17.108, A17.114, A17.140 (built (A17.108, A17.114, 2026-11-17 to 2026-11-18); planned (A17.140, 2026-11-25)): "Keep one undo copy only for your own data (your rules, lists, cards and mail store)." (A17.140)
  - Difference: Records disagree, and the older rule and the plan still keep To Delete folders in the program instead of deleting outright.
  - The records disagree with each other: One record deletes old copies outright; another says nothing is ever deleted and files go to a To Delete folder.
- Coordinator's records, items A19.23, A19.86, A19.156 (built, 2026-11-26): "every roadmap reminder and hold stops there, and the page stays at its link as a record" (A19.23)
  - Difference: The records disagree on whether switching off deletes the roadmap records, saves them inside the project, or moves them to a To Delete folder.
- Coordinator's records, items A19.24, A19.188, A19.230 (built, 2026-11-19 to 2026-11-26): "turns the roadmap off for a project: its settings move to a dated To Delete folder" (A19.24)
  - Difference: Moves things to a To Delete folder, which Kevin said is his own habit and not part of the product; he wants deleted things deleted.
- Coordinator's records, items A19.52, A19.60 (built): "Turn a project's roadmap off; its records are deleted and the page stays" (A19.60)
  - Difference: Another record says the records are first saved inside the project before deletion, so the records disagree.
- Coordinator's records, items A19.85, A19.87, A19.180, A19.252 (built, 2026-11-25): "Switching off will first save the project's roadmap records inside the project, and switching back on restores them" (A19.252)
  - Difference: Keeps a saved copy of the records when switching off instead of deleting them outright.
- Coordinator's records, items A19.181, A19.194, A19.196 (built, 2026-11-17 to 2026-11-25): "Claude can now switch the roadmap off and on, and retire a project's old roadmap locks, when you say yes." (A19.181)
  - Difference: The earlier closing step moves roadmap files to To Delete before removal.
  - The records disagree with each other: An earlier record says no command in Claude closes a roadmap, while later ones let Claude switch it off on the owner's yes.
- Coordinator's records, items B1.93, B9.17 (built, 2026-11-18 to 2026-11-21): "The two blank files get moved to your To Delete folder under today's date, not deleted" (B1.93)
  - Difference: Moves files to a To Delete folder, while Kevin now wants deleted things deleted outright; records also disagree about a helper moving files an update still used
- Coordinator's records, items B3.49 (built, 2026-11-21): "the move to To Delete refuses any file that something else still calls." (B3.49)
  - Difference: It still moves things to a To Delete holding folder instead of deleting outright.
- Coordinator's records, items B10.22 (built, 2026-11-25): "Never delete; move to To Delete only." (B10.22)
  - Difference: Moves things to a To Delete folder, while Kevin's current word is that deleted things are deleted outright; the records also disagree.
- Other coordinator records match this requirement: items A17.38, A20.16, A20.50, A20.162, B3.19 (see Appendix).

[74] **74. Spec 19.6.** The plugin's guardrails stop only really harmful actions; mentioning a word must not trip them, and the roadmap has very few blocks.

- Your words: "The roadmap IS NOT A CRITCAL FUNCTION. it should have very few blocks."
- Coordinator's records, items A20.18, A20.22, A20.63, A20.80, A20.82, A20.106, A20.128, A20.140, A20.141, A20.154 (built (A20.18, A20.22, A20.63, A20.80, A20.82, A20.128, A20.141, 2026-11-17 to 2026-11-25); planned (A20.106, A20.140, A20.154, 2026-11-23 to 2026-11-25)): "Refuse only a write whose target is one of the 5 safety files, the roadmap ids or a settings file." (A20.140)
  - Difference: The older record locked the whole plugin folder, which the newer records narrow; the records disagree
  - The records disagree with each other: A20.128 (11/17) locks the plugin's whole folder and working copy; later items narrow the lock to the safety files only
- Coordinator's records, items A20.119 (built, 2026-11-17): "Terminal commands are seen as text only: a check can refuse a command by what it names" (A20.119)
  - Difference: Records judge a command by the words it names, while Kevin says merely mentioning a word must not trip a guard
- Coordinator's records, items A20.115 (built, 2026-11-17): "A writing command that names those folders is refused unless a change is under a go." (A20.115)
  - Difference: Records refuse a command because of the folder names it contains, while Kevin says merely mentioning a word must not trip a guard
- Coordinator's records, items A20.15, A20.60, A20.68, A20.77, A20.78, A20.90, A20.117, A20.137 (built (A20.15, A20.60, A20.68, A20.77, A20.78, A20.90, A20.117, 2026-11-17 to 2026-11-25); planned (A20.137, 2026-11-25)): "A missing guardrails file now blocks only sends, nothing else." (A20.90)
  - Difference: Older records refuse every write, send or command when the guardrails are missing; newer ones refuse only sends; the records disagree
  - The records disagree with each other: A20.117 and A20.78 (11/17) fail closed on every write or command; the 11/25 items refuse only sends
- Coordinator's records, items B3.31, B3.50, B3.70, B3.72 (built, 2026-11-17 to 2026-11-24): "Only you can change the guard, so that step has to be yours." (B3.70)
  - Difference: It hands guard steps to Kevin to run by hand, while he wants projects to run without him intervening.
- Coordinator's records, items B3.40, B3.82 (built, 2026-11-19): "The end-of-turn check also catches a roadmap write that" (B3.82)
  - Difference: It adds a stop on roadmap work, while Kevin wants the roadmap to have very few blocks.
- Coordinator's records, items B3.12, B3.45 (built, 2026-11-20): "Any check left for you has to say why only you can do it" (B3.45)
  - Difference: It keeps refusals coded into the roadmap, while Kevin wants the roadmap to have very few blocks.
- Other coordinator records match this requirement: items A19.137, A19.143, A19.219, A20.1, A20.8, A20.9, A20.10, A20.11, A20.12, A20.13, A20.14, A20.17, A20.19, A20.20, A20.21, A20.23, A20.24, A20.57, A20.62, A20.74, A20.81, A20.85, A20.87, A20.88, A20.89, A20.93, A20.112, A20.116, A20.131, A20.132, A20.134, A20.135, A20.136, A20.145, A20.160, A20.161, A20.168, B1.1, B3.9, B3.14, B3.23, B3.24, B3.25, B3.26, B3.27, B3.33, B3.78, B6.36, B8.11 (see Appendix).

[75] **75. Spec 20.1.** A phone layout is not part of this release; it comes with version 2.0.

- Your words: "Cancel the phone for now. Version 2.0 will include the phone."
- Coordinator's records, items A18.3, A18.5, A18.11 (planned, 2026-11-21 to 2026-11-25): "A full design session for the page on a phone: the jump bar, Texts, Slack, mail and cards made to fit" (A18.5)
  - Difference: Keeps a phone design session on the plan as current work rather than set aside for version 2.0
- Coordinator's records, items B2.4 (planned, 2026-11-25): "Each look, in light and dark, at desktop and phone width" (B2.4)
  - Difference: It checks phone width, but the phone layout is out of this release.
- Other coordinator records match this requirement: items A11.14, A18.1, A18.2, A18.4, A18.6, A18.12, A18.13 (see Appendix).

[76] **76. Spec 21.1.** The roadmap stays part of the plugin as a standalone, general-purpose planning tool with its own settings that happens to connect to the assistant.

- Your words: "I don't want to remove roadmap from the plugin. That's still part of the plugin."
- Coordinator's records, items A19.36 (built, 2026-11-15): "The assistant holds none of its files" (A19.36)
  - Difference: Says the roadmap is a separate plugin outside the assistant; Kevin wants it kept as part of the plugin.
- Other coordinator records match this requirement: items A17.57, A19.3, A19.6, A19.135, A19.161, A19.162, A19.163, A19.174, A19.176, A19.184, A19.201, A19.241, A28.27 (see Appendix).

[77] **77. Spec 21.2.** The roadmap is a log: each decision and each change in the project is added as it happens.

- Your words: "The point of the roadmap is a log of what's going on in the project."
- Coordinator's records, items B8.49 (built, 2026-11-18): "Adding a row is your decision, not mine." (B8.49)
  - Difference: Rows are added only when the owner decides, while Kevin now wants every decision and change logged as it happens
- Other coordinator records match this requirement: items A19.106, A19.107, A19.139, A19.142, A19.182, A19.220, A19.249, B3.10, B3.37, B8.3, B8.4, B8.12, B8.13 (see Appendix).

[78] **78. Spec 21.3.** A running roadmap keeps a short renumbered list with a Being fixed group and a history that opens at the bottom.

- Your words: "Let's make it a being fixed group."
- Coordinator's records, items A11.56 (built, 2026-11-16): "The page has three sections, Planning, Working and Done, in place of one long list." (A11.56)
  - Difference: Splits the roadmap into Planning, Working and Done rather than a Being fixed group with a history at the bottom
- Other coordinator records match this requirement: items A19.1, A19.29, A19.30, A19.31, A19.32, A19.98, A19.157, A19.192, A19.233, A19.234 (see Appendix).

[79] **79. Spec 21.4.** Comments and setting changes made on the roadmap reach the session, just as Works / Doesn't work marks do.

- Your words: "my comments do not and setting changes do not?"
- Coordinator's records, items A20.153 (planned, 2026-11-23): "To change it, it gives you the exact command with a Copy button, and you run it yourself." (A20.153)
  - Difference: Records make a roadmap setting change a command Kevin runs himself rather than a setting change that reaches the session
- Other coordinator records match this requirement: items A19.2, A19.4, A19.14, A19.17, A19.33, A19.54, A19.119, A19.121, A19.134, A19.165, A19.168, A19.172, A19.203, A19.204, A19.238, A19.239, A19.244, A19.248 (see Appendix).

[80] **80. Spec 21.5.** Every roadmap includes the questions file, shown as a copy of it (not as cards); the questions file also works on its own and questions can be answered in chat or on the roadmap.

- Your words: "every roadmap gets the questions.md file included in it"
- Coordinator's records, items A19.22, A19.55, A19.56, A19.68, A19.215, A19.229 (built, 2026-11-19 to 2026-11-26): "A question raised in conversation with the person goes in this session's questions file and is answered in chat." (A19.68)
  - Difference: One record says the questions file and the roadmap need not stay in step, while Kevin wants every roadmap to include the questions file as a copy kept up to date.
- Coordinator's records, items A19.11, A19.183 (built, 2026-11-26): "a session's questions file shows on the roadmap, tagged From chat; answer there or in the chat." (A19.183)
  - Difference: Shows chat questions as tagged items on the roadmap, while Kevin wants that part to be only a copy of the questions file, not cards.
- Coordinator's records, items B8.16 (built, 2026-11-16): "A decision with choices for Kevin goes on the roadmap as a question, not only in chat" (B8.16)
  - Difference: Puts questions on the roadmap as its own entries, while Kevin now wants that part to be only a copy of the questions file
- Coordinator's records, items B8.48 (built, 2026-11-18): "I don't track open questions outside the page's own questions, which only you create." (B8.48)
  - Difference: Leaves outside questions off the roadmap, while Kevin now wants every roadmap to include the questions file
- Other coordinator records match this requirement: items A19.48, A19.49, A19.50, A19.84, A19.179, A19.193, A19.250, B1.44, B8.1, B8.2 (see Appendix).

[81] **81. Spec 21.6.** When questions are waiting, the questions-for-you button pulses slowly red; the still-to-check button does the same.

- Your words: "Do that with the still to check section as well."
- Coordinator's records, items A19.12, A19.178, A19.251 (built, 2026-11-25 to 2026-11-26): "Questions for you pulses red and Still to check pulses amber while something waits" (A19.178)
  - Difference: Still to check pulses amber rather than red like Questions for you.

[82] **82. Spec 21.7.** The questions file is laid out like chat (numbered question, lettered answers beneath), holds only its own session's questions, and does not carry the "Open questions for the person..." line.

- Your words: "The questions in the file are only questions gerated in that session not forks."
- Coordinator's records, items A19.189, A19.205, A19.206, A19.227, A19.228 (built, 2026-11-19): "One writer: the project's main session. Helper sessions and subagents never write it." (A19.206)
  - Difference: Keeps one file per project written by the main session, while Kevin wants each session's file to hold only that session's questions.
- Other coordinator records match this requirement: items A9.59, A19.7, A19.10, A19.28, A19.43, A19.61, A19.65, A19.66, A19.70, A19.75, A19.190, A19.207, A19.231, A19.232, A19.255, B7.6 (see Appendix).

[83] **83. Spec 21.8.** Adding a roadmap or questions file from Tools asks which project and exactly which session, sends the command there, and waits for the user to approve it in that session; the roadmap is suggested for higher-level sessions.

- Your words: "there needs to be a way for the user to designate exactly which session we're talking about."
- Coordinator's records, items A22.1 (built): "They work on one of the owner's projects, not on the assistant." (A22.1)
  - Difference: Records only say the tools work on one of the owner's projects; they do not have the user pick the exact session and approve it there
- Coordinator's records, items A19.26, A19.40 (built, 2026-11-20): "Add asks which project, finds its main session and sends it the setup, which waits for your yes in that session" (A19.26)
  - Difference: Picks the project's main session itself instead of letting the owner name exactly which session, and gives no advice on which session suits a roadmap.
- Coordinator's records, items A19.42 (built): "only its own files are deleted, the other projects are untouched, and no message is sent. Without the" (A19.42)
  - Difference: Remove works straight from the page with no session chosen, while Kevin wants all four commands to name exactly which session.
- Other coordinator records match this requirement: items A15.87, A15.89, A17.162, A19.25, A19.39, A19.58, A19.64, A19.105, A19.187 (see Appendix).
