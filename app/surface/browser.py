
from pathlib import Path
from playwright.async_api import async_playwright


class BrowserSurface:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None

    async def start(self):
        self.playwright = await async_playwright().start()

        self.browser = await self.playwright.chromium.launch(
            headless=True
        )

        self.page = await self.browser.new_page()

    async def navigate(self, url: str):
        await self.page.goto(url, wait_until="domcontentloaded")

    
    
    async def observe(self) -> dict:
        controls = await self.page.locator(
            "input, button, a, select, textarea"
        ).evaluate_all("""
            elements => elements.map((el, index) => ({
                control_id: index,
                tag: el.tagName.toLowerCase(),
                text: el.innerText || el.value || "",
                name: el.getAttribute("name"),
                type: el.getAttribute("type"),
                placeholder: el.getAttribute("placeholder")
            }))
        """)

        return {
            "url": self.page.url,
            "title": await self.page.title(),
            "visible_text": await self.page.locator(
                "body"
            ).inner_text(),
            "controls": controls,
        }


    async def click_control(self, control_id: int):
        controls = self.page.locator(
            "input, button, a, select, textarea"
        )

        count = await controls.count()

        if not 0 <= control_id < count:
            raise ValueError("Invalid control_id")

        await controls.nth(control_id).click(timeout=5000)

    async def fill_control(self, control_id: int, value: str):
        controls = self.page.locator(
            "input, button, a, select, textarea"
        )

        count = await controls.count()

        if not 0 <= control_id < count:
            raise ValueError("Invalid control_id")

        await controls.nth(control_id).fill(
            value,
            timeout=5000
        )


    async def capture_locator(self, control_id: int) -> dict:
        controls = self.page.locator(
            "input, button, a, select, textarea"
        )

        count = await controls.count()

        if not 0 <= control_id < count:
            raise ValueError("Invalid control_id")

        element = controls.nth(control_id)

        info = await element.evaluate("""
            el => ({
                tag: el.tagName.toLowerCase(),
                name: el.getAttribute("name"),
                type: el.getAttribute("type"),
                text: (el.innerText || "").trim(),
                aria_label: el.getAttribute("aria-label")
            })
        """)

        if info["tag"] == "input" and info["name"]:
            locator = {
                "strategy": "attribute",
                "tag": "input",
                "attribute": "name",
                "value": info["name"],
            }

            candidate = self.page.locator(
                f'input[name="{info["name"]}"]'
            )

        elif info["tag"] == "button":
            name = info["aria_label"] or info["text"]

            locator = {
                "strategy": "role",
                "role": "button",
                "name": name,
            }

            candidate = self.page.get_by_role(
                "button", name=name, exact=True
            )

        elif info["tag"] == "a":
            name = info["aria_label"] or info["text"]

            locator = {
                "strategy": "role",
                "role": "link",
                "name": name,
            }

            candidate = self.page.get_by_role(
                "link", name=name, exact=True
            )

        else:
            raise ValueError(
                "No supported stable locator for control"
            )

        if await candidate.count() != 1:
            raise ValueError(
                "Locator is not unique"
            )

        return locator


    async def click(self, selector: str):
        await self.page.locator(selector).click(timeout=5000)

    async def fill(self, selector: str, value: str):
        await self.page.locator(selector).fill(value, timeout=5000)

    async def extract(self, selector: str) -> str:
        return await self.page.locator(selector).inner_text()

    async def screenshot(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        await self.page.screenshot(path=path)

    async def close(self):
        if self.browser:
            await self.browser.close()

        if self.playwright:
            await self.playwright.stop()
