
import asyncio

import pytest

from app.artifacts.schema import LocatorSpec
from app.handoff.controller import SharedBrowserController
from app.handoff.intervention import InterventionManager
from app.handoff.session import BrowserSession, SessionState
from app.safety.policy import SafetyPolicy
from app.surface.browser import BrowserSurface


@pytest.mark.asyncio
async def test_live_browser_handoff():
    surface = BrowserSurface()

    try:
        await surface.start()
        await surface.navigate("http://mock-bank:8000")

        original_page = surface.page

        session = BrowserSession(original_page)
        manager = InterventionManager(session)

        controller = SharedBrowserController(
            session=session,
            policy=SafetyPolicy(),
        )

        target = LocatorSpec(
            strategy="attribute",
            tag="input",
            attribute="name",
            value="member_id",
        )

        # Automation requests intervention.
        request = await manager.create(
            capability_id="banking.get_savings_balance",
            step_id="enter_member_id",
            reason="Operator input required",
        )

        assert session.state == SessionState.PAUSED

        # Operator takes control.
        await manager.acquire(
            request.intervention_id,
            "operator-1",
        )

        assert session.state == SessionState.HUMAN_CONTROL

        # Operator uses the SAME browser page.
        await controller.human_action(
            operator_id="operator-1",
            action="fill",
            target=target,
            value="67890",
        )

        assert await original_page.locator(
            'input[name="member_id"]'
        ).input_value() == "67890"

        # Operator releases control.
        await manager.resolve(
            request.intervention_id,
            "operator-1",
        )

        await asyncio.wait_for(
            session.wait_for_resume(),
            timeout=2.0,
        )

        await session.resume_automation()

        assert session.state == SessionState.RUNNING
        assert session.page is original_page

        # Automation continues using the same page.
        search_button = LocatorSpec(
            strategy="role",
            role="button",
            name="Search",
        )

        await controller.automation_action(
            action="click",
            target=search_button,
        )

        assert session.page.url.endswith("/search")

        text = await session.page.locator(
            "body"
        ).inner_text()

        assert "Jordan Lee" in text

    finally:
        await surface.close()
