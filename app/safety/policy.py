
from urllib.parse import urlparse

from pydantic import BaseModel, Field


class PolicyViolation(PermissionError):
    """Raised when an action violates the safety policy."""


class SafetyPolicy(BaseModel):
    allowed_origin: str = "http://mock-bank:8000"

    allowed_paths: set[str] = Field(
        default_factory=lambda: {
            "/",
            "/search",
        }
    )

    allowed_path_prefixes: tuple[str, ...] = (
        "/members/",
    )

    allowed_actions: set[str] = Field(
        default_factory=lambda: {
            "navigate",
            "fill",
            "click",
            "extract",
        }
    )

    blocked_button_names: set[str] = Field(
        default_factory=lambda: {
            "Transfer Funds",
            "Delete Account",
            "Close Account",
            "Submit Payment",
            "Approve Transaction",
        }
    )

    def validate_url(self, url: str) -> None:
        """
        Validate scheme, origin, and route.
        """

        parsed = urlparse(url)
        allowed = urlparse(self.allowed_origin)

        if parsed.scheme != allowed.scheme:
            raise PolicyViolation(
                "URL scheme is not permitted"
            )

        if parsed.netloc != allowed.netloc:
            raise PolicyViolation(
                "External origin is not permitted"
            )

        if parsed.username or parsed.password:
            raise PolicyViolation(
                "URL credentials are not permitted"
            )

        path = parsed.path or "/"

        exact_match = path in self.allowed_paths

        prefix_match = any(
            path.startswith(prefix)
            for prefix in self.allowed_path_prefixes
        )

        if not (exact_match or prefix_match):
            raise PolicyViolation(
                "URL route is not permitted"
            )

    def validate_action(
        self,
        action: str,
        target_name: str | None = None,
    ) -> None:
        """
        Validate an action before execution.
        """

        if action not in self.allowed_actions:
            raise PolicyViolation(
                f"Action not permitted: {action}"
            )

        if target_name is not None:
            normalized = target_name.strip().casefold()

            blocked = {
                name.casefold()
                for name in self.blocked_button_names
            }

            if normalized in blocked:
                raise PolicyViolation(
                    "Risky action requires human approval"
                )
