import pytest
from playwright.sync_api import Page, expect

expect.set_options(timeout=3000)


@pytest.fixture(autouse=True)
def short_timeouts(page: Page):
    page.set_default_timeout(3000)


def add(page: Page, item: str, qty: str = "1", price: str = "100"):
    page.get_by_placeholder("Item").fill(item)
    page.locator("input[name=qty]").fill(qty)
    page.get_by_placeholder("Price (cents)").fill(price)
    page.get_by_role("button", name="Add").click()


def test_add_order_shows_in_list(page: Page):
    page.goto("/")
    add(page, "pen", qty="2")
    expect(page.locator("#orders li")).to_have_count(1)
    expect(page.locator("#orders li").first).to_contain_text("pen × 2")


def test_newest_order_is_first(page: Page):
    page.goto("/")
    add(page, "pen")
    expect(page.locator("#orders li")).to_have_count(1)
    add(page, "cup")
    expect(page.locator("#orders li").first).to_contain_text("cup")


def test_form_clears_after_add(page: Page):
    page.goto("/")
    add(page, "pen")
    expect(page.get_by_placeholder("Item")).to_have_value("")


def test_blank_item_shows_error(page: Page):
    page.goto("/")
    add(page, "   ")
    expect(page.get_by_role("alert")).to_have_text("item must not be empty")


def test_delete_removes_order(page: Page):
    page.goto("/")
    add(page, "pen")
    page.locator("#orders li").first.get_by_role("button", name="Delete").click()
    expect(page.locator("#orders li")).to_have_count(0)


def test_existing_orders_load_on_open(page: Page, client):
    client.post("/orders", json={"item": "pen", "qty": 1, "price_cents": 100})
    client.post("/orders", json={"item": "cup", "qty": 1, "price_cents": 100})
    page.goto("/")
    expect(page.locator("#orders li")).to_have_count(2)
