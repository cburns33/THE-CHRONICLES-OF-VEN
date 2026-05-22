# Chronicles of Ven — What the Tool Does

A plain-English guide to every feature. No tech knowledge needed.

---

## The two ways to use it

**Chronicles of Ven (ChatGPT)**
Your main way in. Open your Custom GPT in ChatGPT and ask a question in plain English. The tool searches your manuscript and campaign documents behind the scenes and gives you an answer with sourced passages. Chase needs to have the server running first — just text him.

**Story Health (browser)**
A separate page Chase can pull up that gives you a visual overview of the manuscript. No question needed — it just shows you the data.

---

## Search features

**Semantic search**
Finds passages by *meaning*, not just exact words. Searching "Ven feels uncertain about his power" will surface relevant scenes even if those exact words never appear. It understands intent.

**Source filter**
You can tell it to search only the novel, only the old campaign documents, only the worldbuilding doc, or everything at once. Useful when you want to check what the *manuscript* says vs. what the *campaign history* says.

**Character and place filter**
Narrow results to scenes involving a specific character or location. You can combine multiple.

**Entity lookup**
Instead of searching by meaning, look up which chapters a specific character or place appears in. Good for "where does Thorn show up across the whole manuscript?"

**Relevance score**
Every result shows a percentage — how confident the system is that this passage matches your question. Higher means it's a stronger match.

**Why this result?**
A small expandable note under each passage. It tells you in plain English why that passage was surfaced — for example: "79% similarity · 1 shared character (Ven) · Novel source." Useful if a result feels surprising.

**More like this**
A button on each passage. Click it and the tool finds other passages that are similar to that one, without needing a new search query.

**Copy as ChatGPT context block**
Copies all the results in a format you can paste directly into a regular ChatGPT conversation if you want to ask follow-up questions outside of Chronicles of Ven.

---

## In Chronicles of Ven (the ChatGPT version)

**Citation keys**
Every passage the GPT draws from gets a label like `[C2-P1]` (Chapter 2, Passage 1). The GPT is instructed to include those labels inline when it answers, so you can see exactly which passage any claim is coming from. If it can't find support in the indexed text, it says so instead of making something up.

---

## Story Health page

**Metrics bar**
Four numbers at the top: total passages indexed, number of chapters, number of characters tracked, and number of timeline events found. A quick health check.

**Character appearances chart**
A stacked bar chart showing the top 10 characters by chapter. You can see at a glance which chapters are heavy with certain characters and which chapters they're absent from.

**Chapter overview table**
A list of every indexed document — novel chapters and continuity docs — with how many passages each one contributed and when it was last indexed.

---

## Things it knows about your world

The tool has been told about terms that look like ordinary English words but mean something specific in your world:

- **Myth** — the God of Secrets and Magic (not the common word)
- **Working / Workings** — a spell or act of magic (not the common verb)

It treats these as proper nouns when searching and categorizing passages.
