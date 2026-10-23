
from app.discovery.completion import verify_savings_balance


def test_valid_balance():
    text = """
    Member Details
    Member ID: 12345
    Name: Alex Morgan
    Savings Balance: $2450.75
    Account Status: Active
    """

    result = verify_savings_balance(text, "12345")

    assert result == {
        "member_id": "12345",
        "savings_balance": "2450.75",
        "currency": "USD",
    }


def test_wrong_member():
    text = """
    Member ID: 67890
    Savings Balance: $2450.75
    """

    assert verify_savings_balance(text, "12345") is None


def test_missing_balance():
    text = """
    Member ID: 12345
    Savings Balance: Unavailable
    """

    assert verify_savings_balance(text, "12345") is None
