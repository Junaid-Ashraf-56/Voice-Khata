import sqlite3

import pytest

from app.ledger import Ledger, resolve_name


@pytest.fixture
def led():
    return Ledger(":memory:")


def test_balance_is_udhaar_minus_payments(led):
    led.add_entry("Ahmed", 500, "udhaar")
    led.add_entry("Ahmed", 300, "udhaar")
    led.add_entry("Ahmed", 200, "payment")
    assert led.balance("Ahmed") == 600


def test_balances_are_per_customer(led):
    led.add_entry("Ahmed", 500, "udhaar")
    led.add_entry("Bilal", 100, "udhaar")
    assert led.balance("Ahmed") == 500
    assert led.balance("Bilal") == 100


def test_overpayment_goes_negative(led):
    led.add_entry("Ahmed", 100, "udhaar")
    led.add_entry("Ahmed", 250, "payment")
    assert led.balance("Ahmed") == -150


def test_unknown_customer_balance_is_zero(led):
    assert led.balance("Nobody") == 0


def test_all_balances(led):
    led.add_entry("Bilal", 100, "udhaar")
    led.add_entry("Ahmed", 500, "udhaar")
    led.add_entry("Ahmed", 500, "payment")
    assert dict(led.all_balances()) == {"Ahmed": 0, "Bilal": 100}


def test_customer_created_once(led):
    led.add_entry("Ahmed", 1, "udhaar")
    led.add_entry("Ahmed", 1, "udhaar")
    assert led.customer_names() == ["Ahmed"]


def test_urdu_names_work(led):
    led.add_entry("احمد", 500, "udhaar")
    assert led.balance("احمد") == 500


def test_db_rejects_bad_rows(led):
    led.add_entry("Ahmed", 1, "udhaar")
    with pytest.raises(sqlite3.IntegrityError):
        led.add_entry("Ahmed", 0, "udhaar")
    with pytest.raises(sqlite3.IntegrityError):
        led.add_entry("Ahmed", 5, "gift")


# ---- name matching ----

def test_exact_match_ignores_case_and_spacing():
    assert resolve_name("  ahmed  ", ["Ahmed", "Bilal"]) == ("Ahmed", False, [])


def test_new_name_is_new():
    name, is_new, similar = resolve_name("Zubair", ["Ahmed", "Bilal"])
    assert (name, is_new, similar) == ("Zubair", True, [])


def test_near_match_is_suggested_not_merged():
    name, is_new, similar = resolve_name("Ahmad", ["Ahmed", "Bilal"])
    assert name == "Ahmad" and is_new is True
    assert similar == ["Ahmed"]


def test_no_existing_customers():
    assert resolve_name("Ahmed", []) == ("Ahmed", True, [])
