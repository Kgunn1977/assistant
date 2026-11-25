---
name: questions
description: How a session that keeps its own questions file asks the person questions and takes their answers - every question in discussion written into the file first, numbered from 1 oldest first, choices lettered, renumbered at every edit, answers echoed in one line. Use in a session where /assistant:questions-setup turned the questions file on, whenever a question is put to the person or they answer one.
---

# The questions file

A session that turned this on has its own questions file at the top of the project's folder: `Questions.md` for the first session, `Questions - <session title>.md` for each further one. It holds only the questions raised in that session that are open, oldest first. Other sessions in the project, including forks and sessions started from this one, do not share it. The person reads it in the side panel beside the chat and answers in chat. It keeps questions from scrolling out of sight and from being answered against the wrong number.

**Two places for questions to the person.** A question raised by the work (while building, or one a helper reports) goes on the roadmap, on the row it is about, and is answered there with a tap. A question raised in conversation with the person goes in this file and is answered in chat. Each question goes in one place, never both. In a project with only one of the two, every question to the person goes there; with neither, it is asked in chat. When you tell the person you put a work question on the roadmap, that is not a question to them in chat, and the file is not where it goes.

## Who writes it

Only the session that ran `/assistant:questions-setup` writes its file, and only its own. A helper, subagent or fork with no file of its own writes none and just asks in chat. The person reads the file and never edits it.

## The file

```
# Questions

Answer in chat by number and letter, for example "1b", or in your own words.

1. <the question, in one or two plain sentences that make sense on their own, with enough background to answer without opening anything else>

    a. <choice>
    b. <choice>

    Recommended: <letter, and one line of why, or "no recommendation">
    Asked: <date>

2. ...
```

The way a numbered question looks in chat: the number and question at the left margin, a blank line, then everything under it indented four spaces. End each indented line with two spaces so the side panel keeps them on separate lines. Only the question line starts at the left margin with a number and a period.

- Lettered choices only where there are real choices. An open-ended question has none and is answered in words.
- No limit on how many are open.
- When nothing is open it says "No open questions." The file is never deleted.
- Edit it in place, never by writing a copy over it. Read the file named in the plugin's note, not another session's.

## The rules

1. A question is written into the file before it is asked. A question put to the person that is only in chat is a fault.
2. Oldest first: number 1 is always the oldest open question, and numbers run 1, 2, 3 with no gaps.
3. Renumber at every edit: when a question is added, answered, withdrawn or reworded.
4. The file changes only during your own turn, never between the person's reading and their answering. Their answer is matched against the file as it stood at the end of your last reply.
5. Every answer is echoed in one line that names the question in words, not by number. Example: "Took 2b as: the scoper and the director are two separate people." That line is the whole reply to an answer, unless the answer asked for more. If an answer could fit more than one question, or fits none, say which reading you took or ask, and never guess silently.
6. When the person answers, in the same turn: the question leaves the file, the decision is recorded wherever the project keeps decisions, and the list is renumbered.
7. A reply that asks for more information is not an answer. The question stays open, is reworded to give what was asked for, and keeps its place by age.
8. A question no longer needed is withdrawn: removed, renumbered, and the person told in one line that it was dropped and why.
9. Questions ask about the outcome the person wants, never about internal mechanisms.
10. Never list the open questions in chat, and never say that an answer was recorded and removed or that the numbers changed. The file in the side panel is the list.

## On the roadmap

In a project with a roadmap, the page shows a copy of this file under "Questions in chat", with this session's name; the person reads it there and answers in chat. At the end of every turn in which the file changed, run as one plain command `python "${CLAUDE_PLUGIN_DATA}/scripts/questions_setup.py" roadmap --file "<this session's file>"`, then make the write it saves in `writes_file` with ArtifactData, exactly as written, and if it prints `full_patch`, run that command after. With no roadmap it says so and changes nothing. Never write the copy yourself.

## The checks

The plugin shows you the open questions on each message and when a session starts or resumes. It holds your reply once, with a plain reason, when the person answered and the file has not changed, or when the reply asks the person a question that is not in the file. Do what it says, then end your reply. It lets go after three holds in a row.
