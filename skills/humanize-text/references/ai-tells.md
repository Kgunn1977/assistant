# Catalogue of AI-writing signs

Adapted from Wikipedia:Signs of AI writing (WP:AISIGNS), an advice page from WikiProject AI Cleanup. This is a field guide of writing/formatting conventions typical of AI chatbots. Use it to locate and name the specific tell you're rewriting.

Important framing from the source:
- This is **descriptive, not prescriptive** — a list of observations, not rules.
- **Not all text with these features is AI-generated.** LLMs are trained on human writing, so these patterns appear in editorials, blogs, marketing, and fan fiction too.
- Each pattern is a **potential sign**, not proof. The value is in the *cluster*: many tells, many times, in post-2022 text.
- **AI-detection tools (e.g. GPTZero) are unreliable** — don't depend on them.

## Table of contents
1. Content
2. Language and grammar
3. Style
4. Consistency / miscellaneous
5. Indicators specific to comments and discussion

---

## 1. Content

LLMs predict the statistically likely next token, so they "regress to the mean": specific, unusual, nuanced facts (statistically rare) get replaced by generic, positive, important-sounding descriptions (statistically common). "Inventor of the first train-coupling device" becomes "a revolutionary titan of industry." This is the root cause of most content-level tells.

**Undue emphasis on significance, legacy, and broader trends.** The text repeatedly asserts how important, influential, enduring, or far-reaching the subject is, rather than just stating facts. It connects the subject to grand themes ("broader movements", "lasting legacy", "shaping generations").

**Canned emphasis on notability, attribution, and media coverage.** The text tries to *prove* the subject is notable by hammering claims of notability — listing the kinds of sources it appeared in (trade publications, regional/national media), echoing the wording of notability guidelines ("independent coverage"), or attributing its own shallow analysis to those sources.

**Superficial analyses.** Shallow commentary about significance/recognition/impact, often via a trailing present-participle ("-ing") phrase at sentence end: "..., highlighting its role", "..., reflecting broader trends." With retrieval-augmented models these may be falsely pinned to a named source regardless of whether the source supports them.

**Promotional and advertisement-like language.** Even when asked for a neutral tone, output drifts toward marketing or travel-guide prose. Subtypes:
- *Cultural-heritage inflation*: constantly reminding the reader of a subject's importance/heritage ("rich cultural heritage", "vibrant", "fascinating glimpse").
- *Brochure framing*: "nestled in the heart of", "must-visit", "gateway to", "seamless".
- Older models (e.g. GPT-4) are more blatantly superlative ("the best"); newer ones are more subtly positive.

**Vague attributions and overgeneralization of opinions.** Weasel wording — attributing claims/opinions to an unnamed authority: "experts argue", "observers note", "it is widely regarded", "researchers and conservationists are interested."

**Outline-like conclusions about challenges and future prospects.** Articles end on a rigid template: a "Challenges" beat followed by "Future Outlook" / "Future Prospects" / "Challenges and Legacy." The tell is the formulaic scaffold, not the mere mention of challenges.

**Leads treating list/broad titles as proper nouns.** In articles whose title is not a proper name (e.g. a list), the first sentence defines the title as if it were a standalone real-world entity, unnaturally.

---

## 2. Language and grammar

LLM text shows consistent syntactic/word-choice patterns regardless of subject, giving it an identifiable "voice." (Some models vary more than others; GPT-4o produced more syntactic variation than peers.)

**High density of "AI vocabulary".** Studies show LLMs overuse a specific set of words, which spiked in text after 2022 and tend to co-occur. One or two may be coincidence; many, repeatedly, in post-2022 text is one of the strongest single tells. The exact set shifts by model and over time (e.g. "delve" peaked in 2023–early 2024, then fell off). See `word-lists.md` for the words, era breakdown, and phrase lists.

**Avoidance of basic copulatives ("is"/"are").** LLMs replace plain "is/are" with "serves as a", "stands as", "marks", "represents", and prefer marketing verbs ("features", "offers", "boasts") over neutral "has". A documented >10% drop in "is/are" in academic writing appeared in 2023. In leads, they may write "refers to" as if the article were about the term rather than the subject. (Exception: "has" as a past-participle auxiliary is normal.)

**Negative parallelisms.** Constructions that set up a contrast as if correcting a misconception:
- *Not just X, but also Y* — "Not only ... but ...", "It's not just ..., it's ..."
- *Not X, but Y* — "It's not ..., it's ...", "no ..., no ..., just ..." (states the subject lacks the first trait entirely).
Common in human "myth-busting" listicles too, but stereotypically an AI sign.

**Rule of three.** Overuse of triples: "adjective, adjective, adjective" or "short phrase, short phrase, and short phrase." Often used to make a shallow analysis feel comprehensive.

**Lexical diversity / elegant variation.** A repetition penalty pushes models to avoid reusing a word, cycling through synonyms even where plain repetition would read better. (Caveat: if separate AI passages were generated in isolation, this may not show.)

---

## 3. Style

**Title case** in section headings — capitalizing all main words.

**Overuse of boldface.** Mechanical, excessive bolding for emphasis — often "key takeaways" style, bolding every instance of a chosen term. Inherited from readmes, fan wikis, how-tos, sales pitches, slide decks, listicles. (Some newer models have been instructed to suppress this.)

**Inline-header vertical lists.** Lists where each item is a bolded inline header + colon + description. Bullets may render as raw characters (•, -, –, #, emoji) and numbered lists as literal "1." instead of proper markup; copy-pasting can lose formatting and line breaks.

**Overuse of em dashes.** LLMs use em dashes (—) more than nonprofessional human writing of the same genre, often in a formulaic, "punched-up" sales-like way, where humans would use commas, parentheses, colons, or hyphens. Best used as a tell in combination with others; more common on discussion pages than article text. (Some newer models, e.g. GPT-5.1, were tuned to suppress them.)

**Unusual use of tables.** Occasionally creating small unnecessary tables for content better expressed as prose or an infobox.

**Curly quotation marks and apostrophes.** ChatGPT and DeepSeek often emit curly quotes (" " ' ') instead of straight ones, sometimes mixing both inconsistently. NOT proof on its own: Chicago style, MS Word/macOS "smart quotes", grammar tools, and major newspapers all produce curly quotes legitimately.

**Skipping heading levels.** Jumping heading levels (e.g. straight to a lower level, skipping level 2).

**Thematic breaks before headings.** Inserting a horizontal rule before headings as a matter of habit.

---

## 4. Consistency / miscellaneous

**Pronounced shift in writing style.** When only part of a document is AI-generated, that section reads as a tonal/rhythmic seam against the human-written rest.

Other source-listed miscellaneous signs (mostly Wikipedia-workflow-specific, less relevant to general prose): overwhelmingly exhaustive edit summaries; "submission statements" in drafts; pre-placed maintenance templates; permissions gaming; broken wikitext and reference-markup bugs (e.g. stray "contentReference", "oaicite", "turn0search0" artifacts); fabricated/placeholder citations, invalid DOIs/ISBNs, and book citations lacking page numbers.

---

## 5. Indicators specific to comments and discussion

In discussion/comment contexts, additional AI tells include canned emphasis on quality, good faith, and adherence to policies/guidelines, and the same negative-parallelism and rule-of-three habits showing up in argumentation. Em dashes are especially common here. Treat these the same way: reduce the cluster, restore a plainer, more direct voice.

---

## Note on use

When humanizing, fix the **underlying habit** (inflation, formula, hedge, mechanical formatting), not merely the surface vocabulary. Simply swapping flagged words for synonyms leaves the structure intact and can make the text harder to read without making it more human. And never trade truthfulness for naturalness — cut an unsupported claim rather than inventing a concrete-sounding replacement.
