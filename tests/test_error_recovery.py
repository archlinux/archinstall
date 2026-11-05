import pytest

from archinstall.lib import error_recovery
from archinstall.lib.error_recovery import RETRY, InstallationAbortedError, Recovery, prompt

OPTIONS = [
	Recovery('keep_first', 'Keep the first one'),
	Recovery('drop', 'Keep neither and continue'),
]


@pytest.fixture(autouse=True)
def _interactive(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Pretend a terminal is attached; individual tests drive the answers themselves."""
	monkeypatch.setattr(error_recovery, '_can_prompt', lambda: True)


def _answers(monkeypatch: pytest.MonkeyPatch, *lines: str | None) -> None:
	remaining = list(lines)

	def read_line(_question: str, _timeout: float | None) -> str | None:
		return remaining.pop(0)

	monkeypatch.setattr(error_recovery, '_read_line', read_line)


def test_selecting_an_option_returns_its_key(monkeypatch: pytest.MonkeyPatch) -> None:
	_answers(monkeypatch, '1')

	assert prompt('Package conflict', OPTIONS, safe='drop') == 'keep_first'


def test_invalid_answers_are_rejected_without_advancing(monkeypatch: pytest.MonkeyPatch) -> None:
	_answers(monkeypatch, 'yes', '', '9', '-1', '2')

	assert prompt('Package conflict', OPTIONS, safe='drop') == 'drop'


def test_no_answer_falls_back_to_the_safe_option(monkeypatch: pytest.MonkeyPatch) -> None:
	_answers(monkeypatch, None)

	assert prompt('Package conflict', OPTIONS, safe='drop') == 'drop'


def test_no_answer_and_no_safe_option_aborts(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Without a safe choice the prompt waits, so a None here means stdin is gone."""
	_answers(monkeypatch, None)

	with pytest.raises(InstallationAbortedError):
		prompt('Package conflict', OPTIONS, safe=None)


def test_unattended_runs_take_the_safe_option_without_asking(monkeypatch: pytest.MonkeyPatch) -> None:
	def unreachable(_question: str, _timeout: float | None) -> str | None:
		raise AssertionError('should not have prompted')

	monkeypatch.setattr(error_recovery, '_read_line', unreachable)

	assert prompt('Package conflict', OPTIONS, safe='drop', interactive=False) == 'drop'


def test_unattended_runs_abort_when_nothing_is_safe() -> None:
	with pytest.raises(InstallationAbortedError):
		prompt('Package conflict', OPTIONS, safe=None, interactive=False)


def test_the_escape_hatches_are_always_appended(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Two caller options means 3 is the shell and 4 is exit."""
	_answers(monkeypatch, '4', 'n')

	with pytest.raises(InstallationAbortedError) as raised:
		prompt('Package conflict', OPTIONS, safe='drop')

	assert raised.value.save_config is False


def test_exiting_can_request_the_configuration_to_be_saved(monkeypatch: pytest.MonkeyPatch) -> None:
	_answers(monkeypatch, '4', 'y')

	with pytest.raises(InstallationAbortedError) as raised:
		prompt('Package conflict', OPTIONS, safe='drop')

	assert raised.value.save_config is True
	assert raised.value.reason == 'Package conflict'


def test_resolving_manually_and_resuming_retries_the_operation(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(error_recovery, 'open_shell', lambda _hint='': None)
	_answers(monkeypatch, '3', 'y')

	assert prompt('Package conflict', OPTIONS, safe='drop') == RETRY


def test_declining_to_resume_shows_the_choices_again(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(error_recovery, 'open_shell', lambda _hint='': None)
	_answers(monkeypatch, '3', 'n', '2')

	assert prompt('Package conflict', OPTIONS, safe='drop') == 'drop'


def test_a_safe_option_that_is_not_offered_is_a_programming_error() -> None:
	with pytest.raises(ValueError, match='not among the offered choices'):
		prompt('Package conflict', OPTIONS, safe='nonexistent')


def test_a_deliberate_exit_is_not_reported_as_a_crash(capsys: pytest.CaptureFixture[str]) -> None:
	"""
	The abort travels out through `with Installer(...)`. Choosing to stop is a
	decision, so it must not print the "please file a bug" banner.
	"""
	from archinstall.lib.installer import Installer

	installer = Installer.__new__(Installer)
	installer._helper_flags = {}

	propagated = installer.__exit__(InstallationAbortedError, InstallationAbortedError('Package conflict'), None)

	assert propagated is None, 'the abort has to reach main() to be reported there'
	assert 'submit this issue' not in capsys.readouterr().out


def test_a_genuine_failure_still_asks_for_a_bug_report(capsys: pytest.CaptureFixture[str]) -> None:
	from archinstall.lib.installer import Installer

	installer = Installer.__new__(Installer)
	installer._helper_flags = {}

	installer.__exit__(RuntimeError, RuntimeError('boom'), None)

	assert 'submit this issue' in capsys.readouterr().out
