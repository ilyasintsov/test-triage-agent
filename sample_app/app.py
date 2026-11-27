import os
import sqlite3
from contextlib import closing
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

TAX_RATE = float(os.environ.get("TAX_RATE", "0.2"))
DISCOUNTS = {"SAVE10": 10, "SAVE25": 25}
INDEX_HTML = (Path(__file__).parent / "index.html").read_text()

app = FastAPI()


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(os.environ["DB_PATH"])
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, item TEXT NOT NULL,"
        " qty INTEGER NOT NULL, price_cents INTEGER NOT NULL, discount_code TEXT)"
    )
    return conn


class OrderIn(BaseModel):
    item: str
    qty: int
    price_cents: int
    discount_code: str | None = None


@app.post("/orders", status_code=201)
def create_order(order: OrderIn) -> dict:
    item = order.item.strip()
    if not item:
        raise HTTPException(422, "item must not be empty")
    if order.qty < 1:
        raise HTTPException(422, "qty must be at least 1")
    code = order.discount_code.upper() if order.discount_code else None
    if code is not None and code not in DISCOUNTS:
        raise HTTPException(422, "unknown discount code")
    with closing(db()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO orders (item, qty, price_cents, discount_code) VALUES (?, ?, ?, ?)",
            (item, order.qty, order.price_cents, code),
        )
    return {
        "id": cur.lastrowid,
        "item": item,
        "qty": order.qty,
        "price_cents": order.price_cents,
        "discount_code": code,
    }


@app.get("/orders")
def list_orders(page: int = 1, size: int = 10, q: str = "") -> list[dict]:
    offset = (page - 1) * size
    with closing(db()) as conn:
        rows = conn.execute(
            "SELECT * FROM orders WHERE item LIKE ? ORDER BY id DESC LIMIT ? OFFSET ?",
            (f"%{q}%", size, offset),
        ).fetchall()
    return [dict(row) for row in rows]


def get_row(order_id: int) -> sqlite3.Row:
    with closing(db()) as conn:
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "order not found")
    return row


@app.get("/orders/{order_id}")
def get_order(order_id: int) -> dict:
    return dict(get_row(order_id))


@app.get("/orders/{order_id}/total")
def order_total(order_id: int) -> dict:
    row = get_row(order_id)
    subtotal = row["qty"] * row["price_cents"]
    discount = subtotal * DISCOUNTS.get(row["discount_code"], 0) // 100
    tax = round((subtotal - discount) * TAX_RATE)
    return {
        "subtotal_cents": subtotal,
        "discount_cents": discount,
        "tax_cents": tax,
        "total_cents": subtotal - discount + tax,
    }


@app.delete("/orders/{order_id}", status_code=204)
def delete_order(order_id: int) -> None:
    with closing(db()) as conn, conn:
        cur = conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    if cur.rowcount == 0:
        raise HTTPException(404, "order not found")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML
