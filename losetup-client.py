#!/usr/bin/env python3
"""Client for losetup-server, intended as a drop-in replacement for losetup."""

import json
import subprocess
import sys
import urllib.request
import urllib.error

DEFAULT_PORT = 12345


def get_default_gateway() -> str:
    """Get the default IPv4 gateway address."""
    result = subprocess.run(
        ["ip", "-j", "route", "show", "default"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get default route: {result.stderr}")

    routes = json.loads(result.stdout)
    if routes and "gateway" in routes[0]:
        return routes[0]["gateway"]

    raise RuntimeError("No default gateway found")


def main():
    gateway = get_default_gateway()
    server_url = f"http://{gateway}:{DEFAULT_PORT}"

    url = f"{server_url}/losetup"
    data = json.dumps({"args": sys.argv[1:]}).encode()

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read())
    except urllib.error.URLError as e:
        print(f"Error connecting to server: {e}", file=sys.stderr)
        sys.exit(1)

    if result.get("stdout"):
        print(result["stdout"], end="")
    if result.get("stderr"):
        print(result["stderr"], end="", file=sys.stderr)

    sys.exit(result.get("returncode", 1))


if __name__ == "__main__":
    main()
