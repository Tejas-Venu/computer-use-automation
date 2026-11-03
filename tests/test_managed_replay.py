
import asyncio
import json

import pytest

from app.handoff.intervention import InterventionManager
from app.handoff.session import BrowserSession, SessionState
from app.replay.engine import run_replay
from app.surface.browser import BrowserSurface


@pytest.mark.asyncio
async def test_managed_replay_handoff(tmp_path):
    surface = BrowserSurface()
    replay_task = None

    try:
        await surface.start()
        await surface.navigate("http://mock-bank:8000")

        original_page = surface.page

        session = BrowserSession(original_page)
        manager = InterventionManager(session)

        # Load the original capability artifact.
        with open(
            "artifacts/banking.get_savings_balance.v1.json"
        ) as file:
            artifact = json.load(file)

        # Keep the approved Search button locator.
        artifact["steps"][1]["target"] = {
            "strategy": "role",
            "role": "button",
            "name": "Search",
        }

        # Simulate a temporary UI problem.
        # The Search button becomes unavailable.
        await original_page.evaluate("""
            () => {
                const button = document.querySelector(
                    'button[type="submit"]'
                );

                button.style.display = "none";
            }
        """)

        # Save a temporary artifact without modifying
        # the working capability.
        temporary_artifact = tmp_path / "handoff.json"

        temporary_artifact.write_text(
            json.dumps(artifact)
        )

        # Start managed replay in the background.
        replay_task = asyncio.create_task(
            run_replay(
                member_id="12345",
                artifact_path=str(temporary_artifact),
                session=session,
                intervention_manager=manager,
                intervention_timeout=20.0,
            )
        )

        # Wait until replay requests intervention.
        request = None

        for _ in range(150):
            requests = manager.list_requests()

            if requests:
                request = requests[0]
                break

            if replay_task.done():
                break

            await asyncio.sleep(0.1)

        assert request is not None, (
            "No intervention request was created"
        )

        assert session.state == SessionState.PAUSED
        assert not replay_task.done()

        # Human operator acquires control.
        await manager.acquire(
            request.intervention_id,
            "operator-1",
        )

        assert session.state == SessionState.HUMAN_CONTROL

        session.assert_human_control("operator-1")

        # Simulate the operator restoring the UI
        # on the SAME Playwright page.
        await original_page.evaluate("""
            () => {
                const button = document.querySelector(
                    'button[type="submit"]'
                );

                button.style.display = "";
            }
        """)

        # Verify the original approved Search button
        # is available again.
        search_button = original_page.get_by_role(
            "button",
            name="Search",
            exact=True,
        )

        assert await search_button.is_visible()

        # Operator releases control.
        await manager.resolve(
            request.intervention_id,
            "operator-1",
        )

        # Wait for automation to resume.
        result = await asyncio.wait_for(
            replay_task,
            timeout=15.0,
        )

        print("\nMANAGED REPLAY RESULT:")
        print(json.dumps(result, indent=2))

        # Verify successful replay.
        assert result["status"] == "success"

        assert (
            result["outputs"]["member_id"]
            == "12345"
        )

        assert (
            result["outputs"]["savings_balance"]
            == "2450.75"
        )

        assert (
            result["outputs"]["currency"]
            == "USD"
        )

        # Verify the original browser page was preserved.
        assert session.page is original_page

        assert session.state == SessionState.COMPLETED

        # Verify that the browser reached the
        # correct member details page.
        assert original_page.url.endswith(
            "/members/12345"
        )

    finally:
        if replay_task is not None and not replay_task.done():
            replay_task.cancel()

            try:
                await replay_task
            except asyncio.CancelledError:
                pass

        await surface.close()
