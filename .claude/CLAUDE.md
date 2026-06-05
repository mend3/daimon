# Project Memory Policy

Long-term context lives in three files under `.claude/`. Review them at session
start and keep them current.

- **MEMORY.md** — durable project knowledge (architecture, standards, constraints).
  The current truth of the project. Not a log, task list, or changelog.
- **DECISIONS.md** — ADRs: major decisions that stay relevant long-term.
- **SESSION.md** — ephemeral working context for the active session. Safe to reset.

## Updating

Update MEMORY.md / DECISIONS.md after durable changes: new architectural patterns,
business rules, conventions, integration behaviors, constraints, or standards.
Skip temporary experiments, one-off discussions, open questions, and routine code
changes — those belong in SESSION.md or nowhere.

Replace obsolete information instead of appending corrections. Keep every entry
concise, actionable, non-redundant, and fact-based. When unsure, exclude.

Writing follows the `documentation-minimalism` skill.
