
import json

from app.replay.evidence import (
    ReplayEvidence,
    sanitize,
)


def test_sensitive_data_redaction():
    data = {
        "member_id": "12345",
        "password": "secret123",
        "status": "failure",
        "nested": {
            "token": "abc123",
        },
    }

    result = sanitize(data)

    assert result["member_id"] == "[REDACTED]"
    assert result["password"] == "[REDACTED]"
    assert result["nested"]["token"] == "[REDACTED]"
    assert result["status"] == "failure"


def test_evidence_recording(tmp_path, monkeypatch):
    import app.replay.evidence as evidence_module

    monkeypatch.setattr(
        evidence_module,
        "EVIDENCE_ROOT",
        tmp_path,
    )

    recorder = ReplayEvidence()

    recorder.record(
        event_type="step_failed",
        step="open_details",
        details={
            "error_type": "locator_timeout",
            "member_id": "12345",
        },
    )

    path = recorder.save({
        "status": "failure",
        "member_id": "12345",
    })

    payload = json.loads(path.read_text())

    assert payload["result"]["status"] == "failure"
    assert payload["result"]["member_id"] == "[REDACTED]"

    assert (
        payload["events"][0]["details"]["member_id"]
        == "[REDACTED]"
    )

    assert payload["events"][0]["step"] == "open_details"


def test_unique_run_directories(tmp_path, monkeypatch):
    import app.replay.evidence as evidence_module

    monkeypatch.setattr(
        evidence_module,
        "EVIDENCE_ROOT",
        tmp_path,
    )

    first = ReplayEvidence()
    second = ReplayEvidence()

    assert first.run_id != second.run_id
    assert first.directory != second.directory
