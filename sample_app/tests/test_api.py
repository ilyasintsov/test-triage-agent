def make(client, item="pen", qty=1, price_cents=100, **extra):
    response = client.post(
        "/orders", json={"item": item, "qty": qty, "price_cents": price_cents, **extra}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_order_can_be_fetched(client):
    order = make(client, item="pen", qty=2, price_cents=150)
    assert client.get(f"/orders/{order['id']}").json() == order


def test_item_is_trimmed(client):
    assert make(client, item="  pen  ")["item"] == "pen"


def test_blank_item_is_rejected(client):
    response = client.post("/orders", json={"item": "   ", "qty": 1, "price_cents": 100})
    assert response.status_code == 422


def test_zero_qty_is_rejected(client):
    response = client.post("/orders", json={"item": "pen", "qty": 0, "price_cents": 100})
    assert response.status_code == 422


def test_unknown_discount_code_is_rejected(client):
    response = client.post(
        "/orders", json={"item": "pen", "qty": 1, "price_cents": 100, "discount_code": "FREE"}
    )
    assert response.status_code == 422


def test_discount_code_is_case_insensitive(client):
    assert make(client, discount_code="save10")["discount_code"] == "SAVE10"


def test_list_is_newest_first(client):
    first = make(client, item="pen")
    second = make(client, item="cup")
    assert [o["id"] for o in client.get("/orders").json()] == [second["id"], first["id"]]


def test_pagination(client):
    ids = [make(client, item=f"item{i}")["id"] for i in range(5)]
    newest_first = ids[::-1]
    page1 = client.get("/orders", params={"size": 2, "page": 1}).json()
    page3 = client.get("/orders", params={"size": 2, "page": 3}).json()
    assert [o["id"] for o in page1] == newest_first[:2]
    assert [o["id"] for o in page3] == newest_first[4:]


def test_search_is_case_insensitive(client):
    make(client, item="Blue Pen")
    make(client, item="cup")
    assert [o["item"] for o in client.get("/orders", params={"q": "blue"}).json()] == ["Blue Pen"]


def test_missing_order_is_404(client):
    assert client.get("/orders/999999").status_code == 404


def test_total_applies_tax(client):
    order = make(client, qty=3, price_cents=999)
    assert client.get(f"/orders/{order['id']}/total").json() == {
        "subtotal_cents": 2997,
        "discount_cents": 0,
        "tax_cents": 599,
        "total_cents": 3596,
    }


def test_total_rounds_tax_to_nearest_cent(client):
    order = make(client, qty=1, price_cents=1003)
    assert client.get(f"/orders/{order['id']}/total").json()["tax_cents"] == 201


def test_discount_is_applied_before_tax(client):
    order = make(client, qty=1, price_cents=1000, discount_code="SAVE25")
    total = client.get(f"/orders/{order['id']}/total").json()
    assert (total["discount_cents"], total["tax_cents"], total["total_cents"]) == (250, 150, 900)


def test_delete_order(client):
    order = make(client)
    assert client.delete(f"/orders/{order['id']}").status_code == 204
    assert client.get(f"/orders/{order['id']}").status_code == 404


def test_delete_missing_order_is_404(client):
    assert client.delete("/orders/999999").status_code == 404
