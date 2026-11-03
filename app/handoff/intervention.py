
import asyncio
import uuid

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from app.handoff.session import (
    BrowserSession,
    SessionState,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class InterventionStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class InterventionError(RuntimeError):
    pass


@dataclass
class InterventionRequest:
    intervention_id: str
    session_id: str
    capability_id: str
    step_id: str
    reason: str

    status: InterventionStatus = InterventionStatus.PENDING

    operator_id: str | None = None

    created_at: str = field(default_factory=utc_now)
    resolved_at: str | None = None


class InterventionManager:
    """
    Coordinates intervention requests with the
    ownership state of an existing browser session.

    The manager does not create or replace a page.
    """

    def __init__(self, session: BrowserSession):
        self.session = session
        self.requests: dict[str, InterventionRequest] = {}
        self._lock = asyncio.Lock()

    async def create(
        self,
        capability_id: str,
        step_id: str,
        reason: str,
    ) -> InterventionRequest:
        async with self._lock:
            if not capability_id.strip():
                raise ValueError("Capability ID is required")

            if not step_id.strip():
                raise ValueError("Step ID is required")

            if not reason.strip():
                raise ValueError("Reason is required")

            if any(
                request.status != InterventionStatus.RESOLVED
                for request in self.requests.values()
            ):
                raise InterventionError(
                    "An intervention is already active"
                )

            await self.session.request_intervention(
                step=step_id,
                reason=reason,
            )

            request = InterventionRequest(
                intervention_id=uuid.uuid4().hex,
                session_id=self.session.session_id,
                capability_id=capability_id,
                step_id=step_id,
                reason=reason,
            )

            self.requests[request.intervention_id] = request
            return request

    async def acquire(
        self,
        intervention_id: str,
        operator_id: str,
    ) -> InterventionRequest:
        async with self._lock:
            request = self.get(intervention_id)

            if request.status != InterventionStatus.PENDING:
                raise InterventionError(
                    "Intervention is not pending"
                )

            await self.session.take_control(operator_id)

            request.operator_id = operator_id
            request.status = InterventionStatus.IN_PROGRESS

            return request

    async def resolve(
        self,
        intervention_id: str,
        operator_id: str,
    ) -> InterventionRequest:
        async with self._lock:
            request = self.get(intervention_id)

            if request.status != InterventionStatus.IN_PROGRESS:
                raise InterventionError(
                    "Intervention is not in progress"
                )

            if request.operator_id != operator_id:
                raise InterventionError(
                    "Operator does not own this intervention"
                )

            await self.session.release_control(operator_id)

            request.status = InterventionStatus.RESOLVED
            request.resolved_at = utc_now()

            return request

    def get(self, intervention_id: str) -> InterventionRequest:
        request = self.requests.get(intervention_id)

        if request is None:
            raise InterventionError(
                "Intervention not found"
            )

        return request

    def list_requests(self) -> list[InterventionRequest]:
        return list(self.requests.values())
