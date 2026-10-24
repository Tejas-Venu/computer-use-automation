
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.async_api import Page


EVIDENCE_ROOT = Path("evidence/replay")

SENSITIVE_KEYS = {
    "password",
    "token",
    "secret",
    "authorization",
    "cookie",
    "account_number",
    "member_id",
    "savings_balance",
}



def sanitize(data: Any) -> Any:
    """
    Redact known sensitive fields and common
    credential patterns from structured evidence.
    """

    if isinstance(data, dict):
        result = {}

        for key, value in data.items():
            normalized = str(key).lower()

            if (
                normalized in SENSITIVE_KEYS
                or any(
                    word in normalized
                    for word in (
                        "password",
                        "secret",
                        "token",
                        "authorization",
                        "cookie",
                    )
                )
            ):
                result[key] = "[REDACTED]"
            else:
                result[key] = sanitize(value)

        return result

    if isinstance(data, list):
        return [sanitize(item) for item in data]

    if isinstance(data, str):
        data = re.sub(
            r"(?i)\b(bearer)\s+\S+",
            r"\1 [REDACTED]",
            data,
        )

        data = re.sub(
            r"(?i)\b(password|token|secret)\s*[:=]\s*\S+",
            r"\1=[REDACTED]",
            data,
        )

        return data

    return data



class ReplayEvidence:
    def __init__(self):
        self.run_id = uuid.uuid4().hex
        self.directory = EVIDENCE_ROOT / self.run_id
        self.directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.events: list[dict] = []

    def record(
        self,
        event_type: str,
        step: str | None = None,
        details: dict | None = None,
    ):
        event = {
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "event": event_type,
            "step": step,
            "details": sanitize(details or {}),
        }

        self.events.append(event)

    def save(self, result: dict):
        payload = {
            "run_id": self.run_id,
            "events": self.events,
            "result": sanitize(result),
        }

        path = self.directory / "run.json"

        path.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

        return path

    async def capture_failure(
        self,
        page: Page,
    ) -> Path:
        """
        Capture failure evidence from the live browser.

        Screenshots are restricted to the fictional
        mock banking application.
        """

        if not re.fullmatch(
            r"http://mock-bank:8000(?:/.*)?",
            page.url,
        ):
            raise PermissionError(
                "Screenshots are restricted to mock-bank"
            )

        path = self.directory / "failure.png"

        await page.screenshot(
            path=str(path),
            full_page=True,
        )

        return path
