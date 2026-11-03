
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from app.artifacts.schema import LocatorSpec
from app.handoff.intervention import InterventionError
from app.handoff.service import OperatorService
from app.handoff.session import SessionOwnershipError
from app.safety.policy import PolicyViolation


STATIC_DIR = Path(__file__).parent / "static"

service = OperatorService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await service.stop()


app = FastAPI(
    title="Computer-Use Automation Operator API",
    lifespan=lifespan,
)


def authorize(
    x_operator_token: str | None = Header(default=None),
):
    expected = os.getenv("OPERATOR_TOKEN")

    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Operator token is not configured",
        )

    if not x_operator_token or not secrets.compare_digest(
        x_operator_token,
        expected,
    ):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
        )


class StartRequest(BaseModel):
    member_id: str = Field(pattern=r"^[0-9]{1,20}$")
    demo_intervention: bool = False


class OperatorRequest(BaseModel):
    operator_id: str = Field(min_length=1)


class ManualActionRequest(BaseModel):
    operator_id: str
    action: str
    target: LocatorSpec
    value: str | None = None


@app.get("/")
async def dashboard():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/static/styles.css")
async def styles():
    return FileResponse(
        STATIC_DIR / "styles.css",
        media_type="text/css",
    )


@app.get("/static/app.js")
async def javascript():
    return FileResponse(
        STATIC_DIR / "app.js",
        media_type="application/javascript",
    )


@app.get("/api/status", dependencies=[Depends(authorize)])
async def status():
    return service.status()


@app.post("/api/start", dependencies=[Depends(authorize)])
async def start(request: StartRequest):
    try:
        return await service.start(
            member_id=request.member_id,
            demo_intervention=request.demo_intervention,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )


@app.get("/api/screenshot", dependencies=[Depends(authorize)])
async def screenshot():
    try:
        image = await service.screenshot()

        return Response(
            content=image,
            media_type="image/png",
            headers={"Cache-Control": "no-store"},
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )


@app.post(
    "/api/interventions/{intervention_id}/acquire",
    dependencies=[Depends(authorize)],
)
async def acquire(
    intervention_id: str,
    request: OperatorRequest,
):
    try:
        if service.manager is None:
            raise InterventionError("No active session")

        intervention = await service.manager.acquire(
            intervention_id,
            request.operator_id,
        )

        return {
            "status": intervention.status.value,
            "operator_id": intervention.operator_id,
        }

    except (InterventionError, SessionOwnershipError) as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )


@app.post("/api/action", dependencies=[Depends(authorize)])
async def manual_action(request: ManualActionRequest):
    if service.controller is None:
        raise HTTPException(
            status_code=404,
            detail="No active session",
        )

    try:
        await service.controller.human_action(
            operator_id=request.operator_id,
            action=request.action,
            target=request.target,
            value=request.value,
        )

        return {"status": "executed"}

    except (
        SessionOwnershipError,
        PolicyViolation,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        )


@app.post(
    "/api/interventions/{intervention_id}/resolve",
    dependencies=[Depends(authorize)],
)
async def resolve(
    intervention_id: str,
    request: OperatorRequest,
):
    try:
        if service.manager is None:
            raise InterventionError("No active session")

        intervention = await service.manager.resolve(
            intervention_id,
            request.operator_id,
        )

        return {
            "status": intervention.status.value,
        }

    except (InterventionError, SessionOwnershipError) as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )
