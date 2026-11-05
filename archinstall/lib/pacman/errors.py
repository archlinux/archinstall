"""
Classification of pacman and pacstrap failures.

Kept free of any I/O so that it can be exercised against recorded pacman output.
:func:`classify` never raises and never returns ``None``: anything it does not
recognise comes back as :attr:`FailureKind.UNKNOWN`, which callers can still
offer a generic retry for.
"""

import re
from dataclasses import dataclass, field
from enum import StrEnum, auto

_CONFLICT = re.compile(r'(?P<pkg_a>\S+) and (?P<pkg_b>\S+) are in conflict')
_MISSING_TARGET = re.compile(r'target not found:\s*(?P<pkg>\S+)')
_FILE_EXISTS = re.compile(r'(?P<pkg>[\w@.+-]+):\s+(?P<path>/\S+) exists in filesystem')
_UNSATISFIED = re.compile(r"unable to satisfy dependency '(?P<dep>[^']+)' required by '?(?P<pkg>[^'\s]+)'?")
_ERROR_LINE = re.compile(r'^error:\s*(?P<message>.+)$')

# Package names may contain dots, so only strip punctuation that pacman adds
# around them when it builds a sentence.
_TRAILING = '.,;:?!)\'"'


class FailureKind(StrEnum):
	CONFLICT = auto()
	"""Two packages cannot be installed together."""

	FILE_EXISTS = auto()
	"""A package wants to write files that are already on the target."""

	MISSING_TARGET = auto()
	"""A requested package does not exist in any configured repository."""

	UNSATISFIED_DEPENDENCY = auto()
	"""A package requires something no repository provides."""

	UNKNOWN = auto()
	"""Anything else, including download and signature errors."""


@dataclass(frozen=True)
class Failure:
	kind: FailureKind
	candidates: tuple[str, ...] = ()
	"""Packages involved, in the order pacman named them. Droppable by the caller."""

	paths: tuple[str, ...] = field(default=())
	"""Conflicting files, only populated for :attr:`FailureKind.FILE_EXISTS`."""

	summary: str = ''
	"""The offending output, verbatim, for display."""


def classify(output: str) -> Failure:
	"""Turn raw pacman output into the most specific failure it describes."""
	lines = [line.strip() for line in output.splitlines() if line.strip()]

	for detect in (_conflict, _file_conflict, _missing_target, _unsatisfied):
		if failure := detect(lines):
			return failure

	return Failure(FailureKind.UNKNOWN, summary=_last_error(lines))


def strip_version(name: str) -> str:
	"""
	Reduce a package specification to its bare name: ``foo>=2:1.2-3`` becomes ``foo``.

	Only version constraints are removed. A trailing version is deliberately left
	alone, because package names such as ``dotnet-runtime-8.0`` end in one.
	"""
	return re.split(r'[<>=]', name, maxsplit=1)[0].strip()


def _conflict(lines: list[str]) -> Failure | None:
	for line in lines:
		if match := _CONFLICT.search(line):
			pkg_a, pkg_b = _clean(match['pkg_a']), _clean(match['pkg_b'])

			if pkg_a and pkg_b:
				return Failure(FailureKind.CONFLICT, (pkg_a, pkg_b), summary=line)

	return None


def _file_conflict(lines: list[str]) -> Failure | None:
	packages: list[str] = []
	paths: list[str] = []

	for line in lines:
		if match := _FILE_EXISTS.search(line):
			if (pkg := _clean(match['pkg'])) and pkg not in packages:
				packages.append(pkg)

			paths.append(match['path'])

	if not packages:
		return None

	shown = paths[:5]
	summary = '\n'.join(shown)

	if len(paths) > len(shown):
		summary += f'\n... and {len(paths) - len(shown)} more file(s)'

	return Failure(FailureKind.FILE_EXISTS, tuple(packages), tuple(paths), summary)


def _missing_target(lines: list[str]) -> Failure | None:
	for line in lines:
		if match := _MISSING_TARGET.search(line):
			if pkg := _clean(match['pkg']):
				return Failure(FailureKind.MISSING_TARGET, (pkg,), summary=line)

	return None


def _unsatisfied(lines: list[str]) -> Failure | None:
	for line in lines:
		if match := _UNSATISFIED.search(line):
			if pkg := _clean(match['pkg']):
				return Failure(FailureKind.UNSATISFIED_DEPENDENCY, (pkg,), summary=line)

	return None


def _last_error(lines: list[str]) -> str:
	"""The most recent ``error:`` line, which is usually the one that matters."""
	for line in reversed(lines):
		if match := _ERROR_LINE.match(line):
			return match['message']

	return lines[-1] if lines else ''


def _clean(name: str) -> str:
	return name.strip(_TRAILING)
