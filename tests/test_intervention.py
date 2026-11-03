
import pytest

from app.handoff.intervention import (
    InterventionError,
    InterventionManager,
    InterventionStatus,
)
from app.handoff.session import (
    BrowserSession,
    SessionState,
)


@pytest.mark.asyncio
async def test_create_intervention():
    session = BrowserSession(object())
    manager = InterventionManager(session)

    request = await manager.create(
        capability_id="banking.get_savings_balance",
        step_id="open_details",
        reason="Unexpected confirmation dialog",
    )

    assert request.status == InterventionStatus.PENDING
    assert request.session_id == session.session_id
    assert session.state == SessionState.PAUSED
    assert session.owner == "none"


@pytest.mark.asyncio
async def test_full_intervention_lifecycle():
    page = object()
    session = BrowserSession(page)
    manager = InterventionManager(session)

    request = await manager.create(
        capability_id="banking.get_savings_balance",
        step_id="open_details",
        reason="Manual assistance required",
    )

    await manager.acquire(
        request.intervention_id,
        "operator-1",
    )

    assert request.status == InterventionStatus.IN_PROGRESS
    assert session.state == SessionState.HUMAN_CONTROL

    await manager.resolve(
        request.intervention_id,
        "operator-1",
    )

    assert request.status == InterventionStatus.RESOLVED
    assert request.resolved_at is not None
    assert session.state == SessionState.RESUMING

    await session.wait_for_resume()
    await session.resume_automation()

    assert session.state == SessionState.RUNNING
    assert session.page is page


@pytest.mark.asyncio
async def test_duplicate_active_intervention_blocked():
    session = BrowserSession(object())
    manager = InterventionManager(session)

    await manager.create(
        capability_id="banking.get_savings_balance",
        step_id="submit_search",
        reason="Manual review required",
    )

    with pytest.raises(InterventionError):
        await manager.create(
            capability_id="banking.get_savings_balance",
            step_id="open_details",
            reason="Another request",
        )


@pytest.mark.asyncio
async def test_wrong_operator_cannot_resolve():
    session = BrowserSession(object())
    manager = InterventionManager(session)

    request = await manager.create(
        capability_id="banking.get_savings_balance",
        step_id="open_details",
        reason="Manual assistance required",
    )

    await manager.acquire(
        request.intervention_id,
        "operator-1",
    )

    with pytest.raises(InterventionError):
        await manager.resolve(
            request.intervention_id,
            "operator-2",
        )

    assert request.status == InterventionStatus.IN_PROGRESS
    assert session.owner == "operator-1"


@pytest.mark.asyncio
async def test_unknown_intervention():
    manager = InterventionManager(
        BrowserSession(object())
    )

    with pytest.raises(InterventionError):
        manager.get("missing-id")
