import os
import tempfile
import threading
import time
from contextlib import closing

import pytest

os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "orders.db"))

import uvicorn
from app import app, db
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def clean_db():
    with closing(db()) as conn, conn:
        conn.execute("DELETE FROM orders")


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(scope="session")
def base_url():
    port = int(os.environ.get("APP_PORT", "8765"))
    server = uvicorn.Server(uvicorn.Config(app, port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started:
        if not thread.is_alive() or time.monotonic() > deadline:
            raise RuntimeError(f"app server did not start on port {port}")
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
