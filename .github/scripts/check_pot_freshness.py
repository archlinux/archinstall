#!/usr/bin/env python3
"""Check that all tr() strings from code exist in base.pot.

Used by CI. Fails if any translatable string is missing from the committed pot.

Usage:
    xgettext ... -o /tmp/generated.pot
    python3 check_pot_freshness.py /tmp/generated.pot locales/base.pot
"""

import re
import sys
from pathlib import Path


def extract_msgids(path: str) -> set[str]:
    content = Path(path).read_text()
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


def main() -> None:
    generated = extract_msgids(sys.argv[1])
    committed = extract_msgids(sys.argv[2])

    missing = sorted(generated - committed)

    if missing:
        print('::error::New tr() strings not in base.pot - run locales_generator.sh:')
        for s in missing:
            print(f'  {s}')
        sys.exit(1)

    print('All tr() strings are present in base.pot')


if __name__ == '__main__':
    main()
