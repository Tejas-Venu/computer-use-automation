
import asyncio
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from app.discovery.completion import verify_savings_balance
from app.discovery.agent import DiscoveryAgent
from app.surface.browser import BrowserSurface


ALLOWED_HOST = "mock-bank"
ALLOWED_ACTIONS = {"fill", "click", "extract", "finish", "blocked"}


def check_url(url: str):
    parsed = urlparse(url)

    if parsed.scheme != "http" or parsed.hostname != ALLOWED_HOST:
        raise PermissionError(f"URL not permitted: {url}")


async def run_discovery(goal: str, member_id: str, max_steps: int = 10,):
    if not member_id.isdigit():
        raise ValueError("member_id must contain only digits")

    if not 1 <= len(member_id) <= 20:
        raise ValueError("member_id must be 1-20 digits")
    surface = BrowserSurface()
    agent = DiscoveryAgent()
    history = []
    extracted_data = []
    evidence_dir = Path("evidence/discovery")
    evidence_dir.mkdir(parents=True, exist_ok=True)

    try:
        await surface.start()

        target_url = os.getenv(
            "TARGET_URL", "http://mock-bank:8000"
        )

        check_url(target_url)
        await surface.navigate(target_url)

        for step in range(1, max_steps + 1):
            observation = await surface.observe()
            check_url(observation["url"])

            action = await agent.decide(
                goal=goal,
                observation=observation,
                history=history,
            )

            if action.action not in ALLOWED_ACTIONS:
                raise PermissionError("Action not allowed")

            record = {
                "step": step,
                "url": observation["url"],
                "action": action.model_dump(),
            }

            if action.action in ("fill", "click"):
                control_id = action.control_id

                if control_id is None:
                    raise ValueError("Missing control ID")

                if not 0 <= control_id < len(
                    observation["controls"]
                ):
                    raise ValueError("Invalid control ID")

                record["locator"] = (
                    await surface.capture_locator(control_id)
                )

            print(f"\nSTEP {step}")
            print(json.dumps(record, indent=2))

            if action.action == "fill":
                control = observation["controls"][
                    action.control_id
                ]

                if control["tag"] not in ("input", "textarea"):
                    raise PermissionError("Not an input control")

                await surface.fill_control(
                    action.control_id,
                    action.value,
                )

            elif action.action == "click":
                control = observation["controls"][
                    action.control_id
                ]

                if control["tag"] not in ("button", "a"):
                    raise PermissionError("Not a clickable control")

                await surface.click_control(action.control_id)
                check_url(surface.page.url)

            
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

                extracted_data.append({
                    "url": observation["url"],
                    "outputs": outputs,
                })

                history.append(record)

                result = {
                    "status": "success",
                    "goal": goal,
                    "steps": history,
                    "outputs": outputs,
                }

                (evidence_dir / "run.json").write_text(
                    json.dumps(result, indent=2)
                )

                await surface.screenshot(
                    str(evidence_dir / "final.png")
                )

                return result


            elif action.action == "finish":
                if not extracted_data:
                    raise RuntimeError(
                        "Cannot finish without extraction"
                    )

                history.append(record)

                result = {
                    "status": "success",
                    "goal": goal,
                    "steps": history,
                    "extracted_data": extracted_data,
                }

                (evidence_dir / "run.json").write_text(
                    json.dumps(result, indent=2)
                )

                await surface.screenshot(
                    str(evidence_dir / "final.png")
                )

                return result

            elif action.action == "blocked":
                history.append(record)

                result = {
                    "status": "blocked",
                    "goal": goal,
                    "steps": history,
                }

                (evidence_dir / "run.json").write_text(
                    json.dumps(result, indent=2)
                )

                return result

            history.append(record)

        result = {
            "status": "max_steps_exceeded",
            "goal": goal,
            "steps": history,
        }

        (evidence_dir / "run.json").write_text(
            json.dumps(result, indent=2)
        )

        return result

    finally:
        await surface.close()


if __name__ == "__main__":
    member_id = "12345"

    goal = (
        f"Find member {member_id}, open their details, "
        "and read their savings balance."
    )

    result = asyncio.run(
        run_discovery(
            goal=goal,
            member_id=member_id,
        )
    )

    print("\nFINAL RESULT:")
    print(json.dumps(result, indent=2))

