
import asyncio

from app.discovery.agent import DiscoveryAgent
from app.surface.browser import BrowserSurface


async def main():
    surface = BrowserSurface()

    try:
        await surface.start()
        await surface.navigate("http://mock-bank:8000")

        observation = await surface.observe()

        agent = DiscoveryAgent()

        action = await agent.decide(
            goal=(
                "Find member 12345, open their details, "
                "and read their savings balance."
            ),
            observation=observation,
            history=[],
        )

        print("LLM DECISION:")
        print(action.model_dump_json(indent=2))

    finally:
        await surface.close()


if __name__ == "__main__":
    asyncio.run(main())
