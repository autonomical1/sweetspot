import pytest

from .checks import assert_valid_products

ITEM = {"role": "C", "title": "x", "price": 10.0, "currency": "USD", "link": "https://e.invalid", "thumbnail": None, "source": "s"}
LAYOUT = {"speakers": [{"role": "C"}]}


def result(**item_overrides):
    item = {**ITEM, **item_overrides}
    return {"budget": 100.0, "total": item["price"] if isinstance(item.get("price"), (int, float)) else 0.0, "items": [item]}


def test_valid_without_screen_or_projector_item():
    assert_valid_products(result(), 100.0, LAYOUT)


def test_screen_and_projector_roles_allowed():
    assert_valid_products(result(role="screen"), 100.0)
    assert_valid_products(result(role="projector"), 100.0)


@pytest.mark.parametrize("role", ["subwoofer", "", "l"])
def test_rejects_unknown_roles(role):
    with pytest.raises(AssertionError, match="role"):
        assert_valid_products(result(role=role), 100.0)


@pytest.mark.parametrize("currency", ["usd", "US", "DOLLARS", ""])
def test_rejects_malformed_currency(currency):
    with pytest.raises(AssertionError, match="currency"):
        assert_valid_products(result(currency=currency), 100.0)


def test_other_iso_currency_allowed():
    assert_valid_products(result(currency="EUR"), 100.0)


@pytest.mark.parametrize("bad_item", [None, "item", 3, ["C"]])
def test_non_object_item_is_assertion_error(bad_item):
    with pytest.raises(AssertionError, match="object"):
        assert_valid_products({"budget": 100.0, "total": 0.0, "items": [bad_item]}, 100.0)
