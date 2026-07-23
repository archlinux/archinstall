#!/usr/bin/env python3
"""Verify archinstall/tui/binding_descriptions.py against the installed textual.

Run manually after a textual upgrade or after introducing a new textual
widget in archinstall/tui/components.py:

	python3 test_tooling/check_binding_descriptions.py

The script parses the tr_noop() entries from binding_descriptions.py (no
archinstall import needed) and compares them with the MRO-merged binding
descriptions of the textual classes used in components.py. Exits non-zero
on any difference and prints the exact missing/stale entries.
"""

import re
import sys
from pathlib import Path

from textual.app import App
from textual.screen import Screen
from textual.widgets import Button, DataTable, HelpPanel, Input, OptionList, SelectionList

# Must mirror the textual widget classes used in archinstall/tui/components.py.
# Extend when a new widget is introduced there.
TEXTUAL_CLASSES = (App, Screen, Button, DataTable, HelpPanel, Input, OptionList, SelectionList)

MODULE_PATH = Path(__file__).parent.parent / 'archinstall/tui/binding_descriptions.py'


def live_descriptions() -> set[str]:
	descriptions: set[str] = set()
	# Walk the full MRO: _translate_bindings() operates on the merged bindings
	# map, so descriptions inherited from ancestors are translated too.
	for cls in TEXTUAL_CLASSES:
		for klass in cls.__mro__:
			for binding in klass.__dict__.get('BINDINGS', []):
				description = getattr(binding, 'description', None)
				if not description and isinstance(binding, tuple) and len(binding) > 2:
					description = binding[2]
				if description:
					descriptions.add(str(description))
	return descriptions


def listed_descriptions() -> set[str]:
	content = MODULE_PATH.read_text(encoding='utf-8')
	return set(re.findall(r"tr_noop\('([^']+)'\)", content))


def main() -> int:
	live = live_descriptions()
	listed = listed_descriptions()

	if live == listed:
		print(f'OK: {len(listed)} descriptions in sync with installed textual')
		return 0

	for description in sorted(live - listed):
		print(f'missing from binding_descriptions.py: {description}')
	for description in sorted(listed - live):
		print(f'stale in binding_descriptions.py: {description}')
	return 1


if __name__ == '__main__':
	sys.exit(main())
