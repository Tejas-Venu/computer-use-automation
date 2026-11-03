
import asyncio
import uuid

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SessionState(str, Enum):
    RUNNING = "running"
    PAUSED = "paused"
    HUMAN_CONTROL = "human_control"
    RESUMING = "resuming"
    COMPLETED = "completed"
    FAILED = "failed"


class SessionOwnershipError(RuntimeError):
    pass


@dataclass
class SessionEvent:
    event: str
    state: str
    owner: str
    details: dict[str, Any] = field(default_factory=dict)


class BrowserSession:
    """
    Maintains ownership of one live Playwright page.

    All ownership transitions coordinate with browser
    actions using the same action_lock.
    """

    def __init__(self, page):
        self.session_id = uuid.uuid4().hex
        self.page = page

        self.state = SessionState.RUNNING
        self.owner = "automation"

        self.current_step: str | None = None
        self.intervention_reason: str | None = None

        self.events: list[SessionEvent] = []

        self._lock = asyncio.Lock()
        self.action_lock = asyncio.Lock()
        self._resume_event = asyncio.Event()

    def snapshot(self) -> dict:
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "owner": self.owner,
            "current_step": self.current_step,
            "intervention_reason": self.intervention_reason,
        }

    def _record(self, event: str):
        self.events.append(
            SessionEvent(
                event=event,
                state=self.state.value,
                owner=self.owner,
            )
        )

    async def request_intervention(
        self,
        step: str,
        reason: str,
    ):
        async with self.action_lock:
            async with self._lock:
                if self.state != SessionState.RUNNING:
                    raise SessionOwnershipError(
                        "Session is not running"
                    )

                self.state = SessionState.PAUSED
                self.owner = "none"
                self.current_step = step
                self.intervention_reason = reason

                self._resume_event.clear()
                self._record("intervention_requested")

    async def take_control(self, operator_id: str):
        async with self.action_lock:
            async with self._lock:
                if self.state != SessionState.PAUSED:
                    raise SessionOwnershipError(
                        "Session is not available for takeover"
                    )

                if not operator_id or not operator_id.strip():
                    raise ValueError(
                        "Operator ID is required"
                    )

                self.state = SessionState.HUMAN_CONTROL
                self.owner = operator_id

                self._record("human_control_acquired")

    async def release_control(self, operator_id: str):
        async with self.action_lock:
            async with self._lock:
                if self.state != SessionState.HUMAN_CONTROL:
                    raise SessionOwnershipError(
                        "Session is not under human control"
                    )

                if self.owner != operator_id:
                    raise SessionOwnershipError(
                        "Only the controlling operator can release"
                    )

                self.state = SessionState.RESUMING
                self.owner = "none"

                self._record("human_control_released")
                self._resume_event.set()

    async def wait_for_resume(self):
        await self._resume_event.wait()

    async def resume_automation(self):
        async with self.action_lock:
            async with self._lock:
                if self.state != SessionState.RESUMING:
                    raise SessionOwnershipError(
                        "Session is not ready to resume"
                    )

                self.state = SessionState.RUNNING
                self.owner = "automation"

                self._resume_event.clear()
                self._record("automation_resumed")

    async def complete(self):
        async with self.action_lock:
            async with self._lock:
                if (
                    self.state != SessionState.RUNNING
                    or self.owner != "automation"
                ):
                    raise SessionOwnershipError(
                        "Automation must own session to complete"
                    )

                self.state = SessionState.COMPLETED
                self.owner = "none"
                self.current_step = None
                self.intervention_reason = None

                self._record("session_completed")

    async def fail(self):
        """
        Move a nonterminal session into FAILED.

        This also releases tasks waiting for intervention.
        """
        async with self.action_lock:
            async with self._lock:
                if self.state in (
                    SessionState.COMPLETED,
                    SessionState.FAILED,
                ):
                    return

                self.state = SessionState.FAILED
                self.owner = "none"

                self._resume_event.set()
                self._record("session_failed")

    def assert_automation_control(self):
        if (
            self.state != SessionState.RUNNING
            or self.owner != "automation"
        ):
            raise SessionOwnershipError(
                "Automation does not own the session"
            )

    def assert_human_control(self, operator_id: str):
        if (
            self.state != SessionState.HUMAN_CONTROL
            or self.owner != operator_id
        ):
            raise SessionOwnershipError(
                "Operator does not own the session"
            )
