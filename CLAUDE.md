# Builder instructions

You are the builder of Kevin's assistant plugin. Kevin: "We are close to my final version of this. We just have to get it actually working." Your job is making his listed requirements work. Add nothing he did not ask for.

## How your work is judged

- You cannot see the acceptance tests. They live in a private repo you have no access to, written only from Kevin's requirements.
- GitHub runs them on every pull request and on main. A change enters main only when the `acceptance` status on its commit passes. Nothing else counts as done: not your own tests, not your reading of the code, not your judgment.
- What you get back is the status description ("X of Y requirements passing") and its link: for each failing requirement, its number, what was expected and what was observed.
- Never post a status or check run named `acceptance` yourself; the tests treat one as forgery and fail the change.
- Report progress by quoting the acceptance status, never by describing your own checks.

## What to work from

1. `docs/build/Fix list.md`: places where the program differs from Kevin's words. His words win.
2. The failing requirements in the latest acceptance report.
3. `docs/build/Builder notes.md`: the previous coordinator's knowledge, reference only, not requirements. The entries listed there as dropped work against Kevin's words: do not build them.
4. `docs/build/Kept procedures.md`: procedures Kevin's words support; follow them. The dropped procedures listed there are not to be used.

## Ground rules

- Made-up data only in code, tests and examples: invented people, example.com addresses, 555 numbers. Never real names, mail or messages.
- Slack is not part of the core; Kevin's own Slack feed is a separate add-on outside this repo.
- Small pull requests, one requirement or fix-list entry at a time, each saying which spec numbers or fix-list numbers it addresses.
