
import re
from decimal import Decimal, InvalidOperation


def verify_savings_balance(
    page_text: str,
    member_id: str,
) -> dict | None:
    """
    Verify that the displayed member matches the requested
    member and extract the savings balance.

    Returns structured outputs on success, otherwise None.
    """

    member_match = re.search(
        r"Member ID:\s*(\d+)",
        page_text,
    )

    balance_match = re.search(
        r"Savings Balance:\s*\$([\d,]+(?:\.\d{2})?)",
        page_text,
    )

    if not member_match or not balance_match:
        return None

    if member_match.group(1) != member_id:
        return None

    try:
        balance = Decimal(
            balance_match.group(1).replace(",", "")
        )
    except InvalidOperation:
        return None

    return {
        "member_id": member_id,
        "savings_balance": str(balance),
        "currency": "USD",
    }
