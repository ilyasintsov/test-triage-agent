# test-triage-agent

A Claude agent that reads a failed test run and says why it failed: **product bug**, **test bug**,
**flaky** or **environment**, with root cause, suspect commit and confidence.

> Work in progress. Built in public over one week.

## Plan

- [ ] Sample app with a seeded pytest + Playwright suite and a labeled set of 40+ failures
- [ ] MCP server: failed tests, test logs, recent commits, similar past failures
- [ ] Agent on the Claude API returning structured triage
- [ ] Eval suite as a CI release gate: category accuracy, suspect-commit hit rate, cost, latency
- [ ] FastAPI backend + Next.js UI
- [ ] Deployed on AWS with Terraform

## Run

```bash
uv sync
uv run pytest
```

## License

MIT
