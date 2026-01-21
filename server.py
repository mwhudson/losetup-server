#!/usr/bin/env python3
"""Simple HTTP API server using Flask."""

import argparse
import glob
import json
import os
import subprocess
import sys

from flask import Flask, jsonify, request


def get_container_bridge(container: str) -> str:
    """Get the bridge interface the container is attached to."""
    result = subprocess.run(
        ["lxc", "query", f"/1.0/instances/{container}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to query container: {result.stderr}")

    config = json.loads(result.stdout)
    devices = config.get("expanded_devices", {})

    for device in devices.values():
        if device.get("type") == "nic":
            network = device.get("network")
            if network:
                return network

    raise RuntimeError("No network device with parent found for container")


def get_interface_ip(interface: str) -> str:
    """Get the IPv4 address of a network interface."""
    result = subprocess.run(
        ["ip", "-j", "addr", "show", interface],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get interface info: {result.stderr}")

    data = json.loads(result.stdout)
    for iface in data:
        for addr_info in iface.get("addr_info", []):
            if addr_info.get("family") == "inet":
                return addr_info.get("local")

    raise RuntimeError(f"No IPv4 address found for interface {interface}")


app = Flask(__name__)
container_name = None
container_rootfs = None


@app.route("/losetup", methods=["POST"])
def losetup():
    """Run losetup with the provided arguments."""
    data = request.get_json()
    if data is None:
        return jsonify({"error": "Expected JSON body"}), 400

    args = data.get("args", [])
    if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        return jsonify({"error": "args must be a list of strings"}), 400

    print(f"Received args: {args}", file=sys.stderr)

    # Check if --show is in the args
    has_show = "--show" in args

    # Find the last positional argument (not an option, not a device path)
    # and prepend container_rootfs to it
    args = list(args)  # copy to avoid modifying original
    for i in range(len(args) - 1, -1, -1):
        arg = args[i]
        if not arg.startswith("-") and not arg.startswith("/dev/"):
            args[i] = os.path.join(container_rootfs, arg)
            break

    cmd = ["losetup"] + args
    print(f"Running: {cmd}", file=sys.stderr)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    response = {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }

    # If --show was used and losetup succeeded, add the device to the container
    if has_show and result.returncode == 0:
        device_path = result.stdout.strip()
        if device_path.startswith("/dev/"):
            # Collect all devices to add: the main device plus any partitions
            devices_to_add = [device_path]
            partition_devices = sorted(glob.glob(f"{device_path}p[0-9]*"))
            devices_to_add.extend(partition_devices)

            for dev_path in devices_to_add:
                device_name = os.path.basename(dev_path)
                print(f"Adding device {dev_path} to container {container_name}", file=sys.stderr)
                subprocess.run(
                    [
                        "lxc", "config", "device", "add",
                        container_name,
                        device_name,
                        "unix-block",
                        f"source={dev_path}",
                        f"path={dev_path}",
                    ],
                    capture_output=True,
                )

    return jsonify(response)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simple HTTP API server")
    parser.add_argument("--port", type=int, default=12345, help="Port to listen on")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument(
        "container",
        help="Name of the LXD container",
    )
    args = parser.parse_args()

    container_name = args.container
    container_rootfs = (
        f"/var/snap/lxd/common/lxd/storage-pools/default/containers"
        f"/{container_name}/rootfs"
    )

    bridge = get_container_bridge(container_name)
    host = get_interface_ip(bridge)
    print(f"Container {container_name} is on bridge {bridge}, listening on {host}")

    app.run(host=host, port=args.port, debug=args.debug)
