# Kept procedures
Coordinator build procedures whose verdict line says "Your list supports it", copied word for word from Requirements comparison.md Section 3 (original numbers in brackets).
Kevin's ruling 2026-11-25 followed: all coordinator build procedures are dropped except those Kevin's list supports.

[633] **633.** Made-up test cards can be put on the page and taken off again, and a press on them changes only that card and sends nothing
- Items: A3.82, A3.172, A3.241, A15.57, A15.58. Status: built, 2026-11-19.
- Excerpt: "Made-up cards to try the page with, kept apart from the owner's real ones." (A3.82)
- Your list supports it (spec 8.2): Kevin wants test cards put on the site to confirm changes work.
- Your list supports it (spec 8.2): Kevin wants check cards put on the site to confirm changes work

[637] **637.** The owner's own rules stay out of the core unless he picks them one by one in a review before a push
- Items: A9.51, A9.52, B1.87, B4.47. Status: built, 2026-11-18 to 2026-11-25.
- Excerpt: "a rule he picks is rewritten in general terms (no names or personal data) before going into the repo" (A9.52)
- Your list supports it (spec 6.4): Kevin says core rules are mostly the rules he makes about how the system works
- Your list supports it (spec 6.4): Kevin separates core rules from personal ones
- Your list supports it (spec 6.4): Kevin says core rules are mostly his rules about how the system works.
- Also tied to your requirements: spec 6.4 (matches), spec 6.4 (matches)

[638] **638.** A question put to Kevin in discussion is written into the project's questions file first, numbered from 1 oldest first, renumbered at every edit, with choices lettered
- Items: A9.59. Status: built, 2026-11-19.
- Excerpt: "Kevin has ruled choices are lettered and agreed the line should change." (A9.59)
- Your list supports it (spec 21.7): Kevin asked for the questions file to look like chat, with numbered questions and lettered answers
- Also tied to your requirements: spec 21.7 (matches)

[640] **640.** Report of what was not yet checked on the new looks: phone width, mail, texts, calendar and settings screens and two look fixes
- Items: A11.14. Status: unclear, 2026-11-25.
- Excerpt: "Not checked: phone width (the phone page is for version 2.0; see Phone design.md)" (A11.14)
- Your list supports it (spec 20.1): Leaving phone width to version 2.0 follows Kevin's call to put the phone off to 2.0
- Also tied to your requirements: spec 20.1 (matches)

[645] **645.** Build the loop in the order of the four steps, since each needs the one before
- Items: A12.128. Status: planned, 2026-11-25.
- Excerpt: "follows his steps, because each step needs the one before it" (A12.128)
- Your list supports it (spec 7.1): Kevin wants the loop built the way the video lays it out.

[647] **647.** A build or test fails if any setting or tool lacks its explanation
- Items: A15.111, B2.11. Status: planned (A15.111, 2026-11-22); built (B2.11, 2026-11-22).
- Excerpt: "Any new setting will have to come with one, or the build fails." (A15.111)
- Your list supports it (spec 15.5): Kevin wants every setting to have an information pop-up
- Your list supports it (spec 15.5): Kevin wants every setting to explain what it is for.
- Also tied to your requirements: spec 15.5 (matches)

[649] **649.** Local edits reach the running assistant without a new version number; the number goes up only for a push
- Items: A17.12, A17.36, B4.21, B4.40. Status: built, 2026-11-17 to 2026-11-18.
- Excerpt: "puts local edits into your running assistant even when the version number has not changed" (A17.12)
- Your list supports it (spec 19.3): Kevin wants the version to rise only on a push, so local builds must go in under the same number.
- Your list supports it (spec 19.3): Kevin's own words on when the version goes up.
- Also tied to your requirements: spec 19.3 (matches), spec 19.3 (matches)

[654] **654.** None of the owner's personal data, caches or logs goes into the program code or the shipped package
- Items: A17.128, B10.20, B10.33. Status: built, 2026-11-17 to 2026-11-25.
- Excerpt: "put nothing of yours, like your addresses or calendars, into the code." (B10.33)
- Your list supports it (spec 18.7): Kevin wants a fresh install to work for someone who has never used the program.
- Your list supports it (spec 18.7): A clean package is what lets a fresh install work for someone who never used the program.

[658] **658.** Projects already using the old separate roadmap plugin keep working, and the old plugin is removed from each project after showing Kevin.
- Items: A19.199. Status: built, 2026-11-17.
- Excerpt: "is uninstalled from each project where it is on (shown to Kevin first)" (A19.199)
- Your list supports it (spec 21.1): Kevin wants the roadmap kept as part of the assistant plugin, which this move carries out.

[659] **659.** The auto mode safety check is fixed by rewriting its description to cover all of ClaudeOS, not by turning it off
- Items: A20.10, A20.134. Status: built (A20.10, 2026-11-25); planned (A20.134, 2026-11-25).
- Excerpt: "rewrite the description to cover all of ClaudeOS. The CEO session makes this in your own settings." (A20.10)
- Your list supports it (spec 19.6): Stops a check that kept blocking his projects, as he asked
- Also tied to your requirements: spec 19.6 (matches)

[660] **660.** Claude is allowed to delete named files and folders inside ClaudeOS and the research drive, except git history, while whole-drive wipes stay stopped
- Items: A20.11, A20.135. Status: built (A20.11, 2026-11-25); planned (A20.135, 2026-11-25).
- Excerpt: "allow deleting inside ClaudeOS and your research drive, except git history" (A20.11)
- Your list supports it (spec 19.6): Kevin wants guards to stop only really harmful actions so work is not blocked
- Also tied to your requirements: spec 19.6 (matches)

[676] **676.** The builder's check keeps refusing network code outside the gatekeeper as a hard block.
- Items: A28.18. Status: planned, 2026-11-11.
- Excerpt: "The builder's scan keeps refusing network code anywhere else, so this stays a hard block" (A28.18)
- Your list supports it (spec 19.6): Code that could send data out unapproved is the kind of really harmful action Kevin's guardrail rule still allows blocking.

[681] **681.** Before the rebuild, the learning loop is installed, the guardrails reviewed and the plugin moved into the Assistant folder
- Items: B1.1. Status: planned, 2026-11-25.
- Excerpt: "Before any of this: RSI installed, the guardrail review, and the move of the plugin into the Assistant folder." (B1.1)
- Your list supports it (spec 19.1): Kevin wants everything the assistant needs in the Assistant folder
- Also tied to your requirements: spec 19.1 (matches), spec 19.6 (matches)

[682] **682.** First build step: a pick on every card, rule book rows for every kind of work, actions taken off the page recorded, level 1 only, AI cost measured
- Items: B1.2. Status: planned, 2026-11-25.
- Excerpt: "Level 1 only. Measure the AI cost." (B1.2)
- Your list supports it (spec 7.5): Kevin wants every area to start at level 1
- Also tied to your requirements: spec 7.5 (matches), spec 7.7 (matches)

[683] **683.** Second build step: merge the judging and card writing parts and make buttons that build themselves
- Items: B1.3. Status: planned, 2026-11-25.
- Excerpt: "merge the judge and the card writer; buttons that build themselves." (B1.3)
- Your list supports it (spec 4.2): Kevin wants buttons written for each card
- Also tied to your requirements: spec 4.2 (matches)

[684] **684.** Build step for drafts: study how the owner writes, draft replies and score drafts against his edits and sent replies
- Items: B1.4, B1.13. Status: planned, 2026-11-24 to 2026-11-25.
- Excerpt: "the voice study, drafts, and scoring drafts by your edits." (B1.4)
- Your list supports it (spec 7.9): Kevin wants the judge to learn how he writes
- Also tied to your requirements: spec 7.9 (matches), spec 13.1 (differs, see Section 1)

[685] **685.** Build step for the grader and coach across every kind of work, with a score for each shown in Settings
- Items: B1.5. Status: planned, 2026-11-25.
- Excerpt: "with a score for each in Settings." (B1.5)
- Your list supports it (spec 7.1): Kevin wants a separate grader and coach
- Also tied to your requirements: spec 7.1 (matches), spec 7.2 (matches), spec 7.3 (matches)

[686] **686.** Build step for trust levels 2 and 3 with undo and a daily summary, which needs guardrail changes the owner decides
- Items: B1.6. Status: planned, 2026-11-25.
- Excerpt: "(needs guardrail changes, so your call)." (B1.6)
- Your list supports it (spec 7.8): Kevin's accepted plan describes levels 2 and 3
- Also tied to your requirements: spec 7.8 (matches)

[687] **687.** Build step for setup cards and the study of old messages
- Items: B1.7. Status: planned, 2026-11-25.
- Excerpt: "Setup cards and the history study." (B1.7)
- Your list supports it (spec 18.1): Kevin wants onboarding as a series of cards
- Also tied to your requirements: spec 18.1 (matches), spec 18.3 (matches)

[688] **688.** First learning loop step built: signals, guardrail wording, choice and No presses, buttons that change per card, and noise cards
- Items: B1.8. Status: built, 2026-11-24.
- Excerpt: "Signals and names: guardrail wording; choice press and No press; dynamic buttons" (B1.8)
- Your list supports it (spec 4.2): Kevin wants buttons written for each card
- Also tied to your requirements: spec 4.2 (matches), spec 7.7 (matches)

[689] **689.** Second learning loop step built: rule book rows with a reason, core rules kept read-only in the program, a start-fresh step and rule review in Settings
- Items: B1.9. Status: built, 2026-11-24.
- Excerpt: "core rules moved into the program read-only; store map core vs personal" (B1.9)
- Your list supports it (spec 6.4): Kevin wants core rules shipped and personal rules kept apart
- Also tied to your requirements: spec 6.4 (matches), spec 6.5 (matches), spec 7.4 (matches), spec 18.7 (matches)

[690] **690.** Third learning loop step built: the grader re-judges past items without acting, scores each section, and runs in a queue with its own cap
- Items: B1.10. Status: built, 2026-11-24.
- Excerpt: "Grader and scores: re-judge dry run per layer; signal marking" (B1.10)
- Your list supports it (spec 7.2): Kevin's accepted plan has a grader that only reports
- Also tied to your requirements: spec 7.2 (matches)

[691] **691.** Fourth learning loop step built: the coach writes a draft beside the live version and keeps past versions and rejected drafts
- Items: B1.11. Status: built, 2026-11-24.
- Excerpt: "Coach: draft file and its guardrail" (B1.11)
- Your list supports it (spec 7.3): Kevin's accepted plan has the coach work in a draft and keep versions
- Also tied to your requirements: spec 7.3 (matches)

[692] **692.** Fifth learning loop step built: a learning level for each section in Settings, level 1 wiring, a card for rule changes, and level 3
- Items: B1.12. Status: built, 2026-11-24.
- Excerpt: "Learning levels per section in Settings; Level 1 wiring; rule change card" (B1.12)
- Your list supports it (spec 7.5): Kevin wants a trust level setting for each area
- Also tied to your requirements: spec 7.5 (matches), spec 7.8 (matches)

[693] **693.** A later step rewrites the setup interview
- Items: B1.14. Status: planned, 2026-11-24.
- Excerpt: "until the interview is rewritten in phase 7." (B1.14)
- Your list supports it (spec 18.5): Kevin wants an open-ended onboarding interview
- Also tied to your requirements: spec 18.5 (matches), spec 6.4 (matches)

[720] **720.** Questions are answered in chat by number and letter or in his own words, and the file is the only list
- Items: B1.44, B8.2. Status: built, 2026-11-19 to 2026-11-25.
- Excerpt: "Answer in chat by number and letter, for example" (B8.2)
- Your list supports it (spec 21.5): Kevin says questions can still be answered in chat
- Also tied to your requirements: spec 21.5 (matches)

[724] **724.** Features are built to work for any user and any number of addresses, not only the owner's setup
- Items: B1.49. Status: built, 2026-11-18.
- Excerpt: "built to work for any user and any number of addresses." (B1.49)
- Your list supports it (spec 9.1): Kevin wants many mail accounts read
- Also tied to your requirements: spec 9.1 (matches), spec 18.7 (matches)

[734] **734.** In audits of settings and wording, unclear purposes and judgment calls are flagged as numbered questions instead of guessed
- Items: B1.66, B1.67. Status: built, 2026-11-22 to 2026-11-23.
- Excerpt: "it doesn't guess. It brings those to you as numbered questions." (B1.67)
- Your list supports it (spec 13.3): Kevin asked for an audit of every noun and verb
- Also tied to your requirements: spec 13.3 (matches), spec 15.6 (matches)

[757] **757.** Each look is checked in light and dark, at desktop and phone width, with every card, button and tag readable and pressable.
- Items: B2.4. Status: planned, 2026-11-25.
- Excerpt: "Each look, in light and dark, at desktop and phone width" (B2.4)
- Your list supports it (spec 16.3): Kevin wants every look readable with strong contrast.
- Also tied to your requirements: spec 16.3 (matches), spec 20.1 (differs, see Section 1)

[762] **762.** Rules are tested with made-up rules and test cards: a baseline round first, then after each Approve the other open card of that kind must have changed.
- Items: B2.9, B2.10, B2.76. Status: built, 2026-11-25.
- Excerpt: "make up pretend rules, generate cards and test whether they follow the rules, before you use it live" (B2.9)
- Your list supports it (spec 6.3): Kevin asked to see a rule saved and then applied to existing and new cards.
- Also tied to your requirements: spec 6.3 (matches)

[768] **768.** A test page serves long text threads and slow answers so look and scrolling can be proved in a browser.
- Items: B2.17. Status: built.
- Excerpt: "long threads (300 messages) and slow answers (2 seconds), on a scratch home." (B2.17)
- Your list supports it (spec 10.4): Kevin wants whole long threads to load without the section collapsing.

[773] **773.** A change is refused before it is saved or merged if any page message points at a setting, button or section that does not exist
- Items: B2.25, B6.9, B6.10, B6.15, B6.16, B6.17, B6.21, B6.45, B6.50, B9.6, B9.7, B9.8, B9.9, B9.10. Status: built, 2026-11-20 to 2026-11-21.
- Excerpt: "If a message sends you to a setting, button or section that doesn't exist by that name, the merge is refused." (B6.45)
- Your list supports it (spec 14.7): Kevin wants page messages never to send him somewhere that does not exist.
- Your list supports it (spec 14.7): Kevin wants no message that sends him to a place that does not exist.
- Your list supports it (spec 14.7): Kevin wants page messages never to send him somewhere that does not exist
- Also tied to your requirements: spec 14.7 (matches), spec 14.7 (matches), spec 14.7 (matches)

[775] **775.** The online repository runs the full test set on every change and refuses it until it passes, while the owner's computer keeps minimal testing
- Items: B2.42, B2.44, B9.21. Status: built (B2.42, B2.44, 2026-11-20 to 2026-11-25); planned (B9.21, 2026-11-25).
- Excerpt: "GitHub refuses to accept a change into the program until it passes, and only you can change that rule." (B9.21)
- Your list supports it (spec 7.1): An outside check judges the work instead of the builder
- Your list says nothing on it: Kevin's list does not mention where the full test set runs.
- Also tied to your requirements: spec 7.1 (matches)

[779] **779.** A guard change is tested on many cases in a separate empty session: every real protection still refused, harmless commands let through.
- Items: B2.50, B3.4, B3.71, B3.74. Status: planned (B2.50, B3.74, 2026-11-24 to 2026-11-25); built (B3.4, B3.71, 2026-11-23 to 2026-11-24).
- Excerpt: "It refuses every real protection, closes the 11 holes the current guard misses" (B3.71)
- Your list supports it (spec 19.6): Testing that harmless commands stop being refused serves Kevin's guard rule.

[789] **789.** A reported miss is reproduced with the owner's exact steps or words on a throwaway copy before the fix goes on the page.
- Items: B2.69, B2.75. Status: planned (B2.69, 2026-11-20); built (B2.75, 2026-11-23).
- Excerpt: "The exact steps you took (draft, rewrite, small edit, Send) are tested before it goes onto your page." (B2.69)
- Your list supports it (spec 9.8): Kevin wants the version he last edited to be the one sent.
- Also tied to your requirements: spec 9.8 (matches)

[794] **794.** Acceptance tests are written blind from the acceptance list by someone who never sees the builder's code, and the builder never sees or changes them
- Items: B2.82, B6.24, B6.25, B6.26, B6.87. Status: planned (B2.82, B6.24, B6.26, B6.87, 2026-11-25); built (B6.25, 2026-11-25).
- Excerpt: "a blind tester writes tests from the spec only into a second private repo the builder cannot reach" (B6.26)
- Your list supports it (spec 7.1): Keeps the builder from grading its own work.
- Your list supports it (spec 7.1): Kevin says the builder cannot judge its own work.
- Also tied to your requirements: spec 7.1 (matches), spec 7.1 (matches)

[797] **797.** A guardrail review covered every guard and recorded the owner's answers: most loosened, none dropped, the plugin's set confirmed for install.
- Items: B3.2, B3.35. Status: planned (B3.2, 2026-11-25); built (B3.35, 2026-11-25).
- Excerpt: "18 guards reviewed, covering 8 hook programs, all 41 rule book rules and 2 Claude Code checks." (B3.35)
- Your list supports it (spec 19.6): The review loosens guards toward stopping only real harm.

[799] **799.** The roadmap lock guards only the roadmap's own safety files, judging a command by what it would write; other plugin files can be edited
- Items: B3.6, B3.15, B8.11. Status: built, 2026-11-25.
- Excerpt: "the lock now stops only real harm to the roadmap's own safety files, and judges a command by what it would write" (B8.11)
- Your list supports it (spec 19.6): Kevin wants the roadmap to have very few blocks
- Your list supports it (spec 19.6): Kevin wants the roadmap to have very few blocks.
- Also tied to your requirements: spec 19.6 (matches)

[802] **802.** The roadmap is not a critical function and keeps only real-harm blocks.
- Items: B3.9, B3.27. Status: built, 2026-11-25.
- Excerpt: "The roadmap IS NOT A CRITCAL FUNCTION. it should have very few blocks." (B3.27)
- Your list supports it (spec 19.6): Kevin's own words on roadmap blocks.
- Also tied to your requirements: spec 19.6 (matches)

[803] **803.** One end-of-turn roadmap check remains for work the roadmap does not show; it is silent when nothing is owed and never blocks a plain answer.
- Items: B3.10, B3.37. Status: built, 2026-11-18 to 2026-11-26.
- Excerpt: "It is silent when nothing is owed and never blocks a plain answer." (B3.10)
- Your list supports it (spec 21.2): Kevin wants every change and decision to reach the roadmap log.
- Also tied to your requirements: spec 21.2 (matches)

[806] **806.** Telling the roadmap writer first and the end-of-reply hold are reminders, not blocks.
- Items: B3.14. Status: built.
- Excerpt: "and the end-of-reply hold are now reminders, not blocks." (B3.14)
- Your list supports it (spec 19.6): Kevin wants the roadmap to have very few blocks.
- Also tied to your requirements: spec 19.6 (matches)

[807] **807.** A new block needs a check against ordinary work by someone other than the builder, plus the owner's OK.
- Items: B3.16. Status: built, 2026-11-25.
- Excerpt: "A new block needs a check against ordinary work by someone other than me before it goes live" (B3.16)
- Your list supports it (spec 7.1): Kevin says the builder cannot judge its own work.
- Also tied to your requirements: spec 7.1 (matches)

[808] **808.** Independent researchers find which blocks are truly necessary, others list the real blocks, others fix the gaps.
- Items: B3.17. Status: planned, 2026-11-25.
- Excerpt: "Independent researchers search the internet for which blocks are absolutely necessary." (B3.17)
- Your list supports it (spec 19.6): Aims guards at only really harmful actions.

[809] **809.** There is no To Delete folder; things are deleted outright.
- Items: B3.19. Status: built, 2026-11-25.
- Excerpt: "no To Delete at all: delete outright" (B3.19)
- Your list supports it (spec 19.5): Kevin says deleted things should just be deleted.
- Also tied to your requirements: spec 19.5 (matches)

[810] **810.** The mail guard refuses only commands that actually send.
- Items: B3.20. Status: built, 2026-11-25.
- Excerpt: "1a mail rule refuses only commands that actually send." (B3.20)
- Your list supports it (spec 19.6): Narrows the guard to real harm, as Kevin wants.

[811] **811.** The program-files lock judges by where a command writes; reading is always allowed.
- Items: B3.21. Status: built, 2026-11-25.
- Excerpt: "5a program-files lock judges by where a command writes; reading always allowed." (B3.21)
- Your list supports it (spec 19.6): Narrows the guard to real harm, as Kevin wants.

[812] **812.** If the guard's rule book is missing, only sends are blocked.
- Items: B3.22. Status: built, 2026-11-25.
- Excerpt: "6a rule book missing: block only sends." (B3.22)
- Your list supports it (spec 19.6): Narrows the guard to real harm, as Kevin wants.

[813] **813.** The no-installs guard refuses only commands that actually run an install, update, check or rebuild, not ones that mention them.
- Items: B3.23, B3.33. Status: built (B3.23, 2026-11-25); planned (B3.33, 2026-11-25).
- Excerpt: "no-installs hook refuses only commands that actually run an install, update, check or rebuild." (B3.23)
- Your list supports it (spec 19.6): Kevin says mentioning a word must not trip a guard.
- Also tied to your requirements: spec 19.6 (matches)

[814] **814.** Guards refuse only really bad things and judge a command by what it does, not by words in it; otherwise a reminder.
- Items: B3.24, B3.26. Status: built, 2026-11-25.
- Excerpt: "judge a command by what it actually does, never by words it contains; prefer a reminder over a refusal" (B3.26)
- Your list supports it (spec 19.6): Matches Kevin's rule that guards stop only really harmful actions.
- Also tied to your requirements: spec 19.6 (matches)

[815] **815.** Blocks are fixed at their source with the top-level session, never handed to the owner as manual steps.
- Items: B3.25, B3.78. Status: built, 2026-11-25.
- Excerpt: "Blocks are fixed at their source with the CEO session, never handed to Kevin as manual steps." (B3.25)
- Your list supports it (spec 19.6): Kevin wants projects to work without him intervening.
- Also tied to your requirements: spec 19.6 (matches)

[818] **818.** The context-only hooks never block and are kept.
- Items: B3.34. Status: built, 2026-11-25.
- Excerpt: "They only add information or keep files in step." (B3.34)
- Your list supports it (spec 19.6): Hooks that never block fit Kevin's guard rule.

[825] **825.** Anything new that runs on the owner's machine needs his OK first.
- Items: B3.44. Status: built, 2026-11-20.
- Excerpt: "anything new running on your machine needs your OK first." (B3.44)
- Your list supports it (spec 19.2): Kevin does not want more small always-on programs added.

[830] **830.** Versions stay 0.x until everything is done and the owner is happy; one last push makes it 1.0.
- Items: B4.1, B4.3, B4.8, B4.71. Status: planned (B4.1, B4.3, B4.8, 2026-11-25); built (B4.71, 2026-11-25).
- Excerpt: "Updates stay 0.x (0.1.13, 0.1.14 ...) until everything he wants is done" (B4.1)
- Your list supports it (spec 19.3): Kevin says the project is 0.x and becomes 1.0 at the final push.
- Also tied to your requirements: spec 19.3 (differs, see Section 1)

[833] **833.** Every push raises the version number, because the plugin store sees an update only by a changed version.
- Items: B4.5, B4.34, B4.36, B4.64. Status: built, 2026-11-17 to 2026-11-23.
- Excerpt: "Updates are detected by comparing version text, so every release must change the version." (B4.36)
- Your list supports it (spec 19.3): Consistent with the version going up on each push.
- Also tied to your requirements: spec 19.3 (matches)

[841] **841.** An update switches the regular mail gathering off at its start, waits for any running pass, and confirms it is back on at the end
- Items: B4.16, B4.49, B6.42. Status: built, 2026-11-20.
- Excerpt: "an update first switches off the 15-minute email check, waits for any check already running to finish, and stops the page." (B4.49)
- Your list supports it (spec 17.5): Kevin wants gathering stopped before every update.
- Also tied to your requirements: spec 17.5 (matches), spec 17.5 (matches)

[849] **849.** The install procedure stops the listener, takes a checked full backup, merges, sets the version, pushes, installs, then starts fresh.
- Items: B4.29. Status: built, 2026-11-25.
- Excerpt: "both .duckdb files are inside. If not, stop." (B4.29)
- Your list supports it (spec 17.5): It stops the gathering before the update, as Kevin asked.

[871] **871.** A helper compares everything the page and assistant can do with what the box can do and adds each missing ability to the box.
- Items: B5.4. Status: built, 2026-11-24.
- Excerpt: "A helper compares everything the page and the assistant can do with what the box can do" (B5.4)
- Your list supports it (spec 1.1): Kevin wants the box to be a full interface able to do everything.
- Also tied to your requirements: spec 1.1 (matches), spec 2.1 (matches)

[882] **882.** The maintainer may not publish code, send, delete or set up anything self-running without stopping to ask.
- Items: B5.22. Status: built, 2026-11-17.
- Excerpt: "It can't push to GitHub, send anything, delete anything, or set up anything that runs on its own." (B5.22)
- Your list supports it (spec 19.3): Kevin says the version only goes up when he publishes, which fits the maintainer not publishing on its own.

[892] **892.** Each helper reports every agreed point with proof and what was left untested, and its report is checked and sent back for anything missing or faulty.
- Items: B6.1, B6.61, B6.67, B6.68. Status: built, 2026-11-23 to 2026-11-24.
- Excerpt: "I'll check its report against those five, and I'll send it back for anything missing." (B6.68)
- Your list supports it (spec 7.1): Work is checked by someone other than the helper that did it.

[894] **894.** A newcomer check tests what a person with no background would take each rewritten line to mean, against what the app does.
- Items: B6.5, B6.12. Status: planned (B6.5, 2026-11-25); built (B6.12, 2026-11-26).
- Excerpt: "What a person with no background would take each rewrite to mean, checked against what the app does." (B6.12)
- Your list supports it (spec 13.2): Kevin's check for clear writing uses a reader who has never seen the program.
- Also tied to your requirements: spec 13.2 (matches)

[895] **895.** Work is never accepted on the builder's own tests or look-over; a separate reviewer that did not build it decides.
- Items: B6.7, B6.8, B6.20, B6.78, B6.80. Status: built (B6.7, B6.8, B6.20, B6.78, 2026-11-25); planned (B6.80, 2026-11-25).
- Excerpt: "never mark work done on Claude's or its helpers' own tests. Acceptance is a separate reviewer that did not build it" (B6.20)
- Your list supports it (spec 7.1): Kevin says you can't judge your own work.
- Also tied to your requirements: spec 7.1 (matches)

[897] **897.** A fresh judge that built nothing compares the real page against Kevin's quoted words and posts pass or fail, and the coordinator cannot overrule it.
- Items: B6.27, B6.77, B6.82. Status: planned, 2026-11-25.
- Excerpt: "A fresh session compares the real page against your quoted words and posts pass or fail." (B6.82)
- Your list supports it (spec 7.1): An outside judge fits Kevin's rule that the builder can't judge its own work; his list has the tester use made-up cards, while one item here uses real cards.
- Also tied to your requirements: spec 7.1 (matches)

[899] **899.** Done is judged by the same requests typed in a card, the box and a desktop session giving the same result on the real page.
- Items: B6.29. Status: built, 2026-11-18.
- Excerpt: "Judge done only by the same requests typed in a card, the chat and a desktop session giving the same result" (B6.29)
- Your list supports it (spec 2.1): Kevin's check gives the same instruction in a card, the box and a desktop session.
- Also tied to your requirements: spec 2.1 (matches)

[902] **902.** The manual is checked against the real page: every part present, claims true, pictures drawn without errors at desktop and phone widths, no real names, links working.
- Items: B6.33, B6.34, B6.70, B6.71, B6.72. Status: built, 2026-11-16 to 2026-11-24.
- Excerpt: "that every picture shows properly, that no real names or mail appear, and that the links work." (B6.72)
- Your list supports it (spec 19.7): Kevin wants a manual whose pictures match the current page.

[904] **904.** A guardrail review searches past sessions for refusals and holds, leaves out throwaway test folders, and labels each judgment as an inference.
- Items: B6.36. Status: built, 2026-11-25.
- Excerpt: "Blocks in throwaway test folders (22, all guardrail tests) are left out of the counts below." (B6.36)
- Your list supports it (spec 19.6): Kevin wants guardrails to stop only really harmful actions, which a review of blocks serves.
- Also tied to your requirements: spec 19.6 (matches)

[908] **908.** A passing test count is not proof; someone other than the builder tries each change on a saved copy of the real page (dropped).
- Items: B6.49. Status: dropped, 2026-11-21.
- Excerpt: "After a helper builds something, a different session tries it out on a test copy of your page" (B6.49)
- Your list supports it (spec 7.1): The dropped idea matched Kevin's rule that work must be judged by someone else.
- Also tied to your requirements: spec 7.1 (differs, see Section 1)

[910] **910.** A helper's claim that its tests ran is checked by the coordinator rerunning them before the work is reported ready
- Items: B6.56, B7.10. Status: built, 2026-11-19 to 2026-11-22.
- Excerpt: "The maintainer had earlier reported that test as done when it hadn't run." (B6.56)
- Your list says nothing on it: Not covered by Kevin's list.
- Your list supports it (spec 7.1): A second party checks the helper's work, in line with not judging your own work

[914] **914.** The acceptance test for any card change includes reading a few real cards to see whether they make sense.
- Items: B6.79. Status: built, 2026-11-25.
- Excerpt: "the acceptance test for any card change must include reading a few real cards for whether they make sense" (B6.79)
- Your list supports it (spec 13.2): Kevin wants card writing clear to a reader; his list checks that on made-up cards, not real ones.

[917] **917.** Testers and reviewers may only read and pass or fail the work, never fix it, and get only the change and the criteria.
- Items: B6.84, B6.85. Status: planned, 2026-11-25.
- Excerpt: "A tester role that is never allowed to fix the program, only pass or fail it." (B6.84)
- Your list supports it (spec 7.1): Separating the tester from the fixer follows Kevin's rule that you can't judge your own work.

[927] **927.** Review questions are numbered with lettered choices, a recommended choice marked, and answered like 1a
- Items: B7.6. Status: built, 2026-11-25.
- Excerpt: "a. Loosen: refuse only commands that actually send (recommended)" (B7.6)
- Your list supports it (spec 21.7): Kevin wants numbered questions with lettered answers beneath
- Also tied to your requirements: spec 21.7 (matches)

[938] **938.** Bring the questions file into the questions section of the roadmap
- Items: B8.1. Status: planned, 2026-11-25.
- Excerpt: "Integrate the Questions.md into the Questions for you section of the roadmap." (B8.1)
- Your list supports it (spec 21.5): Kevin wants every roadmap to include the questions file
- Also tied to your requirements: spec 21.5 (matches)

[939] **939.** Every decision and project change goes on the roadmap the same turn without being asked; the roadmap is a log, not a gate
- Items: B8.3, B8.4, B8.12, B8.13. Status: built, 2026-11-25.
- Excerpt: "write every decision and every project change to the roadmap the same turn, without waiting to be told; never record talk as a decision" (B8.13)
- Your list supports it (spec 21.2): Kevin says the roadmap is a log of decisions and changes
- Also tied to your requirements: spec 21.2 (matches)

[965] **965.** The plugin's source, side branches, plans and snapshots live in the Assistant folder under Development
- Items: B9.3, B9.13. Status: built, 2026-11-25.
- Excerpt: "The plugin, its side branches, plans, research and snapshots now live in the Assistant folder, under Development" (B9.3)
- Your list supports it (spec 19.1): Kevin wants everything the assistant needs in the Assistant folder
- Also tied to your requirements: spec 19.1 (matches)

[969] **969.** Tests live in a second private repository the builder's login cannot reach
- Items: B9.20. Status: planned, 2026-11-25.
- Excerpt: "They go in a second private GitHub repo that my builder login has no access to." (B9.20)
- Your list supports it (spec 7.1): Kevin says you cannot judge your own work
- Also tied to your requirements: spec 7.1 (matches)

[971] **971.** Manual pictures are drawn from a made-up stand-in in the page's current look, never the owner's real mail, texts or cards.
- Items: B10.2, B10.14, B10.34. Status: built, 2026-11-24.
- Excerpt: "its pictures redrawn from your page's current look with made-up data" (B10.14)
- Your list supports it (spec 19.7): Kevin wants manual pictures made from the current settings.
- Also tied to your requirements: spec 19.7 (matches)

[972] **972.** Rule tests send pretend emails from the owner's own addresses and delete the test cards afterward.
- Items: B10.3. Status: built, 2026-11-25.
- Excerpt: "send pretend emails from your own addresses; delete the cards after" (B10.3)
- Your list supports it (spec 6.3): Kevin asked to test saving a rule and seeing new cards obey it, which needs test emails.

[975] **975.** Claude sessions may delete files in Claude's own temporary folders without being blocked.
- Items: B10.30. Status: built, 2026-11-21.
- Excerpt: "Claude sessions can now delete files in Claude's own temp folders without being blocked." (B10.30)
- Your list supports it (spec 19.6): Kevin wants guardrails to stop only really harmful actions.

[984] **984.** Model-based checks on the online repository use his Claude usage through a key he creates once
- Items: B11.19. Status: planned, 2026-11-25.
- Excerpt: "use your Claude usage through a key you create once." (B11.19)
- Your list supports it (spec 7.1): An outside check judges the work instead of the builder

## Dropped procedures

Number, one-line title, and the places the item numbers' sources name.

[632] Assistant sessions working in the assistant's folder can message each other, while real email stays blocked
  Sources: Roadmap page row steps/step-01
[634] A connection card says what it connects to, reads and changes, and a build may do only what its card said.
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Live build\Connection design.md
[635] A study of the mail part, starting with folders and labels, planned only with nothing built until the owner agrees.
  Sources: Roadmap page row steps/step-45
[636] The mail part, the draft writer and the ready-to-send summary are checked by running the page's script.
  Sources: Plugin repo, branch main: tests/mail_page_acceptance.py
[639] Each look is built as one style file with light and dark colors and its fonts named at the top
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Looks design.md
[641] How each look is wired in: style rules in the page, fonts in the font list, name in the allowed looks lists
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Looks design.md
[642] The redesign was built against the owner's own look and mode, changing shared colors plus that look
  Sources: Plugin repo, branch main: docs/redesign-findings.md
[643] The page script finds things only by id and data marks, so the style file must keep the names the script writes
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Mockups\Style\Keep these names.md
[644] Build one judgment all the way through (key, grader, coach, level) before the next, starting with show or hide
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\self-improving-talk.md
[646] Leftover sorting instructions that point to rules nobody wrote are either completed or removed
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Live build\Assistant design review.md
[648] The setup files are kept in one place in the plugin.
  Sources: Roadmap page row steps/step-03
[650] The way back from adopting is tried in a test and must restore the old program exactly.
  Sources: Plugin repo, branch main: tests/adopt_acceptance.py; Plugin repo, branch main: tests/adopt_in_place_acceptance.py
[651] A copy's whole life is tested from the built package: install, a pass, a failed and a good update, uninstall.
  Sources: Plugin repo, branch main: tests/lifecycle_acceptance.py
[652] When switching Kevin to the new system, the old one is left untouched and both run side by side until he calls the switch.
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Live build\Plan.md
[653] The plugin's online home was private, so adding it only works on a computer signed in to an account that can see it; making it public is Kevin's call.
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Plugin build\manual\open points.md
[655] Kevin's own switch-over kept heavy data in place, moved retired pieces to a dated To Delete folder, and took the live assistant off last.
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Live build\Plugin family plan.md
[656] After the first failed update, the coordinator runs updates itself with a time limit and confirms them on the real page.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[657] Inside the plugin package the roadmap's commands get fixed new names, while the roadmap's own source keeps its names.
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Plugin build\LAYOUT.md
[661] A file is not deleted or moved aside while code or anything else still uses it
  Sources: Plugin repo, branch main: engine/System/live/core/inuse.py; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[662] The guard hook is tested against the real guardrails in a normal session and a hidden run, and changing one rule in a scratch copy shows the hook enforcing it
  Sources: Plugin repo, branch main: tests/guards_acceptance.py
[663] The two guardrail exceptions approved on 11/25 are covered by tests
  Sources: Plugin repo, branch main: tests/rsi_guard_acceptance.py
[664] When a guard or lock refuses a step, the refusal is shown word for word and work stops, never done another way
  Sources: Plugin repo, branch main: skills/update/SKILL.md; Roadmap page row steps/item-guard-narrower; C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\guard-refusal-means-stop.md; C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\temp-deletes-allowed.md; C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Session brief - lock and install.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl; Transcript a1722239-84ee-4740-b744-e7afb69923c2.jsonl
[665] A product feature that defeats a guard is Kevin's decision, never merged on Claude's judgment
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\guard-refusal-means-stop.md
[666] The box change card was built into the core for every user rather than made as the owner's own change.
  Sources: Roadmap page row steps/item-chat-does-everything
[667] All folder locations are named in one place so a test home can stand in for the real one
  Sources: Plugin repo, branch main: engine/System/live/paths.py
[668] Rules for working with the database: delete child rows first, split table changes from updates, and let the database pick new ids
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\MEMORY.md
[669] The rebuild waits until mail, texts, Slack and cards all work
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[670] The page server's repeated start warning is explained and fixed at its source.
  Sources: Roadmap page row steps/item-fewer-programs
[671] The rebuild must be run before November 30, when older chat history starts to disappear, and the owner starts it
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[672] The new manual is written only when ready to push to the public code site, so it is not rewritten afterward, and ships with the next update on Kevin's yes
  Sources: Roadmap page row steps/item-manual-catchup; Roadmap page row steps/item-wording-audit; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[673] The manual is written from the program as it stands, says only what is confirmed, and lists anything unconfirmed as an open point
  Sources: Plugin repo, branch main: docs/changes.md; C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Plugin build\manual\open points.md
[674] The manual and change list are updated in the same change as every piece of work, and a job is not done until both are current
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\plugin-maintainer-scope.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript a1bd9e09-49c2-47a3-8be3-cb3a8df31b75.jsonl
[675] Each kind of account is reached by one small program part with a fixed set of steps.
  Sources: Plugin repo, branch main: engine/System/live/connections/CONNECTIONS.md
[677] A new connection is tested against a practice address or recorded replies, with the first real call as its own last step.
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Live build\Connection design.md
[678] Helpers use the cheapest model that does the job well, with the strongest model only where reasoning matters or the settings ask for it
  Sources: Plugin repo, branch main: skills/roadmap-director/SKILL.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\default-model-opus.md; C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\planner-coordinates-only.md
[679] A takeover is proved by saving the database again and running the carry-over report, which must show nothing to change and equal counts
  Sources: Plugin repo, branch main: skills/roadmap-setup/SKILL.md
[680] The builder runs every check it can itself first, on test pages or test cards, and brings the owner only the checks it truly cannot do
  Sources: Plugin repo, branch main: skills/roadmap-director/SKILL.md; Roadmap page row steps/item-questions-file; Roadmap page row steps/step-60; Plugin repo, branch main: docs/changes.md; C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\do-look-checks-myself.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript a1722239-84ee-4740-b744-e7afb69923c2.jsonl
[694] While the owner is away, keep building, pushing and installing every planned piece
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\RSI plan.md
[695] A fault is traced from the logs and fixed where it starts, not patched further along
  Sources: Roadmap page row steps/item-answered-raw-data; Roadmap page row steps/item-card-stuck-reading
[696] Work is built in small steps, each ending with a quick check, a real page check and the owner's look before the next starts
  Sources: Roadmap page row steps/item-calendar; Roadmap page row steps/item-judgment-rebuild; C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Judgment rebuild design.md
[697] While the owner is measuring a run's usage, new work waits until that run ends
  Sources: Roadmap page row steps/item-card-date; C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\measured-runs-run-alone.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[698] A draft such as the voice guide is shown for approval before anything in the app is rewritten
  Sources: Roadmap page row steps/item-voice-guide
[699] Opening, showing and sending run as plain scripts; AI is used only for judgment and drafting words
  Sources: Roadmap page row steps/step-58; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[700] The redesign changes only looks and navigation, not behaviour or wording
  Sources: Plugin repo, branch main: docs/redesign-findings.md
[701] Anything another program must reach is kept out of the hidden app data folder and put in Documents
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\appdata-writes-are-sandboxed.md
[702] Before asking a question, check whether he already answered or deferred it, or whether the tool handles it
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\dont-repeat-declined-questions.md
[703] Faults in built work are fixed without asking, asking only when a fix would change agreed behaviour
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\fix-all-faults.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl
[704] When shopping or researching, never request a quote or ask anyone to send him anything
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\no-quote-requests.md
[705] Do every technical step for him; when only he can act, give a link and exact steps one at a time
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\kevin-not-a-programmer.md
[706] When two question lists are open, the number and shape of his answers show which list they belong to
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\match-answers-to-question-set.md
[707] Every feature ships with the design of how it is used
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\office-tower-judge-ux.md
[708] Follow his workspace rules quietly during plugin work and never ask him to reconcile them with plugin decisions
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\office-tower-keep-claudeos-out.md
[709] Prove commands work in a session mode before building on it; if not, tell him before falling back and call it a workaround
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\sdlc-office-live-hookup.md
[710] When he asks for something, start it the same turn on a stated assumption or ask the one blocking question
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\start-what-kevin-asks.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[711] When a helper says it is waiting, the coordinator checks what it waits on at once and unblocks it if that is already done
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\start-what-kevin-asks.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[712] When a step fails or is blocked, stop, report it and fix the block instead of trying workarounds
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\stop-chasing-small-failures.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript b6dc3d79-6ff8-40ac-b407-0e53b635b1fe.jsonl
[713] At the first failure, say plainly if he could do it by hand and give click-by-click steps
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\stop-chasing-small-failures.md
[714] A new major capability starts a conversation; nothing is planned or built until he agrees the whole design
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\talk-before-designing.md; C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Live build\Plugin family plan.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[715] Work that other work waits on ships first and on its own, then the rest is bundled
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\unblock-first.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl
[716] Use a proven outside project the way its makers run it; any difference is named as a change and needs his OK
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\use-proven-projects-as-is.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[717] New code goes in new folders and may use existing engine parts but never edits them
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Live build\Plan.md
[718] A fault fix is checked where its result is used, and a new rule goes in the document its readers follow
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\CLAUDE.md
[719] The questions file is edited in place, never deleted, records answered questions as decisions, and keeps the plugin free of personal content
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Possible additions\The questions file.md
[721] A design review reads the live page only, presses and changes nothing, and writes a ranked list of findings before anything is built
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Live build\Assistant design review.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Plugin repo, branch main: docs/redesign-findings.md
[722] The planner, maintainer and coordinator cover only the plugin's own work and repository, not the owner's other setup or other plugins
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\plugin-maintainer-scope.md
[723] If a mail service cannot do an action, bring it to him rather than working around it
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[725] Do not guess or claim a cause or result until the records show it; take back statements the records do not support
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[726] Build with free pieces, no paid license; outside code whose license would force giving the plugin away is used for ideas only and rewritten fresh
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[727] A wish, a statement or a question is not a go-ahead; nothing new starts until he actually chooses
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl
[728] Messaging and chat services refuse to be shown inside another site, so the page builds its own sections that look and act like them
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[729] Design review plugins check the Texts, Slack and Mail sections in test rounds, and a new look is built only after his go
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[730] Adding a plugin goes through its card, which only the owner can press
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[731] Optional paid connectors are skipped and cost is called unconfirmed when not found on the maker's site
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[732] The data rebuild is not touched without his go
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[733] Calendar research looks only at community-built projects with no paid tier
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[735] Before an erasing run, a dry run shows what would be erased and fetched without touching anything
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[736] If a rebuild step goes wrong or times out twice, stop and fix the cause instead of pushing on or retrying
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[737] Claims about what is running or stuck are checked against clock times and logs before they are reported, and misreadings are corrected at once
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl
[738] An unexplained warning is proven harmless and then silenced where it starts
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[739] A card a helper's check answered by mistake is left alone because it is his card
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[740] A rule's wording needs his approval before anything is written
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[741] Each helper gets one piece, and nothing goes to helpers while any question about the idea or plan is still open
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\build-what-he-says.md; C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\talk-before-designing.md
[742] Plans go in the questions file for him to approve before anything is built
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[743] Files that belong to the Claude app are left alone
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[744] The external browser is used only when the built-in browser cannot do the job
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[745] A workaround is called a workaround and offered with a by-hand alternative
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript 9273085d-7a61-49ac-94ba-bd19a48e2e8a.jsonl
[746] Material he shares is reported in its own words and order first and re-read with his exact words before every answer
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\build-what-he-says.md
[747] When he says stop, stop and do nothing else until told
  Sources: Transcript 406e11e6-359c-419a-8907-356f68f12ed7.jsonl
[748] Never change security permissions on the operating system's own files
  Sources: Transcript e2838c2b-da94-4603-90a3-1df6d18e58f3.jsonl
[749] Give the exact file name and size before any download
  Sources: Transcript e2838c2b-da94-4603-90a3-1df6d18e58f3.jsonl
[750] Replaced or leftover files are moved to a dated To Delete folder instead of being deleted
  Sources: Transcript e2838c2b-da94-4603-90a3-1df6d18e58f3.jsonl; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Session brief - lock and install.md
[751] A test and how to undo it are recorded in the project's memory notes
  Sources: Transcript b608ebf4-334a-464e-8cae-b9d7a3ca2fb5.jsonl
[752] Research only looks and reports; it backs out of any page that leads into changing, cancelling or enrolling
  Sources: Transcript c986e768-5434-425b-a2a9-0b71d0fc5c8e.jsonl
[753] Answer from his own data first and ask only what is not there
  Sources: Transcript c986e768-5434-425b-a2a9-0b71d0fc5c8e.jsonl
[754] Features are built all at once with no stages
  Sources: Transcript a1bd9e09-49c2-47a3-8be3-cb3a8df31b75.jsonl
[755] On the owner's computer each change gets one quick test or look at what changed, with no full test suites, repeated passes or database copies
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\RSI plan.md; C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\minimal-testing.md; C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\roadmap-only-live-truth.md; C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\parallel-by-default.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript 406e11e6-359c-419a-8907-356f68f12ed7.jsonl
[756] One real end-to-end run on a made-up assistant with the real AI model and real page, kept away from the live assistant.
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\RSI plan.md; Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl
[758] After every update a tester opens the real page and tries each change the way the owner would, and anything broken is fixed and checked again
  Sources: Roadmap page row steps/item-live-tester; C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\RSI plan.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[759] The live tester checks the roadmap rows against what it sees and sends faults back to be fixed before the owner hears.
  Sources: Roadmap page row steps/item-live-tester
[760] Guard hooks are tested by feeding them sample commands against a stand-in rule book, proving the plumbing without the real rules.
  Sources: Roadmap page row steps/item-main-no-jobs-block; Plugin repo, branch main: hooks/test_rulebook_guard.py; C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Plugin build\RULEBOOK hooks section.md
[761] Every test passes on the main copy of the plugin, since the save check runs them.
  Sources: Roadmap page row steps/item-main-tests-failing; Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl
[763] Tests must point at page sections that still exist; a stale one was fixed.
  Sources: Roadmap page row steps/item-stale-section-test
[764] A guard limits test commands: at most 2 test files, no whole test folders, no copies of the real database, a 2 minute cut-off and a cap on runs per session.
  Sources: Roadmap page row steps/item-test-limits; Plugin repo, branch main: .claude/hooks/test_limits.py; Plugin repo, branch main: docs/changes.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[765] A commit or merge runs only the tests mapped to the parts it changes, never the whole set; too wide a change names the rest instead of running them.
  Sources: Roadmap page row steps/item-test-limits; Plugin repo, branch main: githooks/pre-commit; Plugin repo, branch main: githooks/run_matching_tests.py; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[766] The update count fix is tested on a made-up home with one of each kind of file.
  Sources: Roadmap page row steps/item-update-count-line
[767] Each part of the cards test names the fault it guards against and changes nothing outside its scratch folder.
  Sources: Plugin repo, branch main: tests/cards_acceptance.py
[769] Whatever a test makes, such as scratch copies, test cards, rules or pages, is removed as soon as the test ends
  Sources: Plugin repo, branch main: tests/_cleanup.py; Plugin repo, branch main: docs/changes.md; Roadmap page row steps/item-rules-live-test; C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\temp-deletes-allowed.md; C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Plugin build\manual\checks.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript a1722239-84ee-4740-b744-e7afb69923c2.jsonl; Transcript a5369da4-55f9-4fbd-bffa-82b66f0eaf82.jsonl
[770] Tests stand in for the AI runs and the network, so nothing outbound is tried and any attempt fails the test.
  Sources: Plugin repo, branch main: tests/card_rules_acceptance.py; Plugin repo, branch main: tests/rsi_loop_acceptance.py; Plugin repo, branch main: tests/replay_acceptance.py
[771] Tests run on a separate scratch copy with its own folder and settings, accounts and sending off, touching nothing real, and are removed afterward
  Sources: Plugin repo, branch main: tests/catch_up_acceptance.py; C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Plugin build\LAYOUT.md; C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Live build\Plugin family plan.md; Plugin repo, branch main: tests/adopt_acceptance.py; Plugin repo, branch main: tests/chat_panels_server.py; Plugin repo, branch main: tests/lifecycle_acceptance.py; Plugin repo, branch main: tests/rsi_grader_acceptance.py; Plugin repo, branch main: tests/mail_acceptance.py; Plugin repo, branch main: hooks/test_rulebook_guard.py; C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Plugin build\Switch-over steps.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl; Transcript a1722239-84ee-4740-b744-e7afb69923c2.jsonl
[772] The roadmap blocks, lock, reminder, setup and write-it-yourself mode are proved by a test on a throwaway project folder that must end all passed.
  Sources: Plugin repo, branch main: README.md; Plugin repo, branch main: hooks/test_roadmap_blocks.py; Plugin repo, branch main: hooks/test_roadmap_direct.py
[774] A redesign of shared styling must keep the other looks working, covered by a looks test.
  Sources: Plugin repo, branch main: docs/redesign-findings.md
[776] Every build round ends with a real play-through as a brand-new user, fixing friction before reporting done.
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\office-tower-judge-ux.md
[777] After putting a change live, a gathering pass is started at once and the page is looked at, instead of waiting for the timed pass.
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\run-passes-on-demand.md; Transcript 9273085d-7a61-49ac-94ba-bd19a48e2e8a.jsonl
[778] Checks cover every kind of card and every button and choice as the owner would see them, against the approved plan.
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\parallel-by-default.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[780] The take-over-in-place flow was proven on a stand-in copy with accounts off, measuring the downtime.
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Plugin build\Switch-over steps.md
[781] A claim such as whether the side panel refreshes by itself is verified in a real session before it is relied on.
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Possible additions\The questions file.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[782] Browser checks use the owner's real look and settings, not a differing test copy.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[783] Card fixes are proven on copies of the affected cards, never the real ones, and real cards are rebuilt only on the owner's yes
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[784] New work is tested against a mailbox sized like the owner's so locking and slowdowns are caught.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[785] A failing check is traced on a copy of the owner's real data or mail, kept away from the live assistant with sending off.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[786] Checks on the owner's real page only read and press only made-up test cards removed afterward, leaving his page as it was
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript a1722239-84ee-4740-b744-e7afb69923c2.jsonl; Transcript a5369da4-55f9-4fbd-bffa-82b66f0eaf82.jsonl; Roadmap page row steps/item-card-stuck-reading; Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl; Roadmap page row steps/item-live-tester; C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\do-look-checks-myself.md
[787] Every update saves a full, checked copy of the assistant's data first; a damaged database is repaired only on copies with the owner told what would be lost.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl
[788] Do not open a second messages web tab, since it pulls the connection away from the owner's tab.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[790] The maintainer runs every test that covers code a change touches and will not merge without them.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[791] Each fix comes with a test that fails without it.
  Sources: Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl
[792] Tests must pass at any hour, not fail in a window after midnight.
  Sources: Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl
[793] A failing test is not worked around; the helper checks whether it already fails on unchanged code.
  Sources: Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl
[795] Test work lists what it has not yet checked so the coordinator checks it when wiring in.
  Sources: Transcript a5369da4-55f9-4fbd-bffa-82b66f0eaf82.jsonl
[796] Every guardrail change waits for the owner's approval of its exact plain-word text before anything is written.
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\RSI plan.md; C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Session brief - lock and install.md; Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl
[798] A command that builds its text from variables still gets the strict guard check, by design.
  Sources: Roadmap page row steps/item-guard-narrower
[800] Installs, updates, checks and other long jobs run on background helpers, even when typed in the main session, so the main session stays free to talk
  Sources: Roadmap page row steps/item-main-no-jobs-block; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\installs-by-helper.md; Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl
[801] If a block's own script fails to run, the command is let through rather than refused.
  Sources: Roadmap page row steps/item-main-no-jobs-block; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[804] When a project's settings would refuse a write that is needed, the change is brought to the owner for approval rather than routed around.
  Sources: Roadmap page row steps/step-24; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[805] A roadmap row may be marked ready for the owner's look only once it carries checks that were run and recorded; other such writes are refused
  Sources: Roadmap page row steps/step-60; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript a1bd9e09-49c2-47a3-8be3-cb3a8df31b75.jsonl
[816] Only the owner changes the guards or safety settings; the assistant gives him the commands to run himself.
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Plugin build\Switch-over steps.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[817] The installed plugin has 7 hook programs in 18 places; 4 can stop work and 3 only add context.
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Guardrail review.md
[819] Another project's own guards were left unreviewed; a review in the same style is suggested.
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Guardrail review.md
[820] The roadmap settings guard refuses changes to a project's roadmap settings but allows reading them.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript a1bd9e09-49c2-47a3-8be3-cb3a8df31b75.jsonl
[821] An end-of-turn check stops the session once if it wrote the roadmap but did not update the page's roadmap copy.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript a1bd9e09-49c2-47a3-8be3-cb3a8df31b75.jsonl
[822] A report that changes no roadmap row, such as a helper saying it is still running, writes nothing to the roadmap
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript a1bd9e09-49c2-47a3-8be3-cb3a8df31b75.jsonl
[823] The safety guard's rule book must not live in a folder an update empties, so a failed update cannot lock out messages to helpers.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[824] Outside extension code is reviewed first for what it reads, what leaves the PC, permissions and license; unlicensed code is not reused.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[826] A slow or unreliable test is marked and skipped automatically instead of rerun until it passes.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[827] Getting around the test guard, or changing it with a permission file, is the owner's call, limited to the named tests once each on throwaway copies; touching an unapproved test needs a separate yes.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[828] A guard exception lets only the rebuild tool's own commands through, and needs the owner's yes.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[829] Finishing the narrower guard test is left to the assistant to work out, with the owner's help if needed.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[831] Before a big install or redesign a restore point is saved, with the program and data copied aside, so the old state comes back in one step
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\RSI plan.md; Roadmap page row steps/item-redesign; C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\self-improving-talk.md; Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[832] Work that lives in the plugin reaches the owner's PC only when the plugin updates from GitHub, so it needs a push first.
  Sources: Roadmap page row questions/q-item-desktop-same-as-box-push; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[834] The page build uses the copy kept with the program and is complete or stops with an error.
  Sources: Roadmap page row steps/item-build-fix; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[835] Roadmap rows never carry version numbers, and the manual reads the version from the plugin
  Sources: Roadmap page row steps/step-04; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript e8565bec-492b-4c84-9d5f-04c83982e7a9.jsonl; Transcript a1bd9e09-49c2-47a3-8be3-cb3a8df31b75.jsonl
[836] After a push, the online main copy is confirmed equal to the local one.
  Sources: Roadmap page row steps/step-16; C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Session brief - lock and install.md
[837] The public repository gets one clean entry with no personal details, while the detailed step history stays private on the owner's computer
  Sources: Roadmap page row steps/step-36; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\independent-check-loop.md
[838] Only one update runs at a time, and an update refuses a half-merged or half-refreshed plugin copy.
  Sources: Roadmap page row steps/step-53; Plugin repo, branch main: docs/changes.md; C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\run-update-without-asking.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[839] Everything planned is built, installed at the current version and checked on the owner's real page.
  Sources: Roadmap page row board/next
[840] An update checks the program loads and the page answers, and puts everything back by itself if that fails.
  Sources: Plugin repo, branch main: docs/changes.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[842] An update no longer mistakes the program's own files for ones the owner added.
  Sources: Plugin repo, branch main: docs/changes.md
[843] Release notes have one plain line per noticeable change, newest version first, added when the number is raised.
  Sources: Plugin repo, branch main: docs/changes.md
[844] The update card and update walk-through read the release notes.
  Sources: Plugin repo, branch main: docs/changes.md
[845] The push yes is asked in the session the owner is in, never by sending him to a helper session.
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\plugin-push-yes-here.md
[846] Changes are made and saved locally, and each push goes up only after the owner's yes for that version
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\plugin-push-yes-here.md; C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\redesign-overnight-2026-11-20.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl; C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\plugin-maintainer-scope.md
[847] Only the GitHub push needs the owner's yes; builds, fixes, merges, syncs and updates go ahead without asking.
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\run-update-without-asking.md
[848] When the owner asks for a change, the update is run at once without asking.
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\run-update-without-asking.md
[850] After install the listener comes back running hidden with no console window and its scheduled job on again.
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Session brief - lock and install.md
[851] The owner's switch-over takes his running assistant over in place, keeping his data, instead of reinstalling.
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Plugin build\Switch-over steps.md
[852] Switch-over order: rebuild and check, owner runs the roadmap test, owner approves the push, then he installs the plugin himself.
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Plugin build\Switch-over steps.md
[853] The package build is repeatable: building the same sources, on any copy, gives an identical result
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Plugin build\LAYOUT.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[854] Nothing reaches GitHub except through a release check: staging build, personal-data search, strict validation, and the owner's yes.
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Live build\Plugin family plan.md
[855] The repository stays private while being proven and goes public only by the owner's own act.
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Live build\Plugin family plan.md
[856] A private repository makes the daily update look fail on a computer with no stored GitHub sign-in.
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Live build\Plugin family plan.md
[857] Before every update the page's server is stopped completely and restarted first, then confirmed running.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[858] The owner's PC reads the plugin from its local copy so he tries changes first; other users install from GitHub.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[859] A new process is tried on one project first and spread only after the owner says it works.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[860] Fixes are saved in the plugin's history and copied into the copy the PC runs from, compared file by file.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[861] Everything a helper reports merged is verified in the merged copy, since a change put only in the built page is lost on rebuild.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[862] The 15-minute pass can be turned off at the owner's request and stays off until he says otherwise.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[863] The program is not changed in the middle of a running rebuild week; changes go in between weeks.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[864] After the open jobs and the owner's checks, what is left is the GitHub push and the manual rewrite.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[865] Related finished changes are installed together so the page restarts only once.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[866] A piece that fails its own tests is held back instead of holding up the rest of the release.
  Sources: Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl
[867] A change to every card's buttons is not installed while the owner sleeps, even with the standing run-the-update order.
  Sources: Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl
[868] Republishing the roadmap page runs only on the owner's yes.
  Sources: Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl
[869] Design work and design notes go to the system maintenance coordinator to build; the design session only designs.
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Looks design.md; Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl; Transcript a5369da4-55f9-4fbd-bffa-82b66f0eaf82.jsonl
[870] Each helper builds on its own light copy of the plugin, and the maintainer merges the pieces
  Sources: Roadmap page row steps/item-appearance-preview; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl
[872] A standing manual keeper gets every finished change and rechecks the whole manual against the plugin, including before each push.
  Sources: Roadmap page row steps/step-20; C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\parallel-by-default.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[873] Only the coordinator can allow one exception to the test limits; a helper that needs a full run or real data asks and waits.
  Sources: Plugin repo, branch main: .claude/hooks/test_limits.py
[874] Helper instructions quote Kevin's own words as the spec instead of a rewritten design.
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\build-what-he-says.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[875] The builder works in cloud sessions that cannot reach Kevin's computer or his code-hosting settings.
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\independent-check-loop.md; Transcript 406e11e6-359c-419a-8907-356f68f12ed7.jsonl
[876] The main coordinating session only plans, decides, briefs and reports, stays free to talk, and hands all work to helpers.
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\office-tower-work-in-sessions.md; C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\planner-coordinates-only.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl
[877] Changes to the roadmap plugin's own files are made by a helper session opened in that plugin's folder, directed by the builder.
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\roadmap-plugin-changes-via-helper.md
[878] Independent pieces of work start at once on parallel helpers, one piece each, rather than waiting in a queue.
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\parallel-by-default.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[879] The maintainer only merges, checks and syncs; all building and fixing goes to helpers.
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\parallel-by-default.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[880] Every builder touches only its own files, saves no versions, switches nothing, sends nothing and labels anything unverified.
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Live build\Plan.md
[881] Work on the guardrail rule book is split into lanes: rule data and checks, the guard that runs before each tool use, the change and undo commands, and the page.
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Plugin build\RULEBOOK.md
[883] The maintainer stops after each job so new messages can reach it.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[884] Long-running helper tests are watched so a crawling test is noticed instead of waited on.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[885] Idle helper sessions whose work is merged are archived.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[886] Test servers left running by helpers are stopped only after confirming whether they block anything.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[887] The maintainer works an agreed queue in order and a helper that skips ahead is sent back to it.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[888] Jobs that would edit the same lines go to one helper so they do not collide.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[889] Several independent auditors get the same short brief to audit a plan against the existing system before building.
  Sources: Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl; C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\self-improving-talk.md
[890] A side session cannot change the page and passes faults on in the owner's words to the page's maintenance coordinator.
  Sources: Transcript e2838c2b-da94-4603-90a3-1df6d18e58f3.jsonl
[891] Browser trials are run by one session at a time because a screenshot only works on the front tab.
  Sources: Transcript a5369da4-55f9-4fbd-bffa-82b66f0eaf82.jsonl
[893] New looks are tried on the real page in a separate browser tab, in light and dark, without pressing or saving anything.
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Looks design.md
[896] A check reads the code, without running it, to catch a call to a renamed or removed part of the engine before the owner presses a button.
  Sources: Plugin repo, branch main: tests/engine_names_acceptance.py
[898] An independent agent compares the coordinator's requirement list with the list from Kevin's own words and lists every difference.
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\independent-check-loop.md
[900] After a gathering pass, confirm it ended cleanly and the error log is unchanged.
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\run-passes-on-demand.md
[901] After an install or change, confirm it landed: the changed files match the new build, the page answers, and the expected settings are present.
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Session brief - lock and install.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript e2838c2b-da94-4603-90a3-1df6d18e58f3.jsonl
[903] The questions file is judged working when questions stay numbered, answers are echoed and removed, new sessions see open questions first, and nothing is lost after a week.
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Possible additions\The questions file.md
[905] Audit findings are labeled counted, read or unverified, and a second, newer source is tried with its result stated.
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Live build\Assistant design review.md
[906] A change counts as done only once it is proven on the owner's real page or computer; a stand-in test alone is rejected and unproven items stay listed as open.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl
[907] Helpers working on the texts or team chat parts build from the layout of Kevin's real open browser tab, read but not touched.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[909] A test-view check on the live page was to replace a built-in live check and the end-of-turn roadmap check; all were dropped.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[911] After a speed fix is installed, the next 15-minute pass is watched to make sure the page stays quick.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[912] Before a push or merge, and before publishing a test page, a search removes personal names, addresses, supplier names and purchase data, and this check must never fail silently.
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Plugin build\manual\checks.md
[913] The coordinator reads the original source itself instead of relying on a helper's summary.
  Sources: Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl
[915] A separate session pulls Kevin's requests from his raw conversations, quoting him, and he approves the list as the spec.
  Sources: Transcript 406e11e6-359c-419a-8907-356f68f12ed7.jsonl
[916] Every failure and every correction from Kevin becomes a new spec line and a new test.
  Sources: Transcript 406e11e6-359c-419a-8907-356f68f12ed7.jsonl
[918] Numbered, testable acceptance criteria are written before anything is built.
  Sources: Transcript 406e11e6-359c-419a-8907-356f68f12ed7.jsonl
[919] A health check inventory only reads and changes nothing.
  Sources: Transcript e8565bec-492b-4c84-9d5f-04c83982e7a9.jsonl
[920] After sending a correction to the coordinator, check the result once it reports the build.
  Sources: Transcript a5369da4-55f9-4fbd-bffa-82b66f0eaf82.jsonl
[921] Produced pages are rendered as images and looked at before they are sent.
  Sources: Transcript e09c6623-0e37-46ec-9cd5-2c67be8674ee.jsonl
[922] Reports say which items the coordinator checked itself and which a helper read.
  Sources: Transcript b6dc3d79-6ff8-40ac-b407-0e53b635b1fe.jsonl
[923] While he is on his phone, every open question is written in full in chat
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\phone-questions-in-chat.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[924] Direct questions get short plain answers, a numbered yes or no each, explanation only if asked
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\simple-answer-first.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[925] Estimates are short, unpadded and labeled as estimates in the same sentence
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\time-estimates-run-long.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl; Transcript b608ebf4-334a-464e-8cae-b9d7a3ca2fb5.jsonl
[926] A session ends with a plain report of each step done or not, the version pushed, counts, and anything unchecked
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Session brief - lock and install.md
[928] A design review lets every item be answered by number with yes, no or later, ranks a top ten, and holds unchecked findings as unverified
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Live build\Assistant design review.md
[929] Nothing is said to have started until it is seen to start, and a handoff is confirmed received
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[930] Say plainly which checks were done for real and which were not tried, such as a phone layout, a real send or a real dictation
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript e2838c2b-da94-4603-90a3-1df6d18e58f3.jsonl
[931] Any extra effect beyond what he approved is disclosed in the report
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[932] Confidence is stated honestly: guesses are labeled as inferences and answers from memory are said to be so
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript e2838c2b-da94-4603-90a3-1df6d18e58f3.jsonl; Transcript b608ebf4-334a-464e-8cae-b9d7a3ca2fb5.jsonl; Transcript b6dc3d79-6ff8-40ac-b407-0e53b635b1fe.jsonl
[933] His numbered answers are echoed in one line saying how each was read, inviting correction
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[934] When a file cannot be checked directly, say the answer relies on his screen
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[935] Corrections to earlier claims are stated openly
  Sources: Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl
[936] Only one question list is kept open at a time
  Sources: Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl
[937] Say which source an answer rests on, what was not opened, and when no independent review was found
  Sources: Transcript 406e11e6-359c-419a-8907-356f68f12ed7.jsonl; Transcript a5369da4-55f9-4fbd-bffa-82b66f0eaf82.jsonl; Transcript b385582f-ee9f-4657-ba36-285cea471c9c.jsonl; Transcript b6dc3d79-6ff8-40ac-b407-0e53b635b1fe.jsonl
[940] Each roadmap row title is the page's own name for that part, a colon, then the result, never the problem
  Sources: Roadmap page row steps/item-roadmap-title-rule; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[941] The approved row-naming sentence appears once each in the three sets of roadmap instructions
  Sources: Roadmap page row steps/item-roadmap-title-rule
[942] Only the project's main session changes the roadmap; helpers never write it
  Sources: Roadmap page row steps/step-24; Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl
[943] The separate roadmap writer session is replaced by the main session writing the roadmap itself, switched one project at a time after a trial
  Sources: Roadmap page row steps/step-24; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[944] Every release moves each roadmap row it touched to its true status that same turn
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\roadmap-only-live-truth.md; Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl
[945] Before reporting where things stand, walk every open roadmap row against what is really built and installed
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\roadmap-only-live-truth.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[946] A decision with choices for him goes on the roadmap as a question, not only in chat
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\roadmap-plugin-changes-via-helper.md
[947] Before ending a turn, check the roadmap for anything he asked for that is neither being worked on nor waiting on a question
  Sources: C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\start-what-kevin-asks.md
[948] A helper that runs all the time is not a roadmap row of work in progress
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[949] His check results are recorded on the roadmap, a fully confirmed row is marked Done, and a reply goes in the comment thread
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[950] The roadmap's What's next part is refreshed to show what is being fixed, what is next and what waits on him
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[951] Roadmap rows carry the real clock time, and wrong times are corrected
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript a1bd9e09-49c2-47a3-8be3-cb3a8df31b75.jsonl
[952] The roadmap page is republished to the same link when the plugin changes
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[953] Before writing anything down, quote his exact words and record only what he actually decided
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[954] Each check tests one thing and says what to open, what to do and what should be seen
  Sources: Transcript a1bd9e09-49c2-47a3-8be3-cb3a8df31b75.jsonl
[955] The writer never uses a status that is not one of the page's statuses
  Sources: Transcript a1bd9e09-49c2-47a3-8be3-cb3a8df31b75.jsonl
[956] Inserting a row renumbers the later steps but row ids never change
  Sources: Transcript a1bd9e09-49c2-47a3-8be3-cb3a8df31b75.jsonl
[957] The writer never writes his Works or Doesn't work marks or notes, which are his own
  Sources: Transcript a1bd9e09-49c2-47a3-8be3-cb3a8df31b75.jsonl
[958] The writer does not fill in missing parts of a check itself
  Sources: Transcript a1bd9e09-49c2-47a3-8be3-cb3a8df31b75.jsonl
[959] Only the roadmap page itself is kept up to date since no other program reads a copy
  Sources: Transcript a1bd9e09-49c2-47a3-8be3-cb3a8df31b75.jsonl
[960] Out-of-date text on the roadmap is pointed out but left until new wording arrives
  Sources: Transcript a1bd9e09-49c2-47a3-8be3-cb3a8df31b75.jsonl
[961] The roadmap writer does not track open questions beyond the page's own questions
  Sources: Transcript a1bd9e09-49c2-47a3-8be3-cb3a8df31b75.jsonl
[962] Adding a roadmap row is the owner's decision, not the writer's
  Sources: Transcript a1bd9e09-49c2-47a3-8be3-cb3a8df31b75.jsonl
[963] A missed helper report is written as soon as the writer notices
  Sources: Transcript a1bd9e09-49c2-47a3-8be3-cb3a8df31b75.jsonl
[964] Built work sits on its own branch, not merged, pushed or installed until it is released
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\RSI plan.md; Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl
[966] A lock makes refreshes of the plugin's working copy take turns, and a copy missing a core file is remade
  Sources: Roadmap page row steps/step-48
[967] The release repository is its own new folder filled only by the release step, never his workspace folder
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\Live build\Plugin family plan.md
[968] Cleaning history rewrites only unpushed steps, keeps a backup on the PC and pushes only on his yes
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[970] The running assistant code had no version history, and putting it under version history needs his yes
  Sources: Transcript e8565bec-492b-4c84-9d5f-04c83982e7a9.jsonl
[973] Tests and examples use only made-up people, addresses, companies and events, never anything copied from real data.
  Sources: Roadmap page row steps/item-voice-guide; Roadmap page row steps/step-58; Plugin repo, branch main: docs/changes.md; C:\Users\kgunn\.claude\projects\C--Users-kgunn-Documents-ClaudeOS\memory\helper-tests-made-up-data.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript e09c6623-0e37-46ec-9cd5-2c67be8674ee.jsonl
[974] Any copy, opening or reading of the owner's real database is refused.
  Sources: Plugin repo, branch main: .claude/hooks/test_limits.py
[976] No real test emails are sent to try out a send fix.
  Sources: Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl
[977] Checking helpers never sign in to the owner's real page and send nothing.
  Sources: Transcript a1722239-84ee-4740-b744-e7afb69923c2.jsonl
[978] The weekly usage pace rule is set aside for this one build
  Sources: C:\Users\kgunn\Documents\ClaudeOS\Assistant\Development\RSI plan.md
[979] Learning runs are capped at 30 a day, apart from the owner's daily limit
  Sources: Roadmap page row steps/item-self-improving
[980] During the rebuild, cards are written on a cheaper model while sorting stays on the strongest model
  Sources: Plugin repo, branch main: docs/changes.md; Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[981] Work stops when weekly usage reaches its limit and resumes on the new week; usage is checked before every new step
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl; Transcript cf834cd0-839f-4ac7-ba3b-d8c3e89410a3.jsonl
[982] A hard diagnosis of a core step goes to a dedicated helper on the strongest model that only reads logs and data
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
[983] A session cannot change its own effort setting; he does it
  Sources: Transcript 764e6b6e-16fb-490c-b977-d181a55089a6.jsonl
