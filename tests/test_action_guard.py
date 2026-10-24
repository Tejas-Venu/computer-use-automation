
import pytest

from app.safety.guard import ActionGuard
from app.safety.policy import (
    PolicyViolation,
    SafetyPolicy,
)
from app.surface.browser import BrowserSurface


@pytest.mark.asyncio
async def test_member_search_allowed():
    surface = BrowserSurface()

    try:
        await surface.start()
        await surface.navigate("http://mock-bank:8000")

        guard = ActionGuard(SafetyPolicy())

        field = surface.page.locator(
            'input[name="member_id"]'
        )

        await guard.validate(
            surface.page, field, "fill"
        )

        button = surface.page.get_by_role(
            "button", name="Search"
        )

        await guard.validate(
            surface.page, button, "click"
        )

    finally:
        await surface.close()


@pytest.mark.asyncio
async def test_external_link_blocked():
    surface = BrowserSurface()

    try:
        await surface.start()
        await surface.navigate("http://mock-bank:8000")

        await surface.page.evaluate("""
            () => {
                const a = document.createElement("a");
                a.href = "https://example.com";
                a.innerText = "External Website";
                document.body.appendChild(a);
            }
        """)

        guard = ActionGuard(SafetyPolicy())

        link = surface.page.get_by_role(
            "link", name="External Website"
        )

        with pytest.raises(PolicyViolation):
            await guard.validate(
                surface.page, link, "click"
            )

    finally:
        await surface.close()


@pytest.mark.asyncio
async def test_risky_button_blocked():
    surface = BrowserSurface()

    try:
        await surface.start()
        await surface.navigate("http://mock-bank:8000")

        await surface.page.evaluate("""
            () => {
                const button = document.createElement("button");
                button.innerText = "Transfer Funds";
                document.body.appendChild(button);
            }
        """)

        guard = ActionGuard(SafetyPolicy())

        button = surface.page.get_by_role(
            "button", name="Transfer Funds"
        )

        with pytest.raises(PolicyViolation):
            await guard.validate(
                surface.page, button, "click"
            )

    finally:
        await surface.close()
