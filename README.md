# test-triage-agent

A Claude agent that reads a failed test run and says why it failed: **product bug**, **test bug**,
**flaky** or **environment**, with root cause, suspect commit and confidence.

> Work in progress. Built in public over one week.

## Plan

- [x] Sample app with a seeded pytest + Playwright suite and a labeled set of 40+ failures
- [ ] MCP server: failed tests, test logs, recent commits, similar past failures
- [ ] Agent on the Claude API returning structured triage
- [ ] Eval suite as a CI release gate: category accuracy, suspect-commit hit rate, cost, latency
- [ ] FastAPI backend + Next.js UI
- [ ] Deployed on AWS with Terraform

## Dataset

`cases/` holds 43 labeled failures of `sample_app/` (a FastAPI orders service with a pytest +
Playwright suite): 14 product bugs, 12 test bugs, 9 flaky and 9 environment failures.

Each `cases/case-NNN/` is what a CI job would leave behind:

| File | Contents |
| --- | --- |
| `junit.xml` | JUnit report of the failing run (absent when pytest stopped before collecting) |
| `run.log` | pytest console output |
| `commits.json` | commits since the last good build, newest first, with diffs |
| `rerun.json` | which tests failed when the suite was run again |

`cases/labels.jsonl` is the answer key: category, root cause, suspect commit (null for
environment failures) and failing tests.

Every label is true by construction. `dataset/generate.py` builds each case as a git history
with 2–4 unrelated commits plus the culprit from `dataset/catalog.py`, then checks it: bugs must
fail the same way twice, and flaky cases must both fail and pass within 20 runs.

```bash
uv sync --all-groups
uv run playwright install chromium
uv run python -m dataset.generate
```

## Run

```bash
uv sync
uv run pytest
```

## License

MIT
