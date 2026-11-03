
import argparse
import asyncio
import json
import os
import re

from pathlib import Path
from urllib.parse import urlparse

from app.discovery.agent import DiscoveryAgent
from app.discovery.completion import verify_savings_balance
from app.safety.guard import ActionGuard
from app.safety.navigation import install_navigation_guard
from app.safety.policy import SafetyPolicy
from app.surface.browser import BrowserSurface


DEFAULT_TARGET_URL = "http://mock-bank:8000"
DEFAULT_MEMBER_ID = "12345"
DEFAULT_MAX_STEPS = 10

ALLOWED_HOST = "mock-bank"

ALLOWED_ACTIONS = {
    "fill",
    "click",
    "extract",
    "finish",
    "blocked",
}


def check_url(url: str) -> None:
    """
    Validate the target application's URL.

    Discovery is restricted to the approved mock
    banking application.
    """
    parsed = urlparse(url)

    if (
        parsed.scheme != "http"
        or parsed.hostname != ALLOWED_HOST
        or parsed.port != 8000
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise PermissionError(
            "Target URL is not permitted"
        )


def validate_member_id(member_id: str) -> None:
    """
    Validate the member identifier.
    """
    if not re.fullmatch(r"[0-9]{1,20}", member_id):
        raise ValueError(
            "member_id must contain 1-20 digits"
        )


def save_discovery_evidence(
    result: dict,
    evidence_dir: Path,
) -> None:
    """
    Persist structured discovery evidence.
    """
    evidence_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    evidence_path = evidence_dir / "run.json"

    evidence_path.write_text(
        json.dumps(result, indent=2),
        encoding="utf-8",
    )


async def run_discovery(
    goal: str,
    member_id: str,
    max_steps: int = DEFAULT_MAX_STEPS,
    target_url: str | None = None,
    evidence_dir: str = "evidence/discovery",
) -> dict:
    """
    Run an LLM-driven observe-decide-act loop.

    The discovery agent:
      1. Observes the current browser state.
      2. Requests an action from the LLM.
      3. Validates the action against safety rules.
      4. Executes the action on the live UI.
      5. Records the interaction.
      6. Verifies successful completion.

    The resulting evidence can be converted into
    a reusable capability artifact.
    """

    validate_member_id(member_id)

    if not isinstance(goal, str) or not goal.strip():
        raise ValueError(
            "A non-empty natural-language goal is required"
        )

    if max_steps < 1:
        raise ValueError(
            "max_steps must be positive"
        )

    target_url = (
        target_url
        or os.getenv("TARGET_URL", DEFAULT_TARGET_URL)
    )

    check_url(target_url)

    evidence_path = Path(evidence_dir)

    surface = BrowserSurface()

    safety_policy = SafetyPolicy()
    action_guard = ActionGuard(safety_policy)

    agent = DiscoveryAgent()

    history = []
    extracted_data = []

    current_step = None

    try:
        await surface.start()

        # Install navigation protection before visiting
        # the target application.
        await install_navigation_guard(
            surface.page.context,
            safety_policy,
        )

        safety_policy.validate_url(target_url)

        await surface.navigate(target_url)

        for step_number in range(1, max_steps + 1):
            current_step = step_number

            # Observe the live application.
            observation = await surface.observe()

            check_url(observation["url"])
            safety_policy.validate_url(
                observation["url"]
            )

            # Ask the LLM what to do next.
            action = await agent.decide(
                goal=goal,
                observation=observation,
                history=history,
            )

            if action.action not in ALLOWED_ACTIONS:
                raise PermissionError(
                    "Discovery action is not permitted"
                )

            record = {
                "step": step_number,
                "url": observation["url"],
                "action": action.model_dump(),
            }

            # Capture a reusable locator before
            # interacting with the control.
            if action.action in ("fill", "click"):
                control_id = action.control_id

                if control_id is None:
                    raise ValueError(
                        "Missing control ID"
                    )

                controls = observation["controls"]

                if not 0 <= control_id < len(controls):
                    raise ValueError(
                        "Invalid control ID"
                    )

                record["locator"] = (
                    await surface.capture_locator(
                        control_id
                    )
                )

            print(
                f"\nDISCOVERY STEP {step_number}",
                flush=True,
            )

            print(
                json.dumps(record, indent=2),
                flush=True,
            )

            # Execute the selected action.
            if action.action == "fill":
                control = observation["controls"][
                    action.control_id
                ]

                if control["tag"] not in (
                    "input",
                    "textarea",
                ):
                    raise PermissionError(
                        "Target is not an input control"
                    )

                locator = surface.page.locator(
                    "input, button, a, select, textarea"
                ).nth(action.control_id)

                await action_guard.validate(
                    page=surface.page,
                    locator=locator,
                    action="fill",
                )

                # The recorded capability must be
                # parameterized for the requested member.
                if action.value != member_id:
                    raise ValueError(
                        "Discovery fill value does not "
                        "match the requested member ID"
                    )

                await surface.fill_control(
                    action.control_id,
                    action.value,
                )

            elif action.action == "click":
                control = observation["controls"][
                    action.control_id
                ]

                if control["tag"] not in (
                    "button",
                    "a",
                ):
                    raise PermissionError(
                        "Target is not clickable"
                    )

                locator = surface.page.locator(
                    "input, button, a, select, textarea"
                ).nth(action.control_id)

                await action_guard.validate(
                    page=surface.page,
                    locator=locator,
                    action="click",
                )

                await surface.click_control(
                    action.control_id
                )

                check_url(surface.page.url)

                safety_policy.validate_url(
                    surface.page.url
                )

            elif action.action == "extract":
                outputs = verify_savings_balance(
                    page_text=observation["visible_text"],
                    member_id=member_id,
                )

                if outputs is None:
                    raise RuntimeError(
                        "Extraction checkpoint failed: "
                        "member ID or balance not verified"
                    )

                extracted_data.append(
                    {
                        "url": observation["url"],
                        "outputs": outputs,
                    }
                )

                history.append(record)

                result = {
                    "status": "success",
                    "goal": goal,
                    "target_app": "mock-bank",
                    "target_url": target_url,
                    "steps": history,
                    "outputs": outputs,
                }

                save_discovery_evidence(
                    result,
                    evidence_path,
                )

                await surface.screenshot(
                    str(evidence_path / "final.png")
                )

                return result

            elif action.action == "finish":
                if not extracted_data:
                    raise RuntimeError(
                        "Cannot finish without "
                        "verified extraction"
                    )

                history.append(record)

                result = {
                    "status": "success",
                    "goal": goal,
                    "target_app": "mock-bank",
                    "target_url": target_url,
                    "steps": history,
                    "outputs": extracted_data[-1]["outputs"],
                    "extracted_data": extracted_data,
                }

                save_discovery_evidence(
                    result,
                    evidence_path,
                )

                await surface.screenshot(
                    str(evidence_path / "final.png")
                )

                return result

            elif action.action == "blocked":
                history.append(record)

                result = {
                    "status": "blocked",
                    "goal": goal,
                    "target_app": "mock-bank",
                    "target_url": target_url,
                    "steps": history,
                }

                save_discovery_evidence(
                    result,
                    evidence_path,
                )

                return result

            history.append(record)

        # Stop when the configured step limit is reached.
        result = {
            "status": "max_steps_exceeded",
            "goal": goal,
            "target_app": "mock-bank",
            "target_url": target_url,
            "steps": history,
        }

        save_discovery_evidence(
            result,
            evidence_path,
        )

        return result

    except Exception as exc:
        # Record failure metadata without persisting
        # arbitrary exception strings or credentials.
        result = {
            "status": "failure",
            "goal": goal,
            "target_app": "mock-bank",
            "target_url": target_url,
            "step": current_step,
            "error": {
                "type": type(exc).__name__,
                "message": "Discovery execution failed",
            },
            "steps": history,
        }

        save_discovery_evidence(
            result,
            evidence_path,
        )

        try:
            await surface.screenshot(
                str(evidence_path / "failure.png")
            )
        except Exception:
            pass

        raise

    finally:
        await surface.close()


def parse_arguments():
    """
    Parse command-line discovery inputs.
    """
    parser = argparse.ArgumentParser(
        description=(
            "LLM-driven browser workflow discovery"
        )
    )

    parser.add_argument(
        "--member-id",
        default=DEFAULT_MEMBER_ID,
        help="Member identifier (1-20 digits)",
    )

    parser.add_argument(
        "--goal",
        default=None,
        help="Natural-language discovery goal",
    )

    parser.add_argument(
        "--target-url",
        default=os.getenv(
            "TARGET_URL",
            DEFAULT_TARGET_URL,
        ),
        help="Approved target application URL",
    )

    parser.add_argument(
        "--max-steps",
        type=int,
        default=DEFAULT_MAX_STEPS,
        help="Maximum number of discovery steps",
    )

    parser.add_argument(
        "--evidence-dir",
        default="evidence/discovery",
        help="Directory for discovery evidence",
    )

    return parser.parse_args()


def main():
    args = parse_arguments()

    validate_member_id(args.member_id)

    if args.max_steps < 1:
        raise ValueError(
            "max_steps must be positive"
        )

    check_url(args.target_url)

    goal = args.goal or (
        f"Find member {args.member_id}, "
        "open their details, "
        "and read their savings balance."
    )

    result = asyncio.run(
        run_discovery(
            goal=goal,
            member_id=args.member_id,
            max_steps=args.max_steps,
            target_url=args.target_url,
            evidence_dir=args.evidence_dir,
        )
    )

    print("\nDISCOVERY RESULT:")

    print(
        json.dumps(result, indent=2)
    )


if __name__ == "__main__":
    main()
