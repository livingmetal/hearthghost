"""Container health probe for the loopback-only Core liveness endpoint."""

from __future__ import annotations

import json
from http.client import HTTPConnection


def main() -> int:
    connection = HTTPConnection("127.0.0.1", 8080, timeout=2)
    try:
        connection.request("GET", "/health/live")
        response = connection.getresponse()
        payload = json.load(response)
        healthy = response.status == 200 and payload.get("status") == "alive"
        return 0 if healthy else 1
    except Exception:
        return 1
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
