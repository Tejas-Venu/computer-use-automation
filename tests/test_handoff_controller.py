
import pytest

from app.artifacts.schema import LocatorSpec
from app.handoff.controller import SharedBrowserController
from app.handoff.session import (
    BrowserSession,
    SessionOwnershipError,
)
from app.safety.policy import SafetyPolicy
from app.surface.browser import BrowserSurface


@pytest.mark.asyncio
async def test_automation_can_fill():
    surface = BrowserSurface()

    try:
        await surface.start()
        await surface.navigate("http://mock-bank:8000")

        session = BrowserSession(surface.page)

        controller = SharedBrowserController(
            session,
            SafetyPolicy(),
        )

        target = LocatorSpec(
            strategy="attribute",
            tag="input",
            attribute="name",
            value="member_id",
        )

        await controller.automation_action(
            action="fill",
            target=target,
            value="12345",
        )

        assert await surface.page.locator(
            'input[name="member_id"]'
        ).input_value() == "12345"

    finally:
        await surface.close()


@pytest.mark.asyncio
async def test_automation_blocked_during_human_control():
    surface = BrowserSurface()

    try:
        await surface.start()
        await surface.navigate("http://mock-bank:8000")

        session = BrowserSession(surface.page)

        controller = SharedBrowserController(
            session,
            SafetyPolicy(),
        )

        await session.request_intervention(
            step="enter_member_id",
            reason="Manual input required",
        )

        await session.take_control("operator-1")

        target = LocatorSpec(
            strategy="attribute",
            tag="input",
            attribute="name",
            value="member_id",
        )

        with pytest.raises(SessionOwnershipError):
            await controller.automation_action(
                action="fill",
                target=target,
                value="12345",
            )

        await controller.human_action(
            operator_id="operator-1",
            action="fill",
            target=target,
            value="67890",
        )

        assert await surface.page.locator(
            'input[name="member_id"]'
        ).input_value() == "67890"

    finally:
        await surface.close()


@pytest.mark.asyncio
async def test_wrong_operator_blocked():
    surface = BrowserSurface()

    try:
        await surface.start()
        await surface.navigate("http://mock-bank:8000")

        session = BrowserSession(surface.page)

        controller = SharedBrowserController(
            session,
            SafetyPolicy(),
        )

        await session.request_intervention(
            step="enter_member_id",
            reason="Manual input required",
        )

        await session.take_control("operator-1")

        target = LocatorSpec(
            strategy="attribute",
            tag="input",
            attribute="name",
            value="member_id",
        )

        with pytest.raises(SessionOwnershipError):
            await controller.human_action(
                operator_id="operator-2",
                action="fill",
                target=target,
                value="67890",
            )

    finally:
        await surface.close()
