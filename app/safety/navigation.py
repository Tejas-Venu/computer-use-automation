
from playwright.async_api import BrowserContext, Route

from app.safety.policy import (
    PolicyViolation,
    SafetyPolicy,
)


async def install_navigation_guard(
    context: BrowserContext,
    policy: SafetyPolicy,
) -> None:
    """
    Enforce URL restrictions on browser requests.

    Track blocked requests for later error classification.
    """

    blocked_requests: list[dict[str, str]] = []

    async def handle_route(route: Route):
        request = route.request

        try:
            policy.validate_url(request.url)

        except PolicyViolation:
            blocked_requests.append({
                "reason": "url_not_allowed",
                "resource_type": request.resource_type,
            })

            await route.abort(
                error_code="blockedbyclient"
            )
            return

        await route.continue_()

    await context.route("**/*", handle_route)

    # Per-context diagnostics, without storing raw URLs.
    setattr(
        context,
        "_blocked_requests",
        blocked_requests,
    )
