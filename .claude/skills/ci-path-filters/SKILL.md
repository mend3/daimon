---
name: ci-path-filters
description: Scope CI workflows to the files they actually check. Use when creating or editing a GitHub Actions (or other CI) workflow — add path filters so a job only runs when files it analyzes change, instead of on every push/PR.
---

# CI path filters

A CI job should run only when a file it checks changes. A lint or test job that
fires on every push wastes minutes and adds noise to the status list.

## Rule

Derive the trigger paths from what the job's steps actually read, and list them
on both `push` and `pull_request`. Include the workflow file and its config files
so editing them re-runs the checks.

```yaml
on:
  push:
    branches: [main]
    paths: &paths
      - '**.sh'                 # shellcheck
      - '**.yml'                # yamllint
      - '**.yaml'
      - '.yamllint'             # the linter's own config
      - 'path/to/dashboards/*.json'   # the json a step validates
  pull_request:
    paths: *paths
```

(GitHub Actions supports YAML anchors; if you avoid them, duplicate the list.)

## Map steps to paths

For each step, add the globs it touches:
- `shellcheck $(git ls-files '*.sh')` → `**.sh`
- `yamllint .` → `**.yml`, `**.yaml`, `.yamllint`
- a JSON/JSON-schema check → that file or its directory
- a unit-test job → the source + test dirs it covers

Prefer an explicit allowlist of what the job checks over `paths-ignore`
exclusions, which silently let new file types through unchecked.

## Caveats

- **Required checks:** a path-filtered job that is skipped stays absent, and a
  branch rule requiring it will block the PR forever. Either don't mark it
  required, or add a tiny always-runs job that the rule requires instead.
- `paths` filters apply to `push`/`pull_request` only — not to `schedule`,
  `workflow_dispatch`, or `release`.

## Other CI systems

Same principle, different syntax: GitLab `rules: changes:`, CircleCI's
path-filtering orb, Bitbucket `condition.changesets.includePaths`.
