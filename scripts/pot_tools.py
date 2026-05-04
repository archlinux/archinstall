#!/usr/bin/env python3
"""Tools for managing base.pot: find and add missing translatable strings.

Usage (from repo root):
	scripts/pot_tools.py stats
	scripts/pot_tools.py list
	scripts/pot_tools.py add_missing [--dry-run]

Requires: gettext (xgettext) installed.
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHINSTALL_DIR = REPO_ROOT / 'archinstall'
BASE_POT = ARCHINSTALL_DIR / 'locales' / 'base.pot'


def extract_msgids(path: Path) -> set[str]:
	content = path.read_text()
	ids: set[str] = set()
	current: str | None = None

	for line in content.splitlines():
		if line.startswith('msgid '):
			m = re.search(r'"(.*)"', line)
			current = m.group(1) if m else ''
		elif current is not None and line.startswith('"'):
			m = re.search(r'"(.*)"', line)
			if m:
				current += m.group(1)
		else:
			if current is not None and current:
				ids.add(current)
			current = None

	if current:
		ids.add(current)

	return ids


def generate_fresh_pot() -> Path:
	fd, tmp_path = tempfile.mkstemp(suffix='.pot')
	os.close(fd)
	tmp = Path(tmp_path)
	py_files = sorted(str(p) for p in ARCHINSTALL_DIR.rglob('*.py'))

	cmd = [
		'xgettext',
		'--no-location',
		'--omit-header',
		'--keyword=tr',
		'-d',
		'base',
		'-o',
		str(tmp),
	] + py_files

	subprocess.run(cmd, check=True, capture_output=True)
	return tmp


def get_missing(fresh_pot: Path) -> set[str]:
	generated = extract_msgids(fresh_pot)
	committed = extract_msgids(BASE_POT)
	return generated - committed


def cmd_stats() -> None:
	fresh_pot = generate_fresh_pot()
	try:
		generated = extract_msgids(fresh_pot)
		committed = extract_msgids(BASE_POT)
		missing = generated - committed

		print(f'Code:        {len(generated)} translatable strings')
		print(f'base.pot:    {len(committed)} msgids')
		print(f'  Missing:   {len(missing)}')
	finally:
		fresh_pot.unlink(missing_ok=True)


def cmd_list() -> None:
	fresh_pot = generate_fresh_pot()
	try:
		missing = sorted(get_missing(fresh_pot))

		if missing:
			print(f'=== MISSING ({len(missing)}): in code but not in base.pot ===')
			for s in missing:
				print(f'  + {s}')
		else:
			print('No missing strings')
	finally:
		fresh_pot.unlink(missing_ok=True)


def cmd_add_missing(dry_run: bool = False) -> None:
	fresh_pot = generate_fresh_pot()
	try:
		missing = sorted(get_missing(fresh_pot))

		if not missing:
			print('No missing strings, base.pot is up to date')
			return

		print(f'Adding {len(missing)} missing string(s)')
		for s in missing:
			print(f'  + {s}')

		if dry_run:
			print('(dry-run, no changes written)')
			return

		with open(BASE_POT, 'a') as f:
			for s in missing:
				if '{' in s:
					f.write('\n#, python-brace-format')
				f.write(f'\nmsgid "{s}"\nmsgstr ""\n')

		print(f'Done. Added to {BASE_POT}')
	finally:
		fresh_pot.unlink(missing_ok=True)


def main() -> None:
	if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
		print('Usage: pot_tools.py {stats|list|add_missing} [--dry-run]')
		sys.exit(0)

	cmd = sys.argv[1]
	if cmd == 'stats':
		cmd_stats()
	elif cmd == 'list':
		cmd_list()
	elif cmd == 'add_missing':
		dry_run = '--dry-run' in sys.argv
		cmd_add_missing(dry_run)
	else:
		print(f'Unknown command: {cmd}')
		sys.exit(1)


if __name__ == '__main__':
	main()
