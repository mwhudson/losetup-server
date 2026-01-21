# losetup-server

A simple HTTP server that allows LXD containers to create and manage loop devices on the host.

## Overview

`losetup-server` runs on the host and listens on the LXD bridge interface. It executes `losetup` commands on behalf of a container and automatically adds created loop devices (and their partitions) to the container.

`losetup-client.py` runs inside the container as a drop-in replacement for `losetup`, forwarding commands to the server.

## Requirements

- Python 3.12+
- Flask 3.0+ (`apt install python3-flask` on Ubuntu 24.04)
- LXD with the dir storage backend

## Usage

### Host

```bash
python3 server.py <container-name>
```

The server automatically detects the network bridge the container is attached to and listens on that interface's IP address (port 12345 by default).

### Container

Copy `losetup-client.py` into the container and use it as a replacement for `losetup`:

```bash
./losetup-client.py -f --show -P /path/to/disk.img
```

The client automatically connects to the server via the container's default gateway.

## License

Copyright (C) Canonical Ltd.

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License version 3 as published by the Free Software Foundation.

See [LICENSE](LICENSE) for the full license text.
