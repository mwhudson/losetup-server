#!/usr/bin/env python3
# Copyright (C) Canonical Ltd.
# SPDX-License-Identifier: GPL-3.0-only
"""
Wrapper for mount that uses losetup to set up loop devices.

When mount would normally set up a loop device itself (e.g., mount -o loop),
this wrapper uses losetup explicitly instead, allowing the losetup-client
to handle loop device creation via the losetup-server.
"""

import os
import subprocess
import sys

REAL_MOUNT = "/usr/bin/mount.REAL"
LOSETUP = "losetup"


def parse_mount_args(args: list[str]) -> tuple[dict, list[str], str | None, str | None]:
    """
    Parse mount arguments to extract options, flags, source, and target.

    Returns:
        (options_dict, flags, source, target)
    """
    options = {}
    flags = []
    positional = []

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-o", "--options"):
            if i + 1 < len(args):
                for opt in args[i + 1].split(","):
                    if "=" in opt:
                        key, value = opt.split("=", 1)
                        options[key] = value
                    else:
                        options[opt] = None
                i += 2
                continue
        elif arg.startswith("-o"):
            for opt in arg[2:].split(","):
                if "=" in opt:
                    key, value = opt.split("=", 1)
                    options[key] = value
                else:
                    options[opt] = None
            i += 1
            continue
        elif arg.startswith("-"):
            # Handle flags that take arguments
            if arg in ("-t", "--types", "-L", "-U", "--source", "--target"):
                if i + 1 < len(args):
                    flags.extend([arg, args[i + 1]])
                    i += 2
                    continue
            flags.append(arg)
        else:
            positional.append(arg)
        i += 1

    source = positional[0] if len(positional) > 0 else None
    target = positional[1] if len(positional) > 1 else None

    return options, flags, source, target


def rebuild_options(options: dict) -> str:
    """Rebuild options string from dict, excluding 'loop'."""
    parts = []
    for key, value in options.items():
        if key == "loop":
            continue
        if value is None:
            parts.append(key)
        else:
            parts.append(f"{key}={value}")
    return ",".join(parts)


def setup_loop_device(source: str, options: dict) -> str | None:
    """Set up a loop device using losetup and return the device path."""
    losetup_args = [LOSETUP, "-f", "--show"]

    # Check for partscan option
    if "partscan" in options:
        losetup_args.append("-P")

    # Check for offset option
    if "offset" in options:
        losetup_args.extend(["-o", options["offset"]])

    # Check for sizelimit option
    if "sizelimit" in options:
        losetup_args.extend(["--sizelimit", options["sizelimit"]])

    # Check for read-only
    if "ro" in options:
        losetup_args.append("-r")

    losetup_args.append(source)

    print(f"mount-wrapper: running {losetup_args}")
    result = subprocess.run(losetup_args, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"losetup failed: {result.stderr}", file=sys.stderr)
        return None

    return result.stdout.strip()


def main():
    args = sys.argv[1:]
    print(f"mount-wrapper: called with args: {args}")

    # Parse the arguments
    options, flags, source, target = parse_mount_args(args)
    print(f"mount-wrapper: parsed options={options}, flags={flags}, source={source}, target={target}")

    # Check if loop option is specified and source is a regular file
    use_loop = "loop" in options and source and os.path.isfile(source)

    if use_loop:
        print(f"mount-wrapper: loop mount requested for {source}")

        # Set up loop device
        loop_device = setup_loop_device(source, options)
        if loop_device is None:
            sys.exit(1)

        print(f"mount-wrapper: losetup returned device {loop_device}")

        # Remove loop-specific options that mount doesn't need
        for opt in ("loop", "offset", "sizelimit", "partscan"):
            options.pop(opt, None)

        # Rebuild mount command with loop device instead of file
        mount_args = [REAL_MOUNT] + flags

        new_options = rebuild_options(options)
        if new_options:
            mount_args.extend(["-o", new_options])

        mount_args.append(loop_device)
        if target:
            mount_args.append(target)

        print(f"mount-wrapper: executing {mount_args}")
        os.execv(REAL_MOUNT, mount_args)
    else:
        # Pass through to real mount
        print(f"mount-wrapper: passing through to {REAL_MOUNT}")
        os.execv(REAL_MOUNT, [REAL_MOUNT] + args)


if __name__ == "__main__":
    main()
