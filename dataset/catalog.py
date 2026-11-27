"""Seeded failures for the sample app. Paths are relative to sample_app/.

An edit is (path, old, new): `old` must occur exactly once; `old=None` appends `new`
(creating the file if needed).
"""

from dataclasses import dataclass, field

Edit = tuple[str, str | None, str]


@dataclass
class Case:
    category: str  # product_bug | test_bug | flaky | environment
    root_cause: str
    message: str | None = None  # subject of the commit that causes the failure
    edits: list[Edit] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    setup: str | None = None  # port_conflict | readonly_db


def api_test(body: str) -> Edit:
    return ("tests/test_api.py", None, "\n\n" + body)


def ui_test(body: str) -> Edit:
    return ("tests/test_ui.py", None, "\n\n" + body)


def api_import(line: str) -> Edit:
    return ("tests/test_api.py", "def make(client, item=", f"{line}\n\n\ndef make(client, item=")


PRODUCT_BUGS = [
    Case(
        "product_bug",
        "list_orders computes OFFSET as page * size, so page 1 skips the first page of results.",
        "perf: simplify pagination offset",
        [("app.py", "offset = (page - 1) * size", "offset = page * size")],
    ),
    Case(
        "product_bug",
        "ORDER BY lost its DESC, so orders are listed oldest first.",
        "refactor: drop redundant sort direction from order query",
        [("app.py", "ORDER BY id DESC", "ORDER BY id")],
    ),
    Case(
        "product_bug",
        "Item search moved from LIKE to instr(), which is case-sensitive.",
        "perf: use instr() for item search instead of LIKE",
        [
            (
                "app.py",
                '"SELECT * FROM orders WHERE item LIKE ? ORDER BY id DESC LIMIT ? OFFSET ?",\n'
                '            (f"%{q}%", size, offset),',
                '"SELECT * FROM orders WHERE instr(item, ?) > 0 ORDER BY id DESC LIMIT ? OFFSET ?",\n'
                "            (q, size, offset),",
            )
        ],
    ),
    Case(
        "product_bug",
        "Tax is truncated with int() instead of rounded, losing a cent on fractional amounts.",
        "fix: avoid float rounding surprises in tax",
        [
            (
                "app.py",
                "tax = round((subtotal - discount) * TAX_RATE)",
                "tax = int((subtotal - discount) * TAX_RATE)",
            )
        ],
    ),
    Case(
        "product_bug",
        "Tax is computed on the subtotal before the discount is taken off.",
        "refactor: compute tax from subtotal",
        [
            (
                "app.py",
                "tax = round((subtotal - discount) * TAX_RATE)",
                "tax = round(subtotal * TAX_RATE)",
            )
        ],
    ),
    Case(
        "product_bug",
        "Discount codes are stored as typed, so a lowercase code is saved lowercase and never "
        "matches the discount table.",
        "refactor: store discount codes as entered",
        [
            (
                "app.py",
                "code = order.discount_code.upper() if order.discount_code else None\n"
                "    if code is not None and code not in DISCOUNTS:",
                "code = order.discount_code or None\n"
                "    if code is not None and code.upper() not in DISCOUNTS:",
            )
        ],
    ),
    Case(
        "product_bug",
        "Item names are no longer stripped, so whitespace-only items pass validation.",
        "fix: keep item names exactly as the customer typed them",
        [("app.py", "item = order.item.strip()", "item = order.item")],
    ),
    Case(
        "product_bug",
        "Quantity check is qty < 0, so zero-quantity orders are accepted.",
        "refactor: tidy order validation",
        [("app.py", "if order.qty < 1:", "if order.qty < 0:")],
    ),
    Case(
        "product_bug",
        "DELETE no longer checks rowcount, so deleting a missing order returns 204 instead of 404.",
        "refactor: simplify delete handler",
        [
            (
                "app.py",
                '        cur = conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))\n'
                "    if cur.rowcount == 0:\n"
                '        raise HTTPException(404, "order not found")\n',
                '        conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))\n',
            )
        ],
    ),
    Case(
        "product_bug",
        "get_row lost its None check, so a missing order raises TypeError (500) instead of 404.",
        "refactor: simplify order lookup",
        [
            (
                "app.py",
                '    if row is None:\n        raise HTTPException(404, "order not found")\n'
                "    return row",
                "    return row",
            )
        ],
    ),
    Case(
        "product_bug",
        "The UI no longer reloads the list after adding an order, so new orders do not appear.",
        "perf(ui): skip refetching the list after adding an order",
        [("index.html", "  event.target.reset();\n  load();", "  event.target.reset();")],
    ),
    Case(
        "product_bug",
        "The UI reads `message` from the error response, but the API returns `detail`, so the "
        "error banner shows 'undefined'.",
        "refactor(ui): read error text from the response message",
        [("index.html", "(await res.json()).detail", "(await res.json()).message")],
    ),
    Case(
        "product_bug",
        "The UI sends deletes as POST, which the API rejects with 405, so orders are not removed.",
        "fix(ui): send deletes as POST for corporate proxies",
        [("index.html", '{ method: "DELETE" }', '{ method: "POST" }')],
    ),
    Case(
        "product_bug",
        "Default page size was left at 1, so the list shows a single order.",
        "chore: lower default page size while debugging slow list",
        [("app.py", "size: int = 10", "size: int = 1")],
    ),
]

TEST_BUGS = [
    Case(
        "test_bug",
        "The UI test targets #order-list, but the list's id is #orders.",
        "test(ui): use list id selector",
        [
            (
                "tests/test_ui.py",
                '    add(page, "pen", qty="2")\n'
                '    expect(page.locator("#orders li")).to_have_count(1)\n'
                '    expect(page.locator("#orders li").first).to_contain_text("pen × 2")',
                '    add(page, "pen", qty="2")\n'
                '    expect(page.locator("#order-list li")).to_have_count(1)\n'
                '    expect(page.locator("#order-list li").first).to_contain_text("pen × 2")',
            )
        ],
    ),
    Case(
        "test_bug",
        "The test expects 600 tax on 2997, but 20% of 2997 is 599.4, which rounds to 599.",
        "test: fix expected tax for multi-quantity order",
        [
            (
                "tests/test_api.py",
                '        "tax_cents": 599,\n        "total_cents": 3596,',
                '        "tax_cents": 600,\n        "total_cents": 3597,',
            )
        ],
    ),
    Case(
        "test_bug",
        "The test requests /orders/missing; a non-integer id fails validation with 422, not 404.",
        "test: use an obviously missing id",
        [
            (
                "tests/test_api.py",
                'assert client.get("/orders/999999").status_code == 404',
                'assert client.get("/orders/missing").status_code == 404',
            )
        ],
    ),
    Case(
        "test_bug",
        "The test expects 200 from DELETE, but the endpoint's contract is 204 No Content.",
        "test: check delete returns OK",
        [
            (
                "tests/test_api.py",
                "assert client.delete(f\"/orders/{order['id']}\").status_code == 204",
                "assert client.delete(f\"/orders/{order['id']}\").status_code == 200",
            )
        ],
    ),
    Case(
        "test_bug",
        "clean_db is no longer autouse, so tests see orders left over by earlier tests.",
        "test: speed up suite by dropping per-test cleanup",
        [
            (
                "tests/conftest.py",
                "@pytest.fixture(autouse=True)\ndef clean_db():",
                "@pytest.fixture\ndef clean_db():",
            )
        ],
    ),
    Case(
        "test_bug",
        "The test asserts oldest-first order, but the listing contract is newest first.",
        "test: assert listing order explicitly",
        [
            (
                "tests/test_api.py",
                '== [second["id"], first["id"]]',
                '== [first["id"], second["id"]]',
            )
        ],
    ),
    Case(
        "test_bug",
        "The UI helper looks for placeholder 'Price in cents'; the page says 'Price (cents)'.",
        "test(ui): match price placeholder copy",
        [
            (
                "tests/test_ui.py",
                'page.get_by_placeholder("Price (cents)").fill(price)',
                'page.get_by_placeholder("Price in cents").fill(price)',
            )
        ],
    ),
    Case(
        "test_bug",
        "The test uses discount code SAVE20, which does not exist, so order creation fails with 422.",
        "test: cover the 20% promo",
        [
            (
                "tests/test_api.py",
                'discount_code="SAVE25"',
                'discount_code="SAVE20"',
            )
        ],
    ),
    Case(
        "test_bug",
        "The UI test seeds orders after opening the page, and the page does not poll, so the list "
        "stays empty.",
        "test(ui): open the page before seeding orders",
        [
            (
                "tests/test_ui.py",
                '    client.post("/orders", json={"item": "pen", "qty": 1, "price_cents": 100})\n'
                '    client.post("/orders", json={"item": "cup", "qty": 1, "price_cents": 100})\n'
                '    page.goto("/")',
                '    page.goto("/")\n'
                '    client.post("/orders", json={"item": "pen", "qty": 1, "price_cents": 100})\n'
                '    client.post("/orders", json={"item": "cup", "qty": 1, "price_cents": 100})',
            )
        ],
    ),
    Case(
        "test_bug",
        "The test expects 200 tax on 1003, but 20% is 200.6, which rounds to 201.",
        "test: tighten rounding expectation",
        [("tests/test_api.py", '["tax_cents"] == 201', '["tax_cents"] == 200')],
    ),
    Case(
        "test_bug",
        "The UI test expects 'pen x 2' with an ASCII x; the page renders a multiplication sign.",
        "test(ui): avoid non-ascii in assertions",
        [("tests/test_ui.py", 'to_contain_text("pen × 2")', 'to_contain_text("pen x 2")')],
    ),
    Case(
        "test_bug",
        "The UI test expects 'Item is required', but the API's message is 'item must not be empty'.",
        "test(ui): update blank item error copy",
        [
            (
                "tests/test_ui.py",
                'to_have_text("item must not be empty")',
                'to_have_text("Item is required")',
            )
        ],
    ),
]

FLAKY = [
    Case(
        "flaky",
        "The new test iterates over a set, whose order changes between runs (hash "
        "randomization), and asserts which item is listed last.",
        "test: cover bulk create",
        [
            api_test(
                "def test_bulk_create_lists_every_item(client):\n"
                '    items = {"pen", "cup", "hat"}\n'
                "    for item in items:\n"
                "        make(client, item=item)\n"
                '    listed = [o["item"] for o in client.get("/orders").json()]\n'
                "    assert sorted(listed) == sorted(items)\n"
                '    assert listed[-1] == "pen"\n'
            )
        ],
    ),
    Case(
        "flaky",
        "The new test picks two random colors that collide one time in three, giving two "
        "search matches instead of one.",
        "test: search returns a single match",
        [
            api_import("import random"),
            api_test(
                "def test_search_matches_one_order(client):\n"
                '    colors = ["red", "blue", "green"]\n'
                "    first, second = random.choice(colors), random.choice(colors)\n"
                '    make(client, item=f"{first} pen")\n'
                '    make(client, item=f"{second} pen")\n'
                '    assert len(client.get("/orders", params={"q": first}).json()) == 1\n'
            ),
        ],
    ),
    Case(
        "flaky",
        "The new test takes the first element of a set of discount codes, which is random per "
        "run, and expects SAVE10's amount.",
        "test: any discount code reduces the total",
        [
            api_test(
                "def test_any_discount_code_reduces_total(client):\n"
                '    code = next(iter({"SAVE10", "SAVE25"}))\n'
                "    order = make(client, qty=1, price_cents=1000, discount_code=code)\n"
                "    total = client.get(f\"/orders/{order['id']}/total\").json()\n"
                '    assert total["discount_cents"] == 100\n'
            )
        ],
    ),
    Case(
        "flaky",
        "The new UI test adds items in set order, which is random per run, and expects 'hat' "
        "to be the newest.",
        "test(ui): add several orders in a row",
        [
            ui_test(
                "def test_add_several_orders(page: Page):\n"
                '    page.goto("/")\n'
                '    for item in {"pen", "cup", "hat"}:\n'
                "        add(page, item)\n"
                '        expect(page.get_by_placeholder("Item")).to_have_value("")\n'
                '    expect(page.locator("#orders li")).to_have_count(3)\n'
                '    expect(page.locator("#orders li").first).to_contain_text("hat")\n'
            )
        ],
    ),
    Case(
        "flaky",
        "The new UI test sleeps a fixed 24 ms and then counts list items without waiting, "
        "racing the list reload.",
        "test(ui): check the count right after adding",
        [
            ui_test(
                "def test_add_order_updates_count(page: Page):\n"
                '    page.goto("/")\n'
                '    add(page, "pen")\n'
                "    page.wait_for_timeout(24)\n"
                '    assert page.locator("#orders li").count() == 1\n'
            )
        ],
    ),
    Case(
        "flaky",
        "The new UI test sleeps a fixed 21 ms and then reads the error banner without waiting, "
        "racing the POST response.",
        "test(ui): error banner appears quickly",
        [
            ui_test(
                "def test_blank_item_error_appears_quickly(page: Page):\n"
                '    page.goto("/")\n'
                '    add(page, "   ")\n'
                "    page.wait_for_timeout(21)\n"
                '    assert page.get_by_role("alert").inner_text() == "item must not be empty"\n'
            )
        ],
    ),
    Case(
        "flaky",
        "The new test assumes a repeated listing is cached and asserts the third call is no "
        "slower than the second; nothing is cached, so it compares timing noise.",
        "test: repeated listing is served from cache",
        [
            api_import("import time"),
            api_test(
                "def test_repeat_listing_is_cached(client):\n"
                "    for i in range(20):\n"
                '        make(client, item=f"item{i}")\n'
                "    timings = []\n"
                "    for _ in range(3):\n"
                "        start = time.perf_counter()\n"
                '        client.get("/orders")\n'
                "        timings.append(time.perf_counter() - start)\n"
                "    assert timings[2] <= timings[1]\n"
            ),
        ],
    ),
    Case(
        "flaky",
        "The new test creates orders from two threads and asserts ids come back in submission "
        "order, which depends on thread scheduling.",
        "test: parallel creates get increasing ids",
        [
            api_import("from concurrent.futures import ThreadPoolExecutor"),
            api_test(
                "def test_parallel_creates_get_increasing_ids(client):\n"
                "    with ThreadPoolExecutor(max_workers=2) as pool:\n"
                '        ids = list(pool.map(lambda i: make(client, item=f"c{i}")["id"], range(2)))\n'
                "    assert ids == sorted(ids)\n"
            ),
        ],
    ),
]

ENVIRONMENT = [
    Case(
        "environment",
        "DB_PATH points to a directory that does not exist on the runner.",
        env={"DB_PATH": "/var/ci-cache/orders/orders.db"},
    ),
    Case(
        "environment",
        "The SQLite file on the runner is read-only.",
        setup="readonly_db",
    ),
    Case(
        "environment",
        "TAX_RATE pipeline variable is '20%' instead of a decimal, so the app fails at import.",
        env={"TAX_RATE": "20%"},
    ),
    Case(
        "environment",
        "TAX_RATE is set to 0.25 on this runner; the suite assumes the default 0.2.",
        env={"TAX_RATE": "0.25"},
    ),
    Case(
        "environment",
        "Port 8765 is already taken on the runner, so the live server for UI tests cannot start.",
        setup="port_conflict",
    ),
    Case(
        "environment",
        "Playwright browsers are not installed in the runner image.",
        env={"PLAYWRIGHT_BROWSERS_PATH": "/opt/ms-playwright"},
    ),
    Case(
        "environment",
        "APP_PORT is set to 87650, which is not a valid port.",
        env={"APP_PORT": "87650"},
    ),
    Case(
        "environment",
        "DB_PATH is an empty string, so SQLite opens a new temporary database per connection "
        "and data does not persist between requests.",
        env={"DB_PATH": ""},
    ),
    Case(
        "environment",
        "DB_PATH points to a directory, not a file.",
        env={"DB_PATH": "/tmp"},
    ),
]

CASES = PRODUCT_BUGS + TEST_BUGS + FLAKY + ENVIRONMENT

# Unrelated commits mixed into every case's history, so the culprit has to be found.
NOISE: list[tuple[str, list[Edit]]] = [
    ("docs: describe local setup", [("README.md", None, "\nRun locally: `make run`.\n")]),
    (
        "feat: add health endpoint",
        [
            (
                "app.py",
                None,
                '\n\n@app.get("/health")\ndef health() -> dict:\n    return {"status": "ok"}\n',
            ),
            (
                "tests/test_api.py",
                None,
                '\n\ndef test_health(client):\n    assert client.get("/health").json() == '
                '{"status": "ok"}\n',
            ),
        ],
    ),
    ("chore: add editorconfig", [(".editorconfig", None, "root = true\n\n[*]\nindent_size = 4\n")]),
    ("docs: changelog for 1.4.0", [("CHANGELOG.md", None, "## 1.4.0\n\n- Faster order list\n")]),
    (
        "style(ui): tighten list spacing",
        [
            (
                "index.html",
                "<title>Orders</title>",
                "<title>Orders</title>\n<style>li { margin: 4px 0; }</style>",
            )
        ],
    ),
    (
        "docs: explain discount table",
        [
            (
                "app.py",
                "DISCOUNTS = {",
                "# Percent off the subtotal, applied before tax.\nDISCOUNTS = {",
            )
        ],
    ),
    (
        "feat: add version endpoint",
        [
            (
                "app.py",
                None,
                '\n\n@app.get("/version")\ndef version() -> dict:\n'
                '    return {"version": os.environ.get("APP_VERSION", "dev")}\n',
            )
        ],
    ),
    (
        "chore: add make targets",
        [("Makefile", None, "test:\n\tpytest\n\nrun:\n\tuvicorn app:app --reload\n")],
    ),
    (
        "test: document live server fixture",
        [
            (
                "tests/conftest.py",
                "def base_url():",
                'def base_url():\n    """Serve the app on a real port so Playwright can load it."""',
            )
        ],
    ),
]
