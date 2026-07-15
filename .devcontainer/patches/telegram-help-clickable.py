#!/usr/bin/env python3
"""Make Telegram /help command listings clickable.

Hermes renders gateway/skill commands wrapped in backticks (a MarkdownV2 *code*
entity). Telegram only auto-links `/command` as a tappable command when it is
plain text, not inside a code entity — so `/help` lists the commands but they
can't be tapped.

This strips the backticks around slash-command mentions at the single chokepoint
every Telegram help string flows through (`_telegramize_command_mentions` in
gateway/run.py), leaving plain `/command` text that Telegram turns into tappable
commands. Command *names* are still sanitized by the existing logic that runs
right after. The native command menu (set_my_commands) is untouched.

Idempotent: applied by postCreate.sh on every container create, so it survives a
Hermes reinstall. If the target moved or the anchor is missing (Hermes changed
shape), it leaves the file untouched and exits non-zero so postCreate can warn —
the feature is off, but nothing is corrupted.

Exit codes: 0 applied or already present; 2 run.py not found; 3 anchor not found.
"""
import os
import sys

MARKER = "# daimon-patch: clickable command mentions"
ANCHOR = "    return _TELEGRAM_COMMAND_MENTION_RE.sub(_replace, text)\n"
INSERT = (
    "    " + MARKER + " — strip backticks around slash commands so Telegram\n"
    "    # auto-links them as tappable commands (a code entity blocks that).\n"
    '    text = re.sub(r"`(/[a-z][a-z0-9_-]*(?: [^`\\n]*)?)`", r"\\1", text)\n'
)


def main() -> int:
    home = os.path.expanduser("~")
    path = os.path.join(home, ".hermes", "hermes-agent", "gateway", "run.py")
    if not os.path.isfile(path):
        print(f"[patch] run.py not found at {path}; skipping")
        return 2
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        print("[patch] clickable command mentions already applied; skipping")
        return 0
    if ANCHOR not in src:
        print("[patch] anchor not found (Hermes layout changed?); skipping")
        return 3
    src = src.replace(ANCHOR, INSERT + ANCHOR, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("[patch] applied clickable command mentions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
