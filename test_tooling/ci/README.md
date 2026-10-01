# archinstall CI - systemd-based QEMU Test Runner

Polls GitHub for open pull requests targeting `master`, builds an Arch ISO with
the archinstall source injected, and runs the QEMU test suite (`tests/qemu/`)
against the latest commit of each matching PR. Results are reported back as
GitHub commit statuses.

## Requirements

- Arch Linux host with KVM support
- Packages: `qemu-full`, `ovmf`, `archiso`, `git`, `python`, `asciinema` (optional)
- A GitHub personal access token with `repo:status` scope

## Quick Start

```bash
sudo ./install.sh [github-token]
```

This creates `/opt/archinstall-ci/` with the following layout:

```
/opt/archinstall-ci/
  bin/          monitor.py, worker.py
  etc/          config.ini, github-token
  state/        tested-commits.json
  work/<sha>/   ephemeral per-run directories
  logs/<sha>/   build.log, serial.log, demo.cast
  mirror/       bare git mirror for fast clones
```

## How It Works

1. **Timer** (`archinstall-ci-monitor.timer`) fires every 5 minutes
2. **Monitor** (`archinstall-ci-monitor.service`) polls open PRs against
   `master`, checks if any `archinstall/` files changed, and starts a worker
   for the latest commit (head SHA) of each matching PR
3. **Worker** (`archinstall-ci-worker@<sha>.service`) clones the repo, runs
   `build_iso.sh`, sets up QEMU, and runs `tests/qemu/run_test.py`
4. Worker reports `success`/`failure` as a GitHub commit status
5. **Cleanup** via `systemd-tmpfiles` (daily) removes work dirs >2d,
   cached ISOs >10d, and logs >30d

## Configuration

Edit `/opt/archinstall-ci/etc/config.ini`:

| Section   | Key              | Default                        | Description                          |
|-----------|------------------|--------------------------------|--------------------------------------|
| `github`  | `repo`           | `archlinux/archinstall`        | GitHub repository                    |
| `github`  | `base_branch`    | `master`                       | Only test PRs targeting this branch  |
| `filter`  | `trigger_paths`  | `archinstall/`                 | Only test if these paths changed     |
| `qemu`    | `test_timeout`   | `1800`                         | QEMU test timeout in seconds         |
| `limits`  | `max_concurrent` | `1`                            | Max simultaneous workers             |

## Systemd Units

| Unit                                    | Type     | Purpose                              |
|-----------------------------------------|----------|---------------------------------------|
| `archinstall-ci-monitor.timer`          | Timer     | Triggers monitor every 5 min             |
| `archinstall-ci-monitor.service`        | Oneshot   | Polls GitHub, dispatches workers         |
| `archinstall-ci-worker@.service`        | Template  | Instantiated per SHA for test runs       |
| `archinstall-ci.slice`                  | Slice     | Global resource caps (10G RAM, 400% CPU) |
| `archinstall-ci.conf` (tmpfiles.d)      | tmpfiles  | Cleans work >2d, ISOs >10d, logs >30d   |

## Security

Workers run as root (required by mkarchiso) but are hardened via systemd:

- `ProtectHome=yes` - no access to /home or /root
- `PrivateTmp=yes` - isolated /tmp namespace
- `DevicePolicy=closed` - explicit device whitelist (KVM, loop, tun)
- `ProtectKernelModules=yes` - can't load kernel modules
- `SystemCallFilter` - blocks reboot, swap, clock syscalls
- `MemoryMax=8G` / `TimeoutStartSec=2700` - resource and time limits

Check hardening scores:

```bash
systemd-analyze security archinstall-ci-monitor.service
systemd-analyze security archinstall-ci-worker@TEST.service
```

## Manual Testing

```bash
# Trigger a manual poll
sudo systemctl start archinstall-ci-monitor.service
journalctl -u archinstall-ci-monitor.service

# Run a specific commit
sudo systemctl start archinstall-ci-worker@COMMIT_SHA.service
journalctl -fu archinstall-ci-worker@COMMIT_SHA.service

# Check state
cat /opt/archinstall-ci/state/tested-commits.json | python -m json.tool
```
