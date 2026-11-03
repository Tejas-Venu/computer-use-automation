
import asyncio

import pytest

from app.handoff.session import (
    BrowserSession,
    SessionOwnershipError,
    SessionState,
)


@pytest.mark.asyncio
async def test_initial_session_state():
    page = object()
    session = BrowserSession(page)

    assert session.state == SessionState.RUNNING
    assert session.owner == "automation"
    assert session.page is page

    session.assert_automation_control()


@pytest.mark.asyncio
async def test_complete_handoff():
    page = object()
    session = BrowserSession(page)

    await session.request_intervention(
        step="open_details",
        reason="Unexpected confirmation dialog",
    )

    assert session.state == SessionState.PAUSED
    assert session.owner == "none"

    await session.take_control("operator-1")

    assert session.state == SessionState.HUMAN_CONTROL
    assert session.owner == "operator-1"

    session.assert_human_control("operator-1")

    with pytest.raises(SessionOwnershipError):
        session.assert_automation_control()

    await session.release_control("operator-1")

    assert session.state == SessionState.RESUMING

    await asyncio.wait_for(
        session.wait_for_resume(),
        timeout=1.0,
    )

    await session.resume_automation()

    assert session.state == SessionState.RUNNING
    assert session.owner == "automation"

    # The browser page must be unchanged.
    assert session.page is page


@pytest.mark.asyncio
async def test_unauthorized_release_blocked():
    session = BrowserSession(object())

    await session.request_intervention(
        step="submit_search",
        reason="Manual review required",
    )

    await session.take_control("operator-1")

    with pytest.raises(SessionOwnershipError):
        await session.release_control("operator-2")

    assert session.owner == "operator-1"


@pytest.mark.asyncio
async def test_takeover_without_pause_blocked():
    session = BrowserSession(object())

    with pytest.raises(SessionOwnershipError):
        await session.take_control("operator-1")


@pytest.mark.asyncio
async def test_session_completion():
    session = BrowserSession(object())

    await session.complete()

    assert session.state == SessionState.COMPLETED
    assert session.owner == "none"

    with pytest.raises(SessionOwnershipError):
        session.assert_automation_control()
