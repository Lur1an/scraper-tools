"""
Provides abstractions around proxies, including manually rotating proxies.
Automatically converts to known formats for mainstream librarires and provides defaults to read proxies both from files and environment variables.
"""

import random
from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from itertools import cycle
from typing import Literal, override

import httpx
from playwright.async_api import ProxySettings as PlaywrightProxy
from pydantic import BaseModel, ValidationError
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

    @property
    def url_str(self) -> str:
        """
        Returns a string representation of the proxy url.
        """
        return str(self.url())


class StaticProxy(Proxy, BaseModel):
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
        match row.strip().split(":"):
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

    __slots__ = ("_proxies",)

    _proxies: Iterator[StaticProxy]

    def __init__(self, proxies: Iterable[StaticProxy]):
        self._proxies = cycle(proxies).__iter__()

    def __iter__(self) -> Iterator[StaticProxy]:
        """
        Returns an infinite iterator over the proxies in the rotation.
        """
        return self._proxies

    def __next__(self) -> StaticProxy:
        """
        Returns the next proxy in the rotation.
        """
        return next(self._proxies)

    @override
    def playwright(self) -> PlaywrightProxy:
        return next(self).playwright()

    @override
    def httpx(self) -> httpx.Proxy:
        return next(self).httpx()

    @override
    def url(self) -> Url:
        return next(self).url()


class ProxyFile(BaseSettings):
    """
    Configuration to read multiple proxies from a proxy file.
    Defaults to `http` scheme and `proxies.txt` file.

    A proxy file is a text file that contains one proxy per line in the following format:
    host:port:username:password or host:port
    """

    PROXY_FILE_PATH: str
    PROXY_SCHEME: ProxyScheme = "http"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def load(self) -> "list[StaticProxy]":
        proxies = []
        with open(self.PROXY_FILE_PATH) as f:
            for line in f:
                cleaned = line.strip()
                if cleaned:
                    proxies.append(
                        StaticProxy.from_proxy_row(cleaned, self.PROXY_SCHEME)
                    )
        if not proxies:
            raise ValueError("Proxy file is empty")
        return proxies


class ProxyEnv(BaseSettings):
    """
    Configuration for a single static proxy
    """

    PROXY_HOST: str
    PROXY_SCHEME: ProxyScheme
    PROXY_PORT: int
    PROXY_USERNAME: str | None = None
    PROXY_PASSWORD: str | None = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def proxy(self) -> "StaticProxy":
        return StaticProxy(
            scheme=self.PROXY_SCHEME,
            host=self.PROXY_HOST,
            port=self.PROXY_PORT,
            username=self.PROXY_USERNAME,
            password=self.PROXY_PASSWORD,
        )


def load_proxy_env() -> Proxy:
    """
    Loads a `Proxy` implementation from environment variables.
    Prefers `ProxyFile` if configured, otherwise falls back to `ProxyEnv`.

    When a `ProxyFile` is configured, it will load and turn all listed proxies into a `RotatingProxy`.
    """
    try:
        # Attempt to load ProxyFile first
        proxy_file_config = ProxyFile()
        proxies = proxy_file_config.load()
        random.shuffle(proxies)
        return RotatingProxy(proxies)
    except (ValidationError, FileNotFoundError):
        # If ProxyFile config is invalid or file not found, try ProxyEnv
        pass

    try:
        # Attempt to load ProxyEnv
        proxy_env_config = ProxyEnv()
        return proxy_env_config.proxy()
    except ValidationError:
        # If ProxyEnv config is also invalid, raise error
        pass

    raise Exception(
        "No valid proxy settings found. Provide either variables for `ProxyEnv` or for `ProxyFile`"
    )
