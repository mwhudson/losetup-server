#!/usr/bin/env python3
"""Client for losetup-server, intended as a drop-in replacement for losetup."""

import json
import os
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


def convert_paths(args: list[str]) -> list[str]:
    """Convert file paths to be relative to container root."""
    result = []
    for arg in args:
        if arg.startswith("-") or arg.startswith("/dev/"):
            result.append(arg)
        else:
            # Convert to absolute path, then strip leading slash
            abs_path = os.path.abspath(arg)
            result.append(abs_path[1:])
    return result


def main():
    gateway = get_default_gateway()
    server_url = f"http://{gateway}:{DEFAULT_PORT}"

    url = f"{server_url}/losetup"
    args = convert_paths(sys.argv[1:])
    data = json.dumps({"args": args}).encode()

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
