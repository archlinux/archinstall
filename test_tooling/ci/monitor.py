#!/usr/bin/env python3
"""GitHub polling monitor for archinstall CI.

Polls open pull requests targeting the configured base branch (master),
checks if the PR touches any trigger paths (archinstall/), and dispatches
a worker service for the latest commit (head SHA) of matching PRs.

Only the head commit of each PR is tested -- older commits are skipped.

Designed to run as a systemd oneshot service triggered by a timer.
Uses only stdlib (no third-party dependencies).
"""

import configparser
import json
import logging
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("ci-monitor")

CONFIG_PATH = os.environ.get(
    "ARCHINSTALL_CI_CONFIG", "/opt/archinstall-ci/etc/config.ini"
)


def load_config(path: str) -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    if not cfg.read(path):
        log.error("Cannot read config file: %s", path)
        sys.exit(1)
    return cfg


def load_token(path: str) -> str:
    try:
        return Path(path).read_text().strip()
    except FileNotFoundError:
        log.error("Token file not found: %s", path)
        sys.exit(1)


def load_state(path: str) -> dict:
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(path: str, state: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp = path + ".tmp"
    Path(tmp).write_text(json.dumps(state, indent=2))
    os.replace(tmp, path)


def github_api(endpoint: str, token: str, method: str = "GET",
               data: bytes | None = None) -> dict | list:
    """Make a GitHub REST API request."""
    url = f"https://api.github.com{endpoint}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "archinstall-ci-monitor",
    }
    req = urllib.request.Request(url, headers=headers, method=method, data=data)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        log.error("GitHub API %s %s -> %d: %s", method, endpoint, exc.code, body)
        raise
    except urllib.error.URLError as exc:
        log.error("GitHub API %s %s -> %s", method, endpoint, exc.reason)
        raise


def set_commit_status(repo: str, sha: str, token: str, state: str,
                      description: str, context: str = "archinstall-ci/qemu") -> None:
    """Set a commit status on GitHub."""
    endpoint = f"/repos/{repo}/statuses/{sha}"
    payload = json.dumps({
        "state": state,
        "description": description[:140],
        "context": context,
    }).encode()
    try:
        github_api(endpoint, token, method="POST", data=payload)
        log.info("Set status %s on %s: %s", state, sha[:12], description)
    except Exception:
        log.exception("Failed to set commit status on %s", sha[:12])


def get_open_prs(repo: str, base_branch: str, token: str) -> list[dict]:
    """Get open PRs targeting the base branch.

    Returns a list of dicts with keys: number, title, head_sha, head_ref.
    """
    prs = []
    page = 1
    while True:
        try:
            data = github_api(
                f"/repos/{repo}/pulls?state=open&base={base_branch}"
                f"&sort=updated&direction=desc&per_page=30&page={page}",
                token,
            )
        except urllib.error.HTTPError:
            break

        if not data:
            break

        for pr in data:
            prs.append({
                "number": pr["number"],
                "title": pr["title"],
                "head_sha": pr["head"]["sha"],
                "head_ref": pr["head"]["ref"],
            })
        page += 1

        # Safety cap -- don't paginate indefinitely
        if page > 10:
            break

    return prs


def get_pr_changed_files(repo: str, pr_number: int, token: str) -> list[str]:
    """Get the list of files changed in a PR (across all commits)."""
    files = []
    page = 1
    while True:
        try:
            data = github_api(
                f"/repos/{repo}/pulls/{pr_number}/files"
                f"?per_page=100&page={page}",
                token,
            )
        except urllib.error.HTTPError:
            break

        if not data:
            break

        files.extend(f["filename"] for f in data)
        if len(data) < 100:
            break
        page += 1

    return files


def matches_trigger_paths(files: list[str], trigger_paths: list[str]) -> bool:
    """Check if any changed file matches the trigger path prefixes."""
    for f in files:
        for prefix in trigger_paths:
            if f.startswith(prefix):
                return True
    return False


def count_running_workers() -> int:
    """Count currently active archinstall-ci-worker instances."""
    try:
        result = subprocess.run(
            ["systemctl", "list-units", "--type=service", "--state=running",
             "--no-legend", "archinstall-ci-worker@*"],
            capture_output=True, text=True, timeout=10,
        )
        return len([line for line in result.stdout.strip().splitlines() if line.strip()])
    except Exception:
        return 0


def start_worker(sha: str) -> bool:
    """Start a worker service for the given commit SHA."""
    unit = f"archinstall-ci-worker@{sha}.service"
    try:
        result = subprocess.run(
            ["systemctl", "start", unit],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            log.info("Started worker: %s", unit)
            return True
        else:
            log.error("Failed to start %s: %s", unit, result.stderr)
            return False
    except Exception:
        log.exception("Exception starting %s", unit)
        return False


def main() -> None:
    cfg = load_config(CONFIG_PATH)

    repo = cfg.get("github", "repo")
    token_file = cfg.get("github", "token_file")
    base_branch = cfg.get("github", "base_branch", fallback="master")

    state_file = cfg.get("paths", "state_file")
    trigger_paths = [p.strip() for p in cfg.get("filter", "trigger_paths").split(",")]
    max_concurrent = cfg.getint("limits", "max_concurrent", fallback=1)

    token = load_token(token_file)
    state = load_state(state_file)

    # Fetch open PRs targeting the base branch
    prs = get_open_prs(repo, base_branch, token)
    log.info("Found %d open PR(s) targeting %s", len(prs), base_branch)

    processed = 0
    for pr in prs:
        sha = pr["head_sha"]
        pr_num = pr["number"]
        source = f"pr:{pr_num}"

        if sha in state:
            log.debug("Already seen %s (PR #%d): %s", sha[:12], pr_num, state[sha].get("status"))
            continue

        log.info("New head commit %s on PR #%d (%s)", sha[:12], pr_num, pr["title"])

        # Check changed files across the entire PR
        files = get_pr_changed_files(repo, pr_num, token)
        if not files:
            log.warning("Could not get changed files for PR #%d, skipping", pr_num)
            state[sha] = {
                "status": "error",
                "source": source,
                "pr_title": pr["title"],
                "reason": "could not fetch changed files",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            save_state(state_file, state)
            continue

        if not matches_trigger_paths(files, trigger_paths):
            log.info("No trigger-path matches for PR #%d, skipping", pr_num)
            state[sha] = {
                "status": "skipped",
                "source": source,
                "pr_title": pr["title"],
                "reason": "no matching paths",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            save_state(state_file, state)
            continue

        # Check concurrency limit
        running = count_running_workers()
        if running >= max_concurrent:
            log.info("Concurrency limit reached (%d/%d), deferring PR #%d",
                     running, max_concurrent, pr_num)
            break

        # Set pending status on GitHub
        set_commit_status(repo, sha, token, "pending",
                          f"QEMU test queued (PR #{pr_num})", "archinstall-ci/qemu")

        # Start worker
        if start_worker(sha):
            state[sha] = {
                "status": "dispatched",
                "source": source,
                "pr_title": pr["title"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        else:
            state[sha] = {
                "status": "error",
                "source": source,
                "pr_title": pr["title"],
                "reason": "failed to start worker",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            set_commit_status(repo, sha, token, "error",
                              "Failed to start CI worker", "archinstall-ci/qemu")

        save_state(state_file, state)
        processed += 1

    if processed == 0:
        log.info("No new commits to process")
    else:
        log.info("Processed %d new commit(s)", processed)


if __name__ == "__main__":
    main()
