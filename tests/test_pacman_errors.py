from archinstall.lib.pacman.errors import FailureKind, classify, strip_version
from archinstall.lib.pacman.pacman import _recovery_options

CONFLICT = """\
:: Synchronizing package databases...
resolving dependencies...
looking for conflicting packages...
:: pipewire-jack and jack2 are in conflict. Remove jack2? [y/N]
error: unresolvable package conflicts detected
error: failed to prepare transaction (conflicting dependencies)
"""

CONFLICT_WITH_PROVIDER = """\
:: iptables-nft and iptables are in conflict (iptables)
error: unresolvable package conflicts detected
"""

MISSING_TARGET = """\
:: Synchronizing package databases...
error: target not found: linux-zen-headerz
"""

FILE_EXISTS = """\
checking for file conflicts...
error: failed to commit transaction (conflicting files)
filesystem: /usr/lib/os-release exists in filesystem
glibc: /usr/lib/locale/locale-archive exists in filesystem (owned by glibc-locales)
Errors occurred, no packages were upgraded.
"""

UNSATISFIED = """\
resolving dependencies...
:: unable to satisfy dependency 'libfoo=2.0' required by bar
error: failed to prepare transaction (could not satisfy dependencies)
"""

DOWNLOAD_FAILURE = """\
error: failed retrieving file 'core.db' from mirror.example.org : Connection timed out
error: failed to synchronize all databases (unexpected error)
"""


def test_classify_conflict() -> None:
	failure = classify(CONFLICT)

	assert failure.kind == FailureKind.CONFLICT
	assert failure.candidates == ('pipewire-jack', 'jack2')


def test_classify_conflict_strips_trailing_punctuation() -> None:
	"""The package name is followed by '.' in 'are in conflict. Remove x?'."""
	assert classify(CONFLICT).candidates[1] == 'jack2'


def test_classify_conflict_with_provider_suffix() -> None:
	failure = classify(CONFLICT_WITH_PROVIDER)

	assert failure.kind == FailureKind.CONFLICT
	assert failure.candidates == ('iptables-nft', 'iptables')


def test_classify_missing_target() -> None:
	failure = classify(MISSING_TARGET)

	assert failure.kind == FailureKind.MISSING_TARGET
	assert failure.candidates == ('linux-zen-headerz',)


def test_classify_file_conflict_collects_every_path() -> None:
	failure = classify(FILE_EXISTS)

	assert failure.kind == FailureKind.FILE_EXISTS
	assert failure.candidates == ('filesystem', 'glibc')
	assert failure.paths == ('/usr/lib/os-release', '/usr/lib/locale/locale-archive')


def test_classify_unsatisfied_dependency() -> None:
	failure = classify(UNSATISFIED)

	assert failure.kind == FailureKind.UNSATISFIED_DEPENDENCY
	assert failure.candidates == ('bar',)


def test_classify_unknown_keeps_the_last_error_line() -> None:
	failure = classify(DOWNLOAD_FAILURE)

	assert failure.kind == FailureKind.UNKNOWN
	assert failure.candidates == ()
	assert failure.summary == 'failed to synchronize all databases (unexpected error)'


def test_classify_conflict_wins_over_a_trailing_error_line() -> None:
	"""A conflict is more actionable than the generic error pacman ends with."""
	assert classify(CONFLICT + DOWNLOAD_FAILURE).kind == FailureKind.CONFLICT


def test_classify_empty_output() -> None:
	failure = classify('')

	assert failure.kind == FailureKind.UNKNOWN
	assert failure.summary == ''


def test_strip_version() -> None:
	assert strip_version('foo') == 'foo'
	assert strip_version('foo>=1.2') == 'foo'
	assert strip_version('foo=1.2') == 'foo'
	assert strip_version('foo>2:1.2-3') == 'foo'
	assert strip_version('lib32-glibc') == 'lib32-glibc'


def test_strip_version_keeps_names_that_end_in_a_version() -> None:
	"""dotnet-runtime-8.0 and friends are package names, not versioned specs."""
	assert strip_version('dotnet-runtime-8.0') == 'dotnet-runtime-8.0'
	assert strip_version('python2') == 'python2'
	assert strip_version('sdl2-compat') == 'sdl2-compat'


def test_conflict_between_two_requested_packages_offers_all_three_choices() -> None:
	failure = classify(CONFLICT)
	options, safe = _recovery_options(failure, ['pipewire-jack', 'jack2'], repeated=False)

	assert [option.key for option in options] == ['keep_first', 'keep_second', 'drop']
	assert safe == 'drop'


def test_conflict_between_dependencies_offers_no_automatic_choice() -> None:
	"""
	Neither package was requested, so dropping one from the request list would be
	a no-op and retrying would fail identically. Nothing may be picked on a timeout.
	"""
	failure = classify(CONFLICT)
	options, safe = _recovery_options(failure, [], repeated=False)

	assert options == []
	assert safe is None


def test_conflict_with_one_requested_package_can_only_drop_that_one() -> None:
	failure = classify(CONFLICT)
	options, safe = _recovery_options(failure, ['jack2'], repeated=False)

	assert [option.key for option in options] == ['drop']
	assert safe == 'drop'


def test_missing_target_can_be_renamed_or_dropped() -> None:
	failure = classify(MISSING_TARGET)
	options, safe = _recovery_options(failure, ['linux-zen-headerz'], repeated=False)

	assert [option.key for option in options] == ['rename', 'drop']
	assert safe == 'drop'


def test_file_conflict_never_overwrites_on_a_timeout() -> None:
	failure = classify(FILE_EXISTS)
	options, safe = _recovery_options(failure, [], repeated=False)

	assert [option.key for option in options] == ['overwrite']
	assert safe is None


def test_unknown_failure_retries_once() -> None:
	failure = classify(DOWNLOAD_FAILURE)
	options, safe = _recovery_options(failure, [], repeated=False)

	assert [option.key for option in options] == ['retry', 'abandon']
	assert safe == 'retry'


def test_a_repeated_failure_stops_offering_the_same_way_out() -> None:
	"""Otherwise the timeout default would loop forever without a keypress."""
	failure = classify(CONFLICT)
	options, safe = _recovery_options(failure, ['pipewire-jack', 'jack2'], repeated=True)

	assert [option.key for option in options] == ['abandon']
	assert safe is None
