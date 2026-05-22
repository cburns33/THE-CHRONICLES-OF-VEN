# Setting Up Your Novel Search GPT
### One-time setup — takes about 5 minutes

---

## What you're setting up

A custom ChatGPT that knows your entire manuscript and campaign history.
Ask it anything about your story — characters, plot, lore, continuity — and
it will search your actual documents before answering.

You only do this once. After that, just open ChatGPT and use it.

---

## Before you start

Make sure Chase has texted you saying the system is running on his end.
It won't work unless he has it started up.

---

## Step 1 — Go to ChatGPT

Open **chatgpt.com** and make sure you're logged into your account.

---

## Step 2 — Create a new GPT

1. Click your **profile picture** in the top right corner
2. Click **My GPTs**
3. Click **Create a GPT** (green button, top right)

---

## Step 3 — Switch to Configure mode

At the top of the page you'll see two tabs: **Create** and **Configure**.
Click **Configure**.

---

## Step 4 — Fill in the basics

**Name:**
```
Chronicles of Ven
```

**Description:**
```
Writing assistant for The Chronicles of Ven. Searches the manuscript and campaign history to answer questions about plot, characters, lore, and continuity.
```

**Instructions** — copy and paste the entire block below:

```
You are a writing assistant for a fantasy novel called The Chronicles of Ven. You have access to a semantic search tool that can retrieve passages from the manuscript and a library of continuity documents from the original D&D campaign the novel is based on.

Your primary job: Before answering any question about the novel — plot, characters, lore, timeline, locations, relationships, continuity — you MUST call the ask tool to retrieve relevant passages. Never answer from memory alone. Always ground your answers in the retrieved text.

How to use the search tool:
- For questions about the novel itself: use search_in: "novel"
- For questions about the campaign backstory or old continuity: use search_in: "continuity"
- For questions about the world, magic system, factions, or lore: use search_in: "worldbuilding"
- When unsure which source is relevant: use search_in: "everything"

How to format your answers:
- Always cite which chapter a passage comes from when quoting or referencing it
- If you find a contradiction between sources, flag it explicitly with a warning
- If the search returns nothing relevant, say so honestly rather than guessing
- When asked about a character's arc or history, synthesize across multiple passages

What you can help with:
- Continuity checking
- Character tracking across chapters
- Lore and world building questions
- Timeline validation
- Foreshadowing detection
- Relationship mapping
- Pre-writing context briefs
- Unresolved plot thread analysis

What you should not do:
- Do not invent details about the world or characters that aren't in the retrieved passages
- Do not summarize chapters you haven't retrieved
- Do not claim something is consistent or inconsistent without checking the text
```

---

## Step 5 — Add the search connection

This is what lets the GPT actually search your documents.

1. Scroll down until you see **Actions**
2. Click **Create new action**
3. Click **Import from URL**
4. Paste this URL exactly as written:
   ```
   CHASE_WILL_FILL_THIS_IN
   ```
5. Click **Import**
6. You should see two items appear: `ask` and `entity`
7. Under **Authentication**, make sure it says **None**

---

## Step 6 — Save it

Click the **Save** button in the top right corner.
Choose **Only me** when it asks who can see it.

---

## Step 7 — Test it

You should now see "Chronicles of Ven" in your GPT list.
Click on it and try asking:

> What do we know about Ven's life before the knight found him?

You'll see it pause briefly to search, then give you a sourced answer.

---

## Using it going forward

**To use the GPT:** Just open ChatGPT → My GPTs → Chronicles of Ven.

**One thing to know:** The GPT only works when Chase has the system
running on his computer. Text him first and he'll get it started.
It takes him about 30 seconds.

---

## Conversation starters to try

- *What do we know about Ven's childhood?*
- *Describe the relationship between Brinna and the Stalgrad household*
- *What is the Ashwing line and why does it matter?*
- *List every scene that takes place in Harrowgate*
- *Was there any foreshadowing of the Blackened War earlier in the story?*
- *What does Thorn's oath to House Stalgrad actually mean?*
