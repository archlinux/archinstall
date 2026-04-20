# MDDOS Installer Development Guide for AI SWE Agents

This is a Python 3.10+ CLI application, heavily forked from `archinstall`. It uses the built-in `curses` library for its TUI, and relies on strict type hinting. It is designed to be a secure, bare-bones Arch Linux installer that strictly sets up Hyprland + Quickshell, locking down other options to provide a predictable environment for a subsequent post-install wizard.

Read more about the purpose and business logic of the app in `docs/obsidian/1.1.prd-installer-mvp.md` and `docs/obsidian/1.2.wbs-installer-mvp.md`.

## Python Environment

This project requires Python 3.10+. Assume the virtual environment is already activated in the agent environment. If starting fresh, activate it with:

```bash
python -m venv venv && source venv/bin/activate
```

Dependencies are managed via `pip`. Install from `requirements.txt` for runtime deps. **Do not add new dependencies to `pyproject.toml` or `requirements.txt` without explicit user authorization.** Prioritize Python standard libraries to maintain a minimal, secure attack surface.

## Commands

- `sudo python -m archinstall --dry-run`: Runs the installer in dry-run mode. **Scope of dry-run:** This flag safely skips all destructive side effects, including disk formatting, `pacstrap` package installation, and `chroot` operations. It only simulates the workflow, outputs the TUI, and writes the `user_configuration.json` and logs to `/var/log/archinstall/`.
- `sudo python -m archinstall`: Runs the full destructive installer.

Always use `--dry-run` when iterating. If a real installation fails mid-way, there is no automatic rollback — the system will be left in a dirty state (partitions mounted at `/mnt`, partially installed packages). Recovery requires `umount -R /mnt` and wiping affected partitions, or rebooting the live environment.

## Validation Pipeline (Linting & Formatting)

After editing any file, run the following in exact order. All must pass before presenting a solution:

1. `ruff format .`
2. `ruff check --fix .`
3. `mypy .`

This project strictly uses Ruff for linting/formatting and Mypy for static type analysis. Use your judgement for linter violations that are not auto-fixable, but never ignore typing errors.

## Testing

- **Unit tests (fast):** `pytest`
- **System testing (simulated):** `sudo python -m archinstall --dry-run`
- **Quality Gate:** All existing tests must pass before considering a task complete. Avoid silent regressions.

Because this is a `curses`-based TUI, standard interactive testing does not apply. Rely on verifying data model logic, testing isolated functions, and `pytest`. Use individual Python scripts or `pdb` for tracing complex state.

**Give-Up Condition:** If an issue cannot be resolved within 3 isolated test attempts, stop and ask the user for architectural clarification to avoid hallucination loops and wasted context.

## Debugging

When investigating a problem, follow this sequence:

1. Restate the problem clearly.
2. List the likely causes.
3. Suggest small, targeted tests to isolate the cause.
4. Only then propose a fix.

The following log files are available to aid investigation:

- `/var/log/archinstall/install.log` — full installer log.
- `/var/log/archinstall/cmd_history.txt` — every shell command that was triggered.
- `/var/log/archinstall/cmd_output.txt` — stdout from those commands.

You can also run specific files directly or drop into `pdb` for complex state inspection.

## Architecture

Key files and what they own:

- `archinstall/lib/menu/global_menu.py` — main TUI entry point. Implements the strict 7-step hierarchy that guides the user without overwhelming them.
- `archinstall/lib/command.py` — defines `SysCommand`, which **must** be used for all shell commands. Bypassing it (e.g., with `subprocess.run`) means commands go unlogged, breaking the `cmd_history.txt` audit trail and destroying the post-install wizard's ability to reconstruct what the base installer did.
- `archinstall/lib/installer.py` — core `pacstrap` and `chroot` logic. Also responsible for exporting the `mddos_config.json` handoff file to the newly installed filesystem.
- `archinstall/lib/models/` — data classes that hold TUI selections, enforcing strict typing before execution. **When modifying configuration exports like `mddos_config.json`, strictly adhere to the schemas defined in `docs/obsidian/schema.md` or validate against `models/config_schema.py`. Do not guess or hallucinate JSON schemas.**
- `archinstall/default_profiles/` — profile configurations. Aggressively pruned to Hyprland only, to minimize attack surface and maintenance burden.

## TUI Patterns

Avoid writing raw `curses` code. Build all UI on the `archinstall.tui` abstraction layer, using classes like `Selection` and `Confirmation` handlers.

For a concrete example, see `archinstall/lib/general/system_menu.py` → `select_kernel()`: it shows how to initialize `Selection[str]` with `multi=True` for a checkbox list and how `MenuItemGroup` captures user selections.

We value code that explains itself through clear class, method, and variable names. Comments should be used only when necessary to explain tricky logic.

## Agent Behavior

- Default behavior is analysis, not implementation. Never write code unless explicitly requested.
- If unsure, ask for clarification before proceeding.
- Act as a senior pair programmer: explain reasoning before proposing solutions, challenge assumptions, and suggest minimal changes first.

## Git

Agents operate read-only. Do not create commits, push, merge, or modify branches unless given explicit authorization. No git authentication is available in this environment — do not run any command that could prompt for credentials.

The full branching strategy and contribution workflow for human developers is documented in `CONTRIBUTING.md`.

### What Agents Must Never Do

- Force-push to `main` or `dev`.
- Commit directly to `main`.
- Run `git merge upstream/main` on `dev` or `main` without a dedicated sync branch.
- Leave merge conflict markers (`<<<<<<<`) in any committed file.
- Perform write operations on any git remote.
