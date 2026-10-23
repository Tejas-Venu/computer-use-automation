
import asyncio
from app.surface.browser import BrowserSurface


async def main():
    surface = BrowserSurface()

    try:
        await surface.start()

        await surface.navigate("http://mock-bank:8000")

        print("INITIAL OBSERVATION:")
        print(await surface.observe())

        await surface.fill(
            'input[name="member_id"]',
            "12345"
        )

        await surface.click('button[type="submit"]')

        print("\nSEARCH RESULTS:")
        print(await surface.observe())

        await surface.click('a[href="/members/12345"]')

        print("\nMEMBER DETAILS:")
        print(await surface.observe())

        await surface.screenshot(
            "evidence/browser_test.png"
        )

        print("\nScreenshot saved successfully!")

    finally:
        await surface.close()


if __name__ == "__main__":
    asyncio.run(main())
