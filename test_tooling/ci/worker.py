#!/usr/bin/env python3
"""CI worker for archinstall QEMU tests.

Runs as a systemd instantiated service (archinstall-ci-worker@SHA.service).
Performs three stages:
  1. Checkout the commit
  2. Build an Arch ISO with the archinstall source injected
  3. Run the QEMU test suite against the ISO

Reports results back to GitHub as commit statuses.
Uses only stdlib (no third-party dependencies).
"""

import configparser
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [worker] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("ci-worker")

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
    url = f"https://api.github.com{endpoint}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "archinstall-ci-worker",
    }
    req = urllib.request.Request(url, headers=headers, method=method, data=data)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        log.error("GitHub API %s %s -> %d: %s", method, endpoint, exc.code, body)
        raise


def set_commit_status(repo: str, sha: str, token: str, state: str,
                      description: str, context: str = "archinstall-ci/qemu") -> None:
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


def run_cmd(cmd: list[str], cwd: str | None = None,
            timeout: int = 600, env: dict | None = None,
            log_file: Path | None = None,
            stream: bool = False) -> subprocess.CompletedProcess:
    """Run a command, logging output. Raises on non-zero exit.

    When stream=True, output goes to both stdout (journald) and log_file
    in real time. Otherwise output is captured silently.
    """
    log.info("Running: %s", " ".join(cmd))
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)

    if stream:
        # Stream output live to stdout (journald) and optionally tee to log_file
        fh = open(log_file, "ab") if log_file else None
        try:
            if fh:
                fh.write(f"\n{'='*60}\n$ {' '.join(cmd)}\n{'='*60}\n".encode())
            proc = subprocess.Popen(
                cmd, cwd=cwd, env=merged_env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            )
            while True:
                line = proc.stdout.readline()
                if not line and proc.poll() is not None:
                    break
                if line:
                    sys.stdout.buffer.write(line)
                    sys.stdout.buffer.flush()
                    if fh:
                        fh.write(line)
                        fh.flush()
            proc.wait(timeout=timeout)
            result = subprocess.CompletedProcess(cmd, proc.returncode)
        finally:
            if fh:
                fh.close()
    elif log_file:
        with open(log_file, "a") as fh:
            fh.write(f"\n{'='*60}\n$ {' '.join(cmd)}\n{'='*60}\n")
            result = subprocess.run(
                cmd, cwd=cwd, timeout=timeout, env=merged_env,
                stdout=fh, stderr=subprocess.STDOUT,
            )
    else:
        result = subprocess.run(
            cmd, cwd=cwd, timeout=timeout, env=merged_env,
            capture_output=True, text=True,
        )

    if result.returncode != 0:
        if not log_file and not stream:
            if result.stdout:
                log.error("stdout: %s", result.stdout[-2000:])
            if result.stderr:
                log.error("stderr: %s", result.stderr[-2000:])
        raise subprocess.CalledProcessError(result.returncode, cmd)
    return result


def stage_checkout(sha: str, work_dir: Path, mirror_repo: str, repo_url: str) -> Path:
    """Stage 1: Clone and checkout the commit."""
    log.info("=== Stage 1: Checkout %s ===", sha[:12])
    repo_dir = work_dir / "repo"

    clone_args = ["git", "clone"]
    if Path(mirror_repo).exists():
        clone_args += ["--reference", mirror_repo]
    clone_args += [repo_url, str(repo_dir)]

    run_cmd(clone_args, timeout=120)

    # PR head commits live on fork branches and aren't fetched by default.
    # Fetch the specific SHA via the PR refs namespace, then fall back to
    # a direct fetch if the commit is on a regular branch.
    try:
        run_cmd(["git", "checkout", sha], cwd=str(repo_dir), timeout=30)
    except subprocess.CalledProcessError:
        log.info("SHA not in clone, fetching pull request refs...")
        run_cmd(
            ["git", "fetch", "origin",
             f"+refs/pull/*/head:refs/remotes/origin/pr/*"],
            cwd=str(repo_dir), timeout=120,
        )
        run_cmd(["git", "checkout", sha], cwd=str(repo_dir), timeout=30)

    log.info("Checked out %s into %s", sha[:12], repo_dir)
    return repo_dir


def stage_iso_build(sha: str, repo_dir: Path, iso_dir: Path, build_log: Path) -> Path:
    """Stage 2: Build the Arch ISO with archinstall source injected.

    ISOs are stored in a shared directory keyed by SHA and reused across
    runs. Cleanup is handled by systemd-tmpfiles.
    """
    log.info("=== Stage 2: ISO Build ===")

    sha_iso_dir = iso_dir / sha
    existing = sorted(sha_iso_dir.glob("archlinux-*.iso")) if sha_iso_dir.exists() else []
    if existing:
        log.info("Reusing cached ISO: %s", existing[-1])
        return existing[-1]

    build_script = repo_dir / "test_tooling" / "mkarchiso" / "build_iso.sh"
    if not build_script.exists():
        raise FileNotFoundError(f"Build script not found: {build_script}")

    # Run the ISO build script from the repo root
    # mkarchiso outputs to /tmp/archlive/out/ (inside PrivateTmp namespace)
    env = {"GITHUB_SHA": sha}
    run_cmd(
        ["bash", str(build_script)],
        cwd=str(repo_dir),
        timeout=1200,  # 20 minutes for ISO build
        env=env,
        log_file=build_log,
        stream=True,
    )

    # Find the built ISO
    archlive_out = Path("/tmp/archlive/out")
    isos = sorted(archlive_out.glob("archlinux-*.iso"))
    if not isos:
        raise FileNotFoundError("No ISO found in /tmp/archlive/out/")

    # Copy ISO to shared cache directory
    sha_iso_dir.mkdir(parents=True, exist_ok=True)
    iso_dest = sha_iso_dir / isos[-1].name
    shutil.copy2(str(isos[-1]), str(iso_dest))

    log.info("ISO built: %s", iso_dest)
    return iso_dest


def stage_qemu_test(repo_dir: Path, work_dir: Path, iso_path: Path,
                    cfg: configparser.ConfigParser, build_log: Path) -> int:
    """Stage 3: Run the QEMU test against the built ISO."""
    log.info("=== Stage 3: QEMU Test ===")

    ovmf_vars_src = cfg.get("qemu", "ovmf_vars")
    disk_size = cfg.get("qemu", "disk_size", fallback="10G")
    test_timeout = cfg.getint("qemu", "test_timeout", fallback=1800)

    test_dir = repo_dir / "tests" / "qemu"
    if not test_dir.exists():
        test_suite_src = cfg.get("qemu", "test_suite_dir",
                                 fallback="/opt/archinstall-ci/share/tests-qemu")
        if not Path(test_suite_src).exists():
            raise FileNotFoundError(
                f"tests/qemu/ not in commit and no fallback at {test_suite_src}"
            )
        log.info("tests/qemu/ not in commit, copying from %s", test_suite_src)
        (repo_dir / "tests").mkdir(parents=True, exist_ok=True)
        shutil.copytree(test_suite_src, str(test_dir))

    # Copy OVMF_VARS (writable copy needed by QEMU)
    ovmf_dest = test_dir / "OVMF_VARS.4m.fd"
    shutil.copy2(ovmf_vars_src, str(ovmf_dest))

    # Create test disk image
    archtest_img = test_dir / "archtest.img"
    if archtest_img.exists():
        archtest_img.unlink()
    run_cmd(
        ["qemu-img", "create", "-f", "qcow2", str(archtest_img), disk_size],
        timeout=30,
    )

    # Set up the ISO path where run_test.py expects it
    # run_test.py uses: ../../_work/iso/archlinux-*-x86_64.iso
    work_iso_dir = repo_dir / "_work" / "iso"
    work_iso_dir.mkdir(parents=True, exist_ok=True)
    iso_link = work_iso_dir / iso_path.name
    if iso_link.exists() or iso_link.is_symlink():
        iso_link.unlink()
    iso_link.symlink_to(iso_path)

    # Create empty serial.log for asciinema
    serial_log = test_dir / "serial.log"
    serial_log.write_text("")

    # Start asciinema recording in background (optional, best-effort)
    asciinema_proc = None
    demo_cast = test_dir / "demo.cast"
    try:
        asciinema_proc = subprocess.Popen(
            ["asciinema", "rec", str(demo_cast), "--overwrite",
             "-c", f"tail -f {serial_log}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(test_dir),
        )
        log.info("Started asciinema recording: %s", demo_cast)
    except FileNotFoundError:
        log.warning("asciinema not found, skipping recording")

    # Run the QEMU test -- stream output to journald so progress is visible.
    # Don't pipe stdout; run_test.py spawns QEMU with socket fd passing
    # which breaks if stdout is a pipe inherited by child processes.
    try:
        run_cmd(
            [sys.executable, "run_test.py"],
            cwd=str(test_dir),
            timeout=test_timeout,
            log_file=build_log,
            stream=True,
        )
        exit_code = 0
        log.info("QEMU test passed")
    except subprocess.CalledProcessError as exc:
        exit_code = exc.returncode
        log.info("QEMU test exited with code %d", exit_code)
    except subprocess.TimeoutExpired:
        log.error("QEMU test timed out after %d seconds", test_timeout)
        exit_code = 124  # Standard timeout exit code
    finally:
        # Stop asciinema
        if asciinema_proc:
            try:
                asciinema_proc.send_signal(signal.SIGINT)
                asciinema_proc.wait(timeout=5)
            except Exception:
                asciinema_proc.kill()
                asciinema_proc.wait()

    return exit_code


def archive_logs(work_dir: Path, repo_dir: Path, log_dir: Path) -> None:
    """Copy logs to the persistent log directory."""
    log_dir.mkdir(parents=True, exist_ok=True)

    build_log = work_dir / "build.log"
    if build_log.exists():
        shutil.copy2(str(build_log), str(log_dir / "build.log"))

    serial_log = repo_dir / "tests" / "qemu" / "serial.log"
    if serial_log.exists():
        shutil.copy2(str(serial_log), str(log_dir / "serial.log"))

    demo_cast = repo_dir / "tests" / "qemu" / "demo.cast"
    if demo_cast.exists():
        shutil.copy2(str(demo_cast), str(log_dir / "demo.cast"))


def main() -> None:
    if len(sys.argv) != 2:
        log.error("Usage: worker.py <commit-sha>")
        sys.exit(1)

    sha = sys.argv[1]
    log.info("Worker starting for commit %s", sha[:12])

    cfg = load_config(CONFIG_PATH)
    repo = cfg.get("github", "repo")
    token_file = cfg.get("github", "token_file")
    token = load_token(token_file)

    work_base = Path(cfg.get("paths", "work_dir"))
    log_base = Path(cfg.get("paths", "log_dir"))
    iso_base = Path(cfg.get("paths", "iso_dir"))
    state_file = cfg.get("paths", "state_file")
    mirror_repo = cfg.get("paths", "mirror_repo")

    work_dir = work_base / sha
    log_dir = log_base / sha
    build_log = work_dir / "build.log"
    repo_url = f"https://github.com/{repo}.git"

    work_dir.mkdir(parents=True, exist_ok=True)

    # ProtectHome=yes makes /root inaccessible; give subprocesses a writable HOME
    os.environ["HOME"] = str(work_dir)

    # Update state to running
    state = load_state(state_file)
    if sha in state:
        state[sha]["status"] = "running"
        state[sha]["started"] = datetime.now(timezone.utc).isoformat()
    else:
        state[sha] = {
            "status": "running",
            "source": "manual",
            "started": datetime.now(timezone.utc).isoformat(),
        }
    save_state(state_file, state)

    set_commit_status(repo, sha, token, "pending", "Building ISO...")

    exit_code = 1
    try:
        # Stage 1: Checkout
        repo_dir = stage_checkout(sha, work_dir, mirror_repo, repo_url)

        # Stage 2: ISO Build
        set_commit_status(repo, sha, token, "pending", "Building ISO...")
        iso_path = stage_iso_build(sha, repo_dir, iso_base, build_log)

        # Stage 3: QEMU Test
        set_commit_status(repo, sha, token, "pending", "Running QEMU test...")
        exit_code = stage_qemu_test(repo_dir, work_dir, iso_path, cfg, build_log)

    except subprocess.TimeoutExpired as exc:
        log.error("Stage timed out: %s", exc)
        exit_code = 124
    except subprocess.CalledProcessError as exc:
        log.error("Stage failed (exit %d): %s", exc.returncode, exc.cmd)
        exit_code = exc.returncode
    except FileNotFoundError as exc:
        log.error("Missing file: %s", exc)
        exit_code = 2
    except Exception:
        log.exception("Unexpected error")
        exit_code = 3

    # Archive logs
    try:
        repo_dir_path = work_dir / "repo"
        archive_logs(work_dir, repo_dir_path, log_dir)
    except Exception:
        log.exception("Failed to archive logs")

    # Report result
    if exit_code == 0:
        status = "success"
        description = "QEMU test passed"
    elif exit_code == 124:
        status = "failure"
        description = "QEMU test timed out"
    else:
        status = "failure"
        description = f"QEMU test failed (exit code {exit_code})"

    set_commit_status(repo, sha, token, status, description)

    # Update state
    state = load_state(state_file)
    if sha in state:
        state[sha]["status"] = status
        state[sha]["exit_code"] = exit_code
        state[sha]["finished"] = datetime.now(timezone.utc).isoformat()
    save_state(state_file, state)

    log.info("Worker finished for %s: %s (exit %d)", sha[:12], status, exit_code)
    sys.exit(0 if exit_code == 0 else 1)


if __name__ == "__main__":
    main()
