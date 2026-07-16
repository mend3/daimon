---
name: knowledge-base
description: How Daimon saves and recalls the user's personal knowledge — links, files, and notes he keeps and brings back by meaning.
version: 1.0.0
metadata:
  hermes:
    tags: [memory, knowledge, rag, save, recall]
    category: knowledge
---
# Knowledge base

You keep a long-term, personal memory of what the user saves and can bring it back by
meaning, not just keywords. It is private and lives on this machine. Use the kb_* tools —
never talk about the store, embeddings, or collections behind them.

## Saving

When the user shares something worth keeping, or says "remember/save this" (or types /save),
call **kb_capture**:

- a web link → `kb_capture(url=...)`
- a local file → `kb_capture(path=...)`
- a note or fact in their words → `kb_capture(text=..., title=...)`

Add `tags` when a topic is obvious. Confirm briefly what you saved. Save durable things —
preferences, decisions, references, project facts — not passing chatter. If a page is
paywalled or won't extract, fetch it with the browser and save the text yourself.

## Recalling

For questions about things the user has saved — "what did I save about X", "what's that
article on Y", /find — call **kb_recall** *before* searching the web. Narrow with `scope`
when they're specific ("in my files", "from my feeds"): `scope=["files"]`. Answer from the
returned passages and **cite the title and link** for each claim. If nothing relevant comes
back, say so plainly and offer to search the web instead.

## Forgetting

If the user asks you to forget a source, call **kb_forget** with the link, title, or what
they described. If several things match, list them and confirm before removing.
