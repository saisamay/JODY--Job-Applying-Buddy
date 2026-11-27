"""One owner-selected HTTPS document per import. Validated same-site redirects only. No cookies or nested requests."""

import http.client
import ipaddress
import queue
import socket
import ssl
import threading
import time
from urllib.parse import urljoin, urlsplit

from fastapi import HTTPException

from ..config import private_preview

_dns_slots = threading.BoundedSemaphore(4)


def public_addresses(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    # Bound slow OS resolver calls as well as the number left running after timeout.
    result: queue.Queue[list[ipaddress.IPv4Address | ipaddress.IPv6Address]] = queue.Queue(
        maxsize=1
    )
    if not _dns_slots.acquire(blocking=False):
        raise HTTPException(503, "Resolver busy.")

    def resolve() -> None:
        try:
            result.put(
                [
                    ipaddress.ip_address(record[4][0])
                    for record in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
                ]
            )
        except (OSError, ValueError):
            result.put([])
        finally:
            _dns_slots.release()

    threading.Thread(target=resolve, daemon=True).start()
    try:
        return result.get(timeout=3)
    except queue.Empty:
        raise HTTPException(503, "Domain lookup timed out.") from None


def fetch(url: str, *, html: bool, redirects: int = 2, registry: bool = False) -> bytes:
    if private_preview():
        raise HTTPException(403, "External imports are disabled for this preview.")
    parts = urlsplit(url)
    host = parts.hostname
    if (
        parts.scheme != "https"
        or not host
        or parts.username
        or parts.password
        or parts.port not in {None, 443}
        or parts.query
        or parts.fragment
    ):
        raise HTTPException(422, "A public HTTPS document on port 443 is required.")
    connection = http.client.HTTPSConnection(host, timeout=5)
    try:
        ips = public_addresses(host)
        if not ips or any(
            not ip.is_global or ip.is_multicast or (ip.version == 6 and ip.is_site_local)
            for ip in ips
        ):
            raise HTTPException(422, "Source must resolve exclusively to public addresses.")
        # Connect to the validated numeric address. Verify TLS against the original hostname.
        with socket.create_connection((str(ips[0]), 443), timeout=5) as raw:
            connection.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
            connection.request(
                "GET",
                parts.path or "/",
                headers={
                    "Host": host,
                    "User-Agent": "JODY owner-requested source import",
                    "Accept-Encoding": "identity",
                },
            )
            response = connection.getresponse()
            if html and response.status in {301, 302, 303, 307, 308} and redirects > 0:
                target = urljoin(url, response.headers.get("Location", ""))
                other = urlsplit(target).hostname or ""
                if other.removeprefix("www.") != host.removeprefix("www.") or target == url:
                    raise HTTPException(422, "Portfolio redirect must stay on the selected site.")
                return fetch(target, html=True, redirects=redirects - 1)
            allowed = (
                {"text/html", "application/xhtml+xml"}
                if html
                else {"application/rdap+json", "application/json"}
                if registry
                else {"text/plain", "application/octet-stream"}
            )
            if response.status != 200 or response.headers.get_content_type() not in allowed:
                raise HTTPException(
                    422, "Source requires a directly accessible document or a manual snapshot."
                )
            data = bytearray()
            deadline = time.monotonic() + 10
            while chunk := response.read1(32768):
                data.extend(chunk)
                if len(data) > 512_000 or time.monotonic() > deadline:
                    raise HTTPException(413, "External source exceeds the import limit.")
            return bytes(data)
    except (OSError, ValueError, http.client.HTTPException):
        raise HTTPException(422, "Could not read this source securely.") from None
    finally:
        connection.close()
