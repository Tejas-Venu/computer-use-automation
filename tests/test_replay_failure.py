
import json

import pytest

from app.replay.engine import run_replay


@pytest.mark.asyncio
async def test_replay_failure_creates_evidence(
    tmp_path,
    monkeypatch,
):
    import app.replay.evidence as evidence_module

    monkeypatch.setattr(
        evidence_module,
        "EVIDENCE_ROOT",
        tmp_path / "evidence",
    )

    with open(
        "artifacts/banking.get_savings_balance.v1.json"
    ) as file:
        artifact = json.load(file)

    # Intentionally break the Search button locator.
    artifact["steps"][1]["target"] = {
        "strategy": "role",
        "role": "button",
        "name": "Nonexistent Search Button",
    }

    temporary_artifact = tmp_path / "broken.json"

    temporary_artifact.write_text(
        json.dumps(artifact)
    )

    result = await run_replay(
        member_id="12345",
        artifact_path=str(temporary_artifact),
    )

    assert result["status"] == "failure"
    assert result["step"] == "submit_search"
    assert result["error"]["type"] == "locator_timeout"

    runs = list(
        (tmp_path / "evidence").glob("*")
    )

    assert len(runs) == 1

    run_directory = runs[0]

    assert (run_directory / "run.json").exists()
    assert (run_directory / "failure.png").exists()

    evidence = json.loads(
        (run_directory / "run.json").read_text()
    )

    assert evidence["result"]["status"] == "failure"

    events = [
        event["event"]
        for event in evidence["events"]
    ]

    assert "step_failed" in events
    assert "failure_screenshot_saved" in events
