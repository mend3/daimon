---
name: feeds-digest
description: Poll the user's subscribed feeds, keep what matters, and send a short, themed digest.
version: 1.0.0
metadata:
  hermes:
    tags: [feeds, digest, proactive]
    category: knowledge
---
# Feeds digest

Run this on a schedule (a cron job delivering to the user) to surface new reading
that's actually worth their time.

1. Run `ella-kb poll feeds` from the shell. It pulls new feed items, keeps the
   relevant ones (by the user's interests), saves them to memory, and prints the
   titles it saved.
2. If nothing new was saved, send a single short line ("Nothing new worth flagging
   today.") — or stay silent if the schedule prefers quiet.
3. Otherwise write a brief digest of what you saved: group related items under a
   theme, one line each with why it might matter, and include the link. Lead with
   the one thing most worth their attention. Keep it warm and skimmable — a friend
   flagging good reading, not a newsletter.

The saved items are also in long-term memory, so the user can later ask you to
recall them.

To set this up, the user creates a cron job once, e.g.:
`hermes cron create "every 1d at 08:30" "Send me my feeds digest" --skill feeds-digest --deliver telegram --name feeds-digest`
