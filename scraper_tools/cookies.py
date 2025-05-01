"""
Common utilities for working with cookies. e.g. converting from a playwright context to a httpx cookiejar.
"""

from collections.abc import Iterable

from playwright.async_api import BrowserContext, Cookie, Page


def convert_playwright_cookies(cookies: Iterable[Cookie]) -> list[tuple[str, str]]:
    converted: list[tuple[str, str]] = []
    for cookie in cookies:
        name = cookie.get("name")
        value = cookie.get("value")
        if name and value:
            converted.append((name, value))
    return converted


async def extract_cookies(pw: BrowserContext | Page) -> list[tuple[str, str]]:
    match pw:
        case BrowserContext():
            context = pw
        case Page():
            context = pw.context

    return convert_playwright_cookies(await context.cookies())
