#!/usr/bin/env python3
"""A tiny HTTP endpoint exposing this host's current clock and timezone."""

import json
import ipaddress
import os
import socket
import struct
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

NTP_EPOCH = 2_208_988_800
ALLOWED_NETWORKS = tuple(
    ipaddress.ip_network(value.strip())
    for value in os.environ.get(
        "ALLOWED_NETWORKS", "150.164.110.0/24,150.164.111.0/24,192.168.137.0/24"
    ).split(",")
    if value.strip()
)


def client_allowed(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
        return any(ip in network for network in ALLOWED_NETWORKS)
    except ValueError:
        return False


def ntp_timestamp(now: float) -> bytes:
    seconds = int(now) + NTP_EPOCH
    fraction = int((now - int(now)) * (1 << 32))
    return struct.pack("!II", seconds & 0xFFFFFFFF, fraction)


def serve_ntp(host: str, port: int) -> None:
    """Serve basic NTP client requests (UDP mode 3) with server replies (mode 4)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((host, port))
        print(f"Serving NTP on {host}:{port}/udp", flush=True)
        while True:
            request, peer = sock.recvfrom(512)
            if not client_allowed(peer[0]):
                print(
                    f"Rejected NTP request from {peer[0]}:{peer[1]} "
                    "reason=source_not_allowed",
                    flush=True,
                )
                continue
            if len(request) < 48:
                print(
                    f"Rejected NTP request from {peer[0]}:{peer[1]} "
                    f"reason=packet_too_short bytes={len(request)}",
                    flush=True,
                )
                continue

            first = request[0]
            version = (first >> 3) & 0x7
            mode = first & 0x7
            if mode != 3 or version not in (3, 4):
                print(
                    f"Rejected NTP request from {peer[0]}:{peer[1]} "
                    f"reason=unsupported_version_or_mode version={version} mode={mode}",
                    flush=True,
                )
                continue

            now = time.time()
            # LI=0, retain the client's NTP version, server mode=4.
            response = bytearray(48)
            response[0] = (version << 3) | 4
            # Local system clock reference (LI is clear while it is usable).
            response[1] = 1  # Stratum 1, reference ID below identifies the local clock.
            response[2] = 6  # Poll interval (2**6 seconds).
            response[3] = -20 & 0xFF  # Precision, approximately one microsecond.
            response[12:16] = b"LOCL"
            response[16:24] = ntp_timestamp(now)  # Reference timestamp
            response[24:32] = request[40:48]  # Originate: client's transmit time
            response[32:40] = ntp_timestamp(now)  # Receive timestamp
            response[40:48] = ntp_timestamp(time.time())  # Transmit timestamp
            sock.sendto(response, peer)


def timezone_name(local_time: datetime) -> str:
    """Return an IANA timezone name where the host provides one."""
    configured = os.environ.get("TZ", "").lstrip(":")
    if configured:
        try:
            ZoneInfo(configured)
            return configured
        except ZoneInfoNotFoundError:
            pass

    for filename in ("/etc/timezone",):
        try:
            name = Path(filename).read_text().strip()
            if name:
                return name
        except OSError:
            pass

    try:
        target = Path("/etc/localtime").resolve()
        marker = "/zoneinfo/"
        if marker in str(target):
            return str(target).split(marker, 1)[1]
    except OSError:
        pass

    return getattr(local_time.tzinfo, "key", None) or str(local_time.tzinfo)


class TimeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Port 8080 is internal-only; Caddy supplies the originating client IP.
        forwarded_for = self.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
        client_ip = forwarded_for or self.client_address[0]
        if not client_allowed(client_ip):
            self.send_error(403, "Forbidden")
            return
        if self.path not in ("/", "/time", "/api/time"):
            self.send_error(404, "Not found")
            return

        utc_now = datetime.now(timezone.utc)
        local_now = utc_now.astimezone()
        payload = {
            "timestamp": utc_now.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "unix_time": time.time(),
            "timezone": timezone_name(local_now),
            "local_time": local_now.isoformat(timespec="milliseconds"),
            "utc_offset": local_now.strftime("%z"),
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"{self.client_address[0]} - {fmt % args}", flush=True)


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    http_port = int(os.environ.get("PORT", "8080"))
    ntp_port = int(os.environ.get("NTP_PORT", "123"))
    threading.Thread(target=serve_ntp, args=(host, ntp_port), daemon=True).start()
    print(f"Serving time API on {host}:{http_port}", flush=True)
    ThreadingHTTPServer((host, http_port), TimeHandler).serve_forever()
