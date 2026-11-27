"""Build the labeled failure set in cases/.

For each catalog case: copy sample_app into a fresh git repo, commit a few unrelated changes
plus the culprit, run the suite, and save what a CI job would leave behind.

    uv run python -m dataset.generate            # all cases
    uv run python -m dataset.generate --only 10  # first 10, to check the pipeline
"""

import argparse
import json
import os
import random
import shutil
import socket
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from dataset.catalog import CASES, NOISE, Case, Edit

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "sample_app"
OUT = ROOT / "cases"
CI_WORKDIR = "/builds/orders-app"
CI_HOME = "/home/ci"
FLAKY_MAX_RUNS = 20
AUTHORS = [
    ("Maya Chen", "maya.chen@example.com"),
    ("Tom Okafor", "tom.okafor@example.com"),
    ("Priya Raman", "priya.raman@example.com"),
    ("Lukas Berg", "lukas.berg@example.com"),
    ("Sara Novak", "sara.novak@example.com"),
]


@dataclass
class Run:
    failed: list[str]
    log: str
    junit: str | None


def git(repo: Path, *args: str, env: dict | None = None) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, env=env, check=True, capture_output=True, text=True
    ).stdout


def commit(repo: Path, message: str, author: tuple[str, str], when: datetime) -> str:
    name, email = author
    stamp = when.isoformat()
    env = os.environ | {
        "GIT_AUTHOR_NAME": name,
        "GIT_AUTHOR_EMAIL": email,
        "GIT_COMMITTER_NAME": name,
        "GIT_COMMITTER_EMAIL": email,
        "GIT_AUTHOR_DATE": stamp,
        "GIT_COMMITTER_DATE": stamp,
    }
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--no-verify", "-m", message, env=env)
    return git(repo, "rev-parse", "HEAD").strip()


def apply(repo: Path, edits: list[Edit]) -> None:
    for path, old, new in edits:
        file = repo / path
        text = file.read_text() if file.exists() else ""
        if old is None:
            text += new
        elif text.count(old) != 1:
            raise ValueError(f"{path}: anchor must occur once: {old[:60]!r}")
        else:
            text = text.replace(old, new)
        file.write_text(text)


def sanitize(text: str, work: Path) -> str:
    for real, fake in [
        (str(work.resolve()), CI_WORKDIR),
        (str(work), CI_WORKDIR),
        (str(ROOT / ".venv"), "/opt/venv"),
        (str(Path.home()), CI_HOME),
        (socket.gethostname(), "ci-runner-07"),
    ]:
        text = text.replace(real, fake)
    return text


def run_suite(work: Path, env: dict) -> Run:
    junit = work / "junit.xml"
    junit.unlink(missing_ok=True)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-rfE", f"--junitxml={junit}"],
        cwd=work,
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )
    log = sanitize(proc.stdout + proc.stderr, work)
    if not junit.exists():  # pytest stopped before collecting, e.g. conftest failed to import
        return Run(["<session>"], log, None)
    failed = [
        f"{tc.get('classname')}::{tc.get('name')}"
        for tc in ET.parse(junit).iter("testcase")
        if tc.find("failure") is not None or tc.find("error") is not None
    ]
    return Run(failed, log, sanitize(junit.read_text(), work))


def case_env(case: Case, scratch: Path, stack: ExitStack) -> dict:
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"DB_PATH", "TAX_RATE", "APP_PORT", "PYTHONHASHSEED", "VIRTUAL_ENV"}
    }
    env |= case.env
    if case.setup == "readonly_db":
        db = scratch / "orders.db"
        db.touch()
        db.chmod(0o444)
        env["DB_PATH"] = str(db)
    elif case.setup == "port_conflict":
        sock = stack.enter_context(socket.socket())
        sock.bind(("127.0.0.1", 8765))
        sock.listen()
    return env


def build_history(case: Case, work: Path, rng: random.Random) -> tuple[str, str | None]:
    """Returns (base sha, culprit sha)."""
    shutil.copytree(APP, work, ignore=shutil.ignore_patterns("__pycache__", "*.db", "junit.xml"))
    git(work, "init", "-q", "-b", "main")
    when = datetime(2026, 11, 2, 9, 0) + timedelta(days=rng.randint(0, 20))
    base = commit(work, "import orders app", AUTHORS[0], when)

    steps: list[tuple[str, list[Edit], bool]] = [
        (msg, edits, False) for msg, edits in rng.sample(NOISE, rng.randint(2, 4))
    ]
    if case.message:
        steps.insert(rng.randint(len(steps) // 2, len(steps)), (case.message, case.edits, True))

    culprit = None
    for message, edits, is_culprit in steps:
        when += timedelta(hours=rng.randint(1, 30), minutes=rng.randint(0, 59))
        apply(work, edits)
        sha = commit(work, message, rng.choice(AUTHORS), when)
        if is_culprit:
            culprit = sha
    return base, culprit


def commits_since(work: Path, base: str) -> list[dict]:
    log = git(work, "log", "--format=%H%x1f%an <%ae>%x1f%aI%x1f%s", f"{base}..HEAD")
    commits = []
    for line in log.splitlines():
        sha, author, date, subject = line.split("\x1f")
        commits.append(
            {
                "sha": sha,
                "author": author,
                "date": date,
                "message": subject,
                "files": git(work, "show", "--format=", "--name-only", sha).split(),
                "diff": git(work, "show", "--format=", sha),
            }
        )
    return commits


def record(work: Path, env: dict, flaky: bool) -> tuple[Run, Run]:
    """Returns (the failing run we keep, the rerun right after it)."""
    if not flaky:
        first, rerun = run_suite(work, env), run_suite(work, env)
        if not first.failed:
            raise RuntimeError("expected failures, suite passed")
        if first.failed != rerun.failed:
            raise RuntimeError(f"not deterministic: {first.failed} then {rerun.failed}")
        return first, rerun

    runs = []
    while len(runs) < FLAKY_MAX_RUNS:
        runs.append(run_suite(work, env))
        outcomes = {bool(r.failed) for r in runs}
        if outcomes == {True, False} and runs[-1] is not next(r for r in runs if r.failed):
            break
    else:
        raise RuntimeError(f"not flaky in {FLAKY_MAX_RUNS} runs: {[bool(r.failed) for r in runs]}")
    i = next(i for i, r in enumerate(runs) if r.failed)
    return runs[i], runs[i + 1]


def generate(index: int, case: Case) -> dict:
    case_id = f"case-{index + 1:03d}"
    rng = random.Random(index)
    with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
        scratch = Path(tmp)
        work = scratch / "orders-app"
        base, culprit = build_history(case, work, rng)
        first, rerun = record(work, case_env(case, scratch, stack), case.category == "flaky")
        commits = commits_since(work, base)

    out = OUT / case_id
    out.mkdir(parents=True)
    (out / "run.log").write_text(first.log)
    if first.junit:
        (out / "junit.xml").write_text(first.junit)
    (out / "commits.json").write_text(json.dumps(commits, indent=2) + "\n")
    (out / "rerun.json").write_text(json.dumps({"failed": rerun.failed}, indent=2) + "\n")
    return {
        "case_id": case_id,
        "category": case.category,
        "root_cause": case.root_cause,
        "suspect_commit": culprit,
        "failing_tests": first.failed,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", type=int, help="generate only the first N cases")
    args = parser.parse_args()

    cases = CASES[:]
    random.Random(42).shuffle(cases)  # so case numbers do not reveal the category
    cases = cases[: args.only] if args.only else cases

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "orders-app"
        shutil.copytree(APP, work, ignore=shutil.ignore_patterns("__pycache__", "*.db"))
        for _, edits in NOISE:
            apply(work, edits)
        if failed := run_suite(work, case_env(Case("", ""), Path(tmp), ExitStack())).failed:
            raise RuntimeError(f"base app with all noise commits must pass, failed: {failed}")

    shutil.rmtree(OUT, ignore_errors=True)
    labels = []
    for index, case in enumerate(cases):
        label = generate(index, case)
        labels.append(label)
        print(f"{label['case_id']} {case.category:12} failed={len(label['failing_tests'])}")
    (OUT / "labels.jsonl").write_text("".join(json.dumps(row) + "\n" for row in labels))


if __name__ == "__main__":
    main()
