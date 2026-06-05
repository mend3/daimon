---
name: documentation-minimalism
description: Minimalist editor for comments and documentation. Use when writing or reviewing code comments, docblocks, READMEs, ADRs, or any markdown — to cut bloat, redundancy, "X not Y" negative guidance, code-restating comments, and defensive notes, and to keep tutorials/setup/operational content out of source files. Favors intent over mechanics and the shorter version when clarity is equal.
---

# Documentation Minimalism

Reduce documentation entropy while preserving useful knowledge. Every sentence
carries a maintenance cost; when two versions are equally clear, keep the shorter.

## Document only

WHAT exists · WHY it exists · WHEN to use it · real constraints, assumptions, and
tradeoffs.

## Cut on sight

- **Negative guidance** — "use X instead of Y", "do not / never use Y", "unlike Y",
  "previously we used Y". Document the chosen approach, not the discarded ones.
  Keep a rejected alternative only when it is essential to understanding the system.
- **Code-restating comments** — `// increment counter`, `// check if user exists`.
- **Defensive notes** aimed at future / AI / junior mistakes — `// do not replace
  with Promise.all`. State the underlying constraint instead.
- **History in source** — migration notes, decision logs, "temporary" rationale.
- **Bloated docblocks** — long paragraphs, step-by-step narratives, implementation
  stories.

## Intent over mechanics

Code shows HOW; comments explain WHY.

```ts
// Bad
// Sort by created_at descending
// Good
// Most recent records must be processed first.
items.sort(...)
```

```bash
# Bad — documents the discarded option and a fix-it warning
# Use the cask, NOT the formula. The formula lacks Metal support.
# Good — documents the chosen approach and its purpose
# Install the desktop app to enable Metal acceleration.
brew install --cask ollama-app
```

```ts
// Bad — defensive
// IMPORTANT: do not replace this with Promise.all
// Good — the actual constraint
// Sequential execution prevents API rate-limit bursts.
```

## Source vs. markdown

Source files are not documentation repositories.

- **Source comments:** short intent, invariants, API contracts, non-obvious
  behavior or side effects, architectural notes tied to the implementation.
- **Markdown:** guides, onboarding, architecture overviews, operational procedures,
  ADRs, rationale, workflows.

Test: if the content still makes sense outside the source file, it belongs in
markdown, not a comment.

## Comment justification test

A comment survives only if it passes all four:

1. It cannot be understood from the code alone.
2. It cannot be replaced by better naming.
3. It does not belong in markdown instead.
4. It explains intent, not mechanics.

Fail any → remove it or relocate it.

## When reviewing

Act as a documentation minimalist editor:

- aggressively remove redundancy and collapse verbose explanations
- relocate misplaced content — docs out of source, implementation detail out of markdown
- prefer concise, intent-focused wording
- reject "X instead of Y" phrasing unless strictly necessary
- optimize for long-term maintainability
