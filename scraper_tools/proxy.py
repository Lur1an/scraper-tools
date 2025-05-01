"""
Provides abstractions around proxies, including manually rotating proxies.
Automatically converts to known formats for mainstream librarires and provides defaults to read proxies both from files and environment variables.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import cycle
from typing import Literal, override

import httpx
from playwright.async_api import ProxySettings as PlaywrightProxy
from pydantic import ValidationError
from pydantic_core import Url
from pydantic_settings import BaseSettings

ProxyScheme = Literal["http", "socks5"]


class Proxy(ABC):
    """
    A utility class for proxy settings.
    Already implements formats for usual use cases: httpx, playwright, http url
    """

    @abstractmethod
    def playwright(self) -> PlaywrightProxy:
        raise NotImplementedError

    @abstractmethod
    def httpx(self) -> httpx.Proxy:
        """
        Returns a proxy object for the httpx library.
        """
        raise NotImplementedError

    @abstractmethod
    def url(self) -> Url:
        """
        Returns a generic url object for usage with various libraries like `requests`, `curl_cffi`, `hrequests`, etc...
        """
        raise NotImplementedError


@dataclass(slots=True)
class StaticProxy(Proxy):
    """
    A proxy configured with a specific target.
    """

    scheme: ProxyScheme
    host: str
    port: int
    username: str | None
    password: str | None

    @staticmethod
    def from_proxy_row(row: str, scheme: ProxyScheme = "http") -> "StaticProxy":
        """
        Creates a static proxy from a row in a standard proxy file.
        The format should be host:port:username:password
        """
        match row.split(":"):
            case [host, port, username, password]:
                return StaticProxy(
                    scheme=scheme,
                    host=host,
                    port=int(port),
                    username=username,
                    password=password,
                )
            case [host, port]:
                return StaticProxy(
                    scheme=scheme,
                    host=host,
                    port=int(port),
                    username=None,
                    password=None,
                )
            case _:
                raise ValueError(
                    "Invalid proxy row. Expected format should be: 'host:port:username:password' or 'host:port'"
                )

    @property
    def server(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"

    @override
    def playwright(self) -> PlaywrightProxy:
        return PlaywrightProxy(
            server=self.server,
            username=self.username,
            password=self.password,
        )

    @override
    def httpx(self) -> httpx.Proxy:
        return httpx.Proxy(
            self.server,
            auth=(self.username, self.password)
            if self.username and self.password
            else None,
        )

    @override
    def url(self) -> Url:
        return Url.build(
            scheme=self.scheme,
            host=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
        )


class RotatingProxy(Proxy):
    """
    An abstraction over a list of proxies which rotates through whilst implementing the `Proxy` interface.
    """

    def __init__(self, proxies: Iterable[StaticProxy]):
        self._proxies = cycle(proxies).__iter__()

    @override
    def playwright(self) -> PlaywrightProxy:
        return next(self._proxies).playwright()

    @override
    def httpx(self) -> httpx.Proxy:
        return next(self._proxies).httpx()

    @override
    def url(self) -> Url:
        return next(self._proxies).url()


class ProxyFile(BaseSettings):
    """
    Configuration to read multiple proxies from a proxy file.

    A proxy file is a text file that contains one proxy per line in the following format:
    host:port:username:password or host:port
    """

    PROXY_FILE_PATH: str
    PROXY_SCHEME: ProxyScheme = "http"

    def load(self) -> "RotatingProxy":
        proxies = []
        with open(self.PROXY_FILE_PATH) as f:
            for line in f:
                proxy = StaticProxy.from_proxy_row(line, self.PROXY_SCHEME)
                proxies.append(proxy)
        return RotatingProxy(proxies)


class ProxyEnv(BaseSettings):
    """
    Configuration for a single static proxy
    """

    PROXY_SERVER: str
    PROXY_SCHEME: ProxyScheme
    PROXY_PORT: int
    PROXY_USERNAME: str | None
    PROXY_PASSWORD: str | None

    def proxy(self) -> "StaticProxy":
        return StaticProxy(
            scheme=self.PROXY_SCHEME,
            host=self.PROXY_SERVER,
            port=self.PROXY_PORT,
            username=self.PROXY_USERNAME,
            password=self.PROXY_PASSWORD,
        )


def load_proxy_env() -> Proxy:
    """
    Loads a `Proxy` implementation from environment variables.
    """
    try:
        return ProxyFile().load()  # type: ignore
    except ValidationError:
        pass

    try:
        return ProxyEnv().proxy()  # type: ignore
    except ValidationError:
        pass

    raise Exception(
        "No proxy settings found. Provide either variables for `ProxyEnv` or for `ProxyFile`"
    )
