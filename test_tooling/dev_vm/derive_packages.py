#!/usr/bin/env python3
"""Parse pyproject.toml runtime dependencies and emit Arch package names.

Assumes the python-<name> convention, which holds for every archinstall
dependency today. If a future dep breaks the convention, fix here.
"""

import re
import sys
import tomllib


def main() -> int:
	if len(sys.argv) != 2:
		print(f'usage: {sys.argv[0]} <path-to-pyproject.toml>', file=sys.stderr)
		return 1

	with open(sys.argv[1], 'rb') as f:
		data = tomllib.load(f)

	for dep in data['project']['dependencies']:
		name = re.split(r'[<>=!~;\[\s]', dep, maxsplit=1)[0].strip()
		if name:
			# PEP 503: lowercase, any run of [-_.] becomes '-'. Arch mirrors this
			# naming, so normalize before prepending the python- prefix.
			name = re.sub(r'[-_.]+', '-', name).lower()
			print(f'python-{name}')

	return 0


if __name__ == '__main__':
	sys.exit(main())
