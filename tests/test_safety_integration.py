
import pytest

from app.replay.evidence import sanitize
from app.safety.guard import ActionGuard
from app.safety.policy import PolicyViolation, SafetyPolicy
from app.surface.browser import BrowserSurface


def test_bearer_token_redaction():
    value = "Authorization: Bearer abc123secret"

    result = sanitize(value)

    assert "abc123secret" not in result
    assert "[REDACTED]" in result


def test_password_string_redaction():
    value = "password=mysecretpassword"

    result = sanitize(value)

    assert "mysecretpassword" not in result


@pytest.mark.asyncio
async def test_unsafe_action_rejected():
    surface = BrowserSurface()

    try:
        await surface.start()
        await surface.navigate("http://mock-bank:8000")

        await surface.page.evaluate("""
            () => {
                const button = document.createElement("button");
                button.innerText = "Delete Account";
                document.body.appendChild(button);
            }
        """)

        guard = ActionGuard(SafetyPolicy())

        button = surface.page.get_by_role(
            "button",
            name="Delete Account",
        )

        with pytest.raises(PolicyViolation):
            await guard.validate(
                surface.page,
                button,
                "click",
            )

    finally:
        await surface.close()
