# orders-app

A small orders service (FastAPI + SQLite + one HTML page) with a pytest and Playwright suite.
It is the system under test for the triage agent: `dataset/generate.py` seeds failures into
copies of it.

```bash
uv run pytest
```
