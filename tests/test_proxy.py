import tempfile

import pytest

from scraper_tools.proxy import (
    ProxyEnv,
    ProxyFile,
    RotatingProxy,
    StaticProxy,
    load_proxy_env,
)


def test_static_proxy_from_proxy_row():
    row1 = "host1:1234:user1:pass1"
    proxy1 = StaticProxy.from_proxy_row(row1, scheme="http")
    assert proxy1.scheme == "http"
    assert proxy1.host == "host1"
    assert proxy1.port == 1234
    assert proxy1.username == "user1"
    assert proxy1.password == "pass1"

    row2 = "host2:5678"
    proxy2 = StaticProxy.from_proxy_row(row2, scheme="socks5")
    assert proxy2.scheme == "socks5"
    assert proxy2.host == "host2"
    assert proxy2.port == 5678
    assert proxy2.username is None
    assert proxy2.password is None

    with pytest.raises(ValueError, match="Invalid proxy row"):
        StaticProxy.from_proxy_row("invalid_format")

    with pytest.raises(ValueError, match="Invalid proxy row"):
        StaticProxy.from_proxy_row("host:port:user")

    # Test stripping of whitespace
    row3 = "  host3:9000:user3:pass3\n  "
    proxy3 = StaticProxy.from_proxy_row(row3.strip(), scheme="http")
    assert proxy3.host == "host3"
    assert proxy3.port == 9000
    assert proxy3.username == "user3"
    assert proxy3.password == "pass3"


def test_proxy_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PROXY_HOST", "proxy.example.com")
    monkeypatch.setenv("PROXY_SCHEME", "http")
    monkeypatch.setenv("PROXY_PORT", "8080")
    monkeypatch.setenv("PROXY_USERNAME", "testuser")
    monkeypatch.setenv("PROXY_PASSWORD", "testpass")

    proxy_env = ProxyEnv()  # type: ignore
    static_proxy = proxy_env.proxy()

    assert isinstance(static_proxy, StaticProxy)
    assert static_proxy.scheme == "http"
    assert static_proxy.host == "proxy.example.com"
    assert static_proxy.port == 8080
    assert static_proxy.username == "testuser"
    assert static_proxy.password == "testpass"


def test_proxy_file(monkeypatch: pytest.MonkeyPatch):
    proxy_data = [
        "host1.com:1111:user1:pass1",
        "host2.com:2222",
        "host3.com:3333:user3:pass3",
        "  host4.com:4444:user4:pass4  ",  # Test whitespace stripping
        "",  # Test empty line skipping
        "host5.com:5555",
    ]
    expected_proxies = [
        StaticProxy(
            scheme="socks5",
            host="host1.com",
            port=1111,
            username="user1",
            password="pass1",
        ),
        StaticProxy(
            scheme="socks5", host="host2.com", port=2222, username=None, password=None
        ),
        StaticProxy(
            scheme="socks5",
            host="host3.com",
            port=3333,
            username="user3",
            password="pass3",
        ),
        StaticProxy(
            scheme="socks5",
            host="host4.com",
            port=4444,
            username="user4",
            password="pass4",
        ),
        StaticProxy(
            scheme="socks5", host="host5.com", port=5555, username=None, password=None
        ),
    ]

    with tempfile.NamedTemporaryFile(mode="w") as tmp_file:
        tmp_file.write("\n".join(proxy_data))
        tmp_file.flush()

        monkeypatch.setenv("PROXY_FILE_PATH", tmp_file.name)
        monkeypatch.setenv("PROXY_SCHEME", "socks5")

        proxy_file = ProxyFile()  # type: ignore
        rotating_proxy = proxy_file.load()

    assert isinstance(rotating_proxy, RotatingProxy)

    for proxy in expected_proxies:
        assert proxy in rotating_proxy._proxies

    # Check rotation by getting the next one (should be the first one again)
    assert next(rotating_proxy._proxies) == expected_proxies[0]


def test_proxy_file_not_found(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PROXY_FILE_PATH", "non_existent_file.txt")
    monkeypatch.setenv("PROXY_SCHEME", "http")

    proxy_file = ProxyFile()  # type: ignore

    with pytest.raises(FileNotFoundError):
        proxy_file.load()


def test_load_proxy_env_from_proxy_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PROXY_HOST", "env.proxy.com")
    monkeypatch.setenv("PROXY_SCHEME", "http")
    monkeypatch.setenv("PROXY_PORT", "8888")
    monkeypatch.setenv("PROXY_USERNAME", "envuser")
    monkeypatch.setenv("PROXY_PASSWORD", "envpass")

    proxy = load_proxy_env()
    assert isinstance(proxy, StaticProxy)
    assert proxy.host == "env.proxy.com"
    assert proxy.port == 8888
    assert proxy.username == "envuser"
    assert proxy.password == "envpass"


def test_load_proxy_env_from_proxy_file(monkeypatch: pytest.MonkeyPatch):
    proxy_data = ["file.proxy.com:9999:fileuser:filepass"]
    expected_proxy = StaticProxy.from_proxy_row(proxy_data[0], scheme="http")

    with tempfile.NamedTemporaryFile(mode="w") as tmp_file:
        tmp_file.write("\n".join(proxy_data))
        tmp_file.flush()

        monkeypatch.setenv("PROXY_FILE_PATH", tmp_file.name)
        monkeypatch.setenv("PROXY_SCHEME", "http")

        proxy = load_proxy_env()

    assert isinstance(proxy, RotatingProxy)
    loaded_proxy = next(proxy)
    assert loaded_proxy == expected_proxy

    # Check that the next proxy wraps around correctly
    assert next(proxy) == expected_proxy


def test_load_proxy_env_no_vars():
    with pytest.raises(Exception, match="No valid proxy settings found"):
        load_proxy_env()
