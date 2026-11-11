"""Bounded readiness checks shared by the local development tools."""

import socket
import time
from urllib.error import URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen


def http_ready(url, headers=None):
    try:
        with urlopen(Request(url, headers=headers or {}), timeout=3) as response:
            return response.status == 200
    except (OSError, URLError):
        return False


def tcp_ready(address):
    parsed = urlparse(f"//{address}")
    if not parsed.hostname or not parsed.port:
        raise ValueError(f"Expected host:port, got {address!r}")
    try:
        with socket.create_connection((parsed.hostname, parsed.port), timeout=1):
            return True
    except OSError:
        return False


def wait_until(probe, timeout=120, interval=1):
    deadline = time.monotonic() + timeout
    while True:
        if probe():
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(interval, remaining))


def check_redis_ready(host, port, password=None, max_retries=5, retry_delay=3, username=None):
    for attempt in range(max_retries):
        try:
            with socket.create_connection((host, port), timeout=3) as sock:
                with sock.makefile("rb") as response:
                    def send(*parts):
                        encoded = [str(part).encode("utf-8") for part in parts]
                        request = f"*{len(encoded)}\r\n".encode()
                        for part in encoded:
                            request += f"${len(part)}\r\n".encode() + part + b"\r\n"
                        sock.sendall(request)
                        return response.readline(4096).decode("utf-8", errors="replace").strip()

                    if password:
                        reply = send("AUTH", username, password) if username else send("AUTH", password)
                        if reply != "+OK":
                            return False, "auth_failed", reply
                    reply = send("PING")
                    if reply == "+PONG":
                        return True, "", ""
                    return False, "auth_failed", reply
        except OSError:
            if attempt + 1 < max_retries:
                time.sleep(retry_delay)
    return False, "not_ready", ""


def redis_readiness_check(memory_backend, redis_url):
    if memory_backend == "memory":
        return True, ""
    if memory_backend != "redis":
        print(f"ERROR: Unknown AE_MEMORY_BACKEND: {memory_backend}")
        return False, "config_error"
    parsed = urlparse(redis_url)
    if parsed.scheme != "redis" or not parsed.hostname or not parsed.password:
        print("ERROR: AE_MEMORY_REDIS_URL must be an authenticated redis:// URL.")
        return False, "config_error"
    ready, error, _ = check_redis_ready(
        parsed.hostname, parsed.port or 6379, unquote(parsed.password),
        username=unquote(parsed.username) if parsed.username else None,
    )
    if not ready:
        print(f"ERROR: Agent Redis check failed: {error}")
    return ready, error
