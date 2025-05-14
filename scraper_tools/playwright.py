from collections.abc import Awaitable, Sequence
from typing import Callable, Literal

from playwright.async_api import Page, Request, Route

ResourceType = Literal[
    "document",
    "stylesheet",
    "image",
    "media",
    "font",
    "script",
    "texttrack",
    "xhr",
    "fetch",
    "eventsource",
    "websocket",
    "manifest",
    "other",
]

ResourceRule = tuple[ResourceType, Callable[[Request], Awaitable[bool]]]

LIGHT_BLOCK_PRESET: list[ResourceType] = [
    "document",
    "stylesheet",
    "image",
    "media",
    "font",
    "texttrack",
]


async def block_resources(
    page: Page, *, resources: Sequence[ResourceType] = LIGHT_BLOCK_PRESET
):
    async def route(route: Route, request: Request):
        if request.resource_type in resources:
            await route.abort()
        else:
            await route.continue_()

    await page.route("**/*", route)
