# Redesign findings: the assistant page (look and navigation only)

Reviewed 2026-11-20 on the live page (Chrome, 1440 px, Calm look, light) and on page 0.1.4 (`main` ebee926) at 375 px and in dark mode, in a local preview with made-up data. Chrome would not go narrower than about 640 px and the live page refuses to load in a frame, so the phone view was taken from the preview.

Plugins: **UR** = UI Design Review `ui-review`. **DC** = Design `design-critique`. **AR** = Design `accessibility-review`. **UC** = Design `ux-copy`.

What it is for: one place where the owner reads and answers his cards, mail and texts. The main job is to see what waits on him and answer it quickly, on a computer or a phone.

Already good: the Calm colours pass contrast (secondary text 6.6:1, faint text 4.9:1, filled buttons 6.3:1, dark mode faint text 6.3:1). Each card has one clear filled recommended button. The chat panels follow the familiar Messages layout. Keyboard focus outlines are styled. Every look is built from tokens (`html[data-look]`), so most fixes are token and layout changes.

## Must fix

1. **The sticky header takes over a third of the screen.** The top block (title, Settings, search, filter) and the stack of section names you have scrolled past are both sticky. On desktop they take up to 260 of 718 px once nine names have stacked. On a phone they take 306 of 812 px. In Texts on a phone, the conversation's own header (name and Back) slides under it, which leaves about 320 px for the chat.
   *Fix:* one compact sticky bar, about 56 px on a phone and 64 px on desktop: a small title, Settings, the search field (on a phone it opens from an icon), and the section index from item 2. Section names you have passed stop stacking. **UR, DC**
2. **The section index is hard to read.** The names you have passed stack in two columns, in 13 px uppercase serif. The right column's rows don't line up with the left's, an empty band appears between them, and the "1 more" / "7 more" label is 11 px.
   *Fix:* one row of jump links (chips) in the sticky bar, each with its count. It scrolls sideways on a phone and highlights the section you are in. The same links open a folded section. **UR, DC**
3. **Each section's close control can't be seen and is easy to press by accident.** The grey line down the left of each section is a 14 px wide button as tall as the section (up to 3,700 px). Nothing shows that it closes the section. On a phone it sits in the 16 px edge where a thumb rests.
   *Fix:* keep the button, but give it a visible hover and focus state, and add a chevron to the section heading (which already toggles). On a phone, make the line a hairline inside the margin. **UR, AR**
4. **Field and card edges are too faint (WCAG 1.4.11).** The search field, mail search, the "Ask or tell" boxes and other fields use `--line` #d9e0d8 on #f3f5f2, which is 1.23:1. Card edges use `--line-soft`, which is 1.09:1.
   *Fix:* a field-border token of at least 3:1 (about #8a988f in light, matched in dark). Give cards a slightly stronger edge as well as the shadow. **AR**
5. **Some touch targets are too small (WCAG 2.5.5).** The pin buttons in the Texts list are 22x22. Each mail row's checkbox and star are about 14 px. "Change how your assistant works" and "Sign out" are links 20 px tall.
   *Fix:* a 44 px hit area through padding, with the icons kept at their current size. **AR, UR**
6. **Settings: Save sits beside Back and then scrolls away, and there is no index.** With the owner's groups open, Settings is 13,000 px long. Save (filled) touches Back, and both leave the screen. The group names are 14 px grey on a grey band, and a closed group has no chevron.
   *Fix:* a sticky Settings bar, with Back on the left and Save (still the main button) on the right, set apart from each other. Add a row of jump links to the 15 groups. Each group gets a real heading and a chevron. All wording stays as it is. **UR, DC**

## Should fix

7. **There is an empty hole in the left column on desktop.** With the left sections folded, the right column (Errors, Today, Ready to send, Handled for you) is taller, which leaves a block of empty page about 400 px tall. Mail and Texts only begin below the right column.
   *Fix:* make the right column a sticky sidebar that scrolls on its own, so the full-width parts follow straight after the left column. the owner's chosen arrangement stays as it is. **DC**
8. **The page is narrow on a wide screen.** The content stops at 1120 px on a 1440 px screen. Mail's folder column then wraps the account name (a long address breaks over two lines).
   *Fix:* let Mail and Texts run to about 1360 px. Keep cards at a comfortable reading width. **DC**
9. **Lettering and counts are mixed.** Headings use the serif, body text uses Inter, and counts use a monospace face. The counts read "22 cards", "22 open", "5" and "55 cards" for the same idea.
   *Fix (style only; the count wording comes from the code):* show counts as small badges in Inter with even-width numbers, and use one heading scale. **DC, UC**
10. **Cards are long.** Every card shows a two-line "Ask or tell the assistant about this card..." box and a heavy 2 px line under its title, so 22 cards make a 3,700 px column.
    *Fix:* show the box at one line until it is focused, replace the title line with spacing, and tighten the gap between cards on desktop. **DC, UR**
11. **Errors show their severity by colour alone (WCAG 1.4.1).** A small red or amber dot is the only difference between them.
    *Fix:* a severity icon and a left accent bar in `--crit` or `--warn`, on a lightly tinted background. **AR, DC**
12. **The Texts controls wrap on a phone.** In Texts, the search field and Search sit on one row, with New text and Refresh on another.
    *Fix:* the search field on its own full row, the buttons together as smaller pills, and the workspace name above the field. **UR**
13. **The Mail toolbar is crowded.** Two pickers, the search field and three buttons share one row on desktop and spread over four rows on a phone.
    *Fix:* filters on the left and actions on the right. On a phone, search comes first at full width, then the two pickers on one row, then the buttons. **UR**
14. **The Texts panel wastes space on a phone.** The panel is a fixed height, and with a short list most of it is blank.
    *Fix:* fit the panel's height to the space under the new compact bar, using `dvh` so the phone's own bars are allowed for. **UR**

## Nice to have

15. In dark Calm, the section lines and the left close lines nearly disappear. Lift `--line` a step. **DC**
16. In the header, the date and time compete with Settings. Make the date quieter and smaller, and put Settings at the right of the sticky bar. **DC**
17. The section notes ("Most urgent first", "Nothing is asked of you") could sit under the heading in faint text, so they stop competing with the counts. **DC**

## Left out (these would change behaviour or wording)

- **UC:** some button wording could be more specific, such as "Other", "Later" and "Not needed". Wording that names a button or setting is fixed, so this is left alone.
- **UC:** the extension error doesn't say what the owner can do about it. The message comes from the engine.
- **UR, AR:** the sign-in page has no styling (default serif, default fields), and at 375 px its field and button run about 600 px wide. It is drawn by the engine (`local_site.py`), so a fix needs the coordinator's agreement.
- **Constraint:** The owner uses the Calm look in light mode. The redesign changes the tokens shared by all six looks plus Calm's own, and the other five looks must keep working (`tests/looks_acceptance.py` covers them).

## What the redesign built (phase 2, on ebee926)

- Built: 1, 2 (one row of jump links with counts; the part you are reading is marked; a shut part's link opens it), 4, 5, 6 (pinned bar; no group index), 8 (Calm reaches 1240 px), 9 (counts only), 11, 12, 13, 14, 15.
- 3, changed from what the finding proposed: the folding lines stay and no arrows are added, because the page was deliberately built to fold without arrows. The lines are lighter until pointed at and narrower at a phone's edge.
- Not built: 7 (closing the empty hole needs the right column moved in the page's structure, beyond a style change), 10, 16, 17, and an index of the Settings groups.
