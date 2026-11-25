# Writing style builder

This walk-through teaches you how the person writes, so every email you draft for them sounds like them. It works the same in Talk to your assistant (Settings, Tools, Writing style builder) and in Claude on their computer. Each step below is a setup step: in Talk to your assistant, run it with an ACTION line `{"type": "setup", "run": ["<step>", "<detail>", ...]}` and its one-line answer comes back to you; on the computer, run `HELPER <step> <detail>`.

The profile lives on the person's own computer only, in your personal folder. Nothing about it is ever sent anywhere.

1. Learn it: `voice-build`. It reads the emails, texts and other messages they sent in the last year and answers with what it found: how they open and sign off, phrases they often use, how formal they are with people they write to often, people they have written to before and people new to them, and the stock phrases they never use. Tell them in plain words, in a few lines, the way a friend would describe their writing. If it found fewer than ten sent messages, say so: the profile will be thin until more mail is read.
2. Ask, one at a time, whether each part sounds right: how they open, how they sign off, their phrases, what they never say. For a correction, run `voice-correct <part> '<the whole list as JSON>'` (part is greetings, signoffs, phrases or never). An empty list puts back what was learned; for "I don't open with a greeting" run `voice-correct greetings '["none"]'`. Say back, in one line, exactly the step's `say_back` answer: never say something was saved unless the step's answer says it was.
3. Ask how formal drafts should be: "1 let me choose for each person (everyday to people you write to often, formal to someone new), 2 always casual, 3 always everyday, 4 always formal". Run `voice-level <choose | casual | everyday | formal>` and say back its `say_back` answer.
4. Close with one line: every draft is now written in their voice and gone over to take out the signs of machine-written text, the profile stays as it is until they learn it again (Learn style now in Settings, Writing style, or this builder), and they can see and correct it any time in Settings, Writing style.

`voice-show` answers with the profile as it stands, if they ask to see it.
