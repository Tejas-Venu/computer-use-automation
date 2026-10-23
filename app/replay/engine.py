
import asyncio
import json
import re
import sys
from pathlib import Path

from app.artifacts.schema import CapabilityArtifact
from app.discovery.completion import verify_savings_balance
from app.replay.locators import resolve_locator
from app.replay.outcomes import detect_business_outcome
from app.replay.waits import (
    BusinessOutcomeDetected,
    LocatorTimeoutError,
    wait_for_control,
)
from app.surface.browser import BrowserSurface
from app.replay.checkpoints import verify_checkpoint


ARTIFACT_PATH = (
    "artifacts/banking.get_savings_balance.v1.json"
)

TARGET_URL = "http://mock-bank:8000"


def load_artifact(path: str) -> CapabilityArtifact:
    """
    Load and validate a saved capability artifact.
    """
    data = json.loads(Path(path).read_text())

    return CapabilityArtifact.model_validate(data)


def resolve_value(template: str, inputs: dict) -> str:
    """
    Replace a parameter placeholder with its
    corresponding runtime input value.
    """
    match = re.fullmatch(
        r"\{\{(\w+)\}\}",
        template,
    )

    if not match:
        raise ValueError(
            "Unsupported parameter template"
        )

    parameter = match.group(1)

    if parameter not in inputs:
        raise ValueError(
            f"Missing parameter: {parameter}"
        )

    return str(inputs[parameter])


async def run_replay(member_id: str) -> dict:
    """
    Execute the saved banking capability without
    invoking an LLM.

    Possible results:
    - success
    - business_outcome
    - failure
    """

    if not re.fullmatch(r"[0-9]{1,20}", member_id):
        raise ValueError(
            "Invalid member ID. Expected 1-20 digits."
        )

    artifact = load_artifact(ARTIFACT_PATH)

    if artifact.capability_id != "banking.get_savings_balance":
        raise ValueError(
            "Unexpected capability ID"
        )

    inputs = {
        "member_id": member_id,
    }

    surface = BrowserSurface()
    current_step = None

    try:
        await surface.start()
        await surface.navigate(TARGET_URL)

        for step in artifact.steps:
            current_step = step.step_id

            print(f"Executing: {current_step}")

            # Inspect the current application state.
            observation = await surface.observe()

            # Detect expected business outcomes before
            # attempting the next action.
            outcome = detect_business_outcome(
                page_text=observation["visible_text"],
                artifact=artifact,
            )

            if outcome is not None:
                return {
                    "status": "business_outcome",
                    "capability_id": artifact.capability_id,
                    "outcome": outcome,
                    "outputs": {},
                }

            # Execute interactive actions.
            if step.action in ("fill", "click"):

                if step.target is None:
                    raise ValueError(
                        f"Missing locator: {current_step}"
                    )

                locator = resolve_locator(
                    surface.page,
                    step.target,
                )

                # Wait for exactly one visible control.
                # Known business outcomes are detected
                # during the wait.
                await wait_for_control(
                    page=surface.page,
                    locator=locator,
                    artifact=artifact,
                    timeout=5.0,
                )

                if step.action == "fill":

                    if step.value is None:
                        raise ValueError(
                            f"Missing fill value: {current_step}"
                        )

                    value = resolve_value(
                        template=step.value,
                        inputs=inputs,
                    )

                    await locator.fill(
                        value,
                        timeout=5000,
                    )

                elif step.action == "click":

                    await locator.click(
                        timeout=5000,
                    )

                if step.checkpoint is not None:
                    await verify_checkpoint(
                        page=surface.page,
                        checkpoint=step.checkpoint,
                        inputs=inputs,
                        timeout_ms=5000,
                    )

            # Extract and verify requested information.
            elif step.action == "extract":

                page_text = await surface.page.locator(
                    "body"
                ).inner_text()

                outcome = detect_business_outcome(
                    page_text=page_text,
                    artifact=artifact,
                )

                if outcome is not None:
                    return {
                        "status": "business_outcome",
                        "capability_id": artifact.capability_id,
                        "outcome": outcome,
                        "outputs": {},
                    }

                if step.extraction is None:
                    raise ValueError(
                        "Missing extraction specification"
                    )

                # Apply the extraction rule stored
                # in the capability artifact.
                match = re.search(
                    step.extraction.pattern,
                    page_text,
                )

                if match is None:
                    raise RuntimeError(
                        "Savings balance extraction failed"
                    )

                extracted_balance = (
                    match.group(step.extraction.group)
                    .replace(",", "")
                )

                # Independently verify that the
                # balance belongs to the requested member.
                outputs = verify_savings_balance(
                    page_text=page_text,
                    member_id=member_id,
                )

                if outputs is None:
                    raise RuntimeError(
                        "Member ID or balance verification failed"
                    )

                if outputs["savings_balance"] != extracted_balance:
                    raise RuntimeError(
                        "Extracted balance verification mismatch"
                    )

                return {
                    "status": "success",
                    "capability_id": artifact.capability_id,
                    "outputs": outputs,
                }

            else:
                raise ValueError(
                    f"Unsupported action: {step.action}"
                )

        raise RuntimeError(
            "Replay ended without satisfying "
            "the success condition"
        )

    except BusinessOutcomeDetected as exc:
        return {
            "status": "business_outcome",
            "capability_id": artifact.capability_id,
            "outcome": exc.outcome,
            "outputs": {},
        }

    except LocatorTimeoutError as exc:
        return {
            "status": "failure",
            "capability_id": artifact.capability_id,
            "step": current_step,
            "error": {
                "type": "locator_timeout",
                "message": str(exc),
                "recoverable": True,
            },
        }

    except Exception as exc:
        return {
            "status": "failure",
            "capability_id": artifact.capability_id,
            "step": current_step,
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
                "recoverable": False,
            },
        }

    finally:
        await surface.close()


if __name__ == "__main__":

    member_id = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "12345"
    )

    result = asyncio.run(
        run_replay(member_id)
    )

    print("\nREPLAY RESULT:")
    print(json.dumps(result, indent=2))
