import json
from pathlib import Path

from _pytest.capture import CaptureFixture
from pytest import MonkeyPatch

from archinstall.lib.args import ArchConfigHandler


def _write(tmp_path: Path, config: dict) -> Path:
	path = tmp_path / 'config.json'
	path.write_text(json.dumps(config))
	return path


def test_unknown_keys_are_reported(
	monkeypatch: MonkeyPatch,
	tmp_path: Path,
	capsys: CaptureFixture[str],
) -> None:
	"""A misspelled key must not just leave the option at its default."""
	config_file = _write(tmp_path, {'boot_loader': 'grub', 'timezone': 'UTC'})
	monkeypatch.setattr('sys.argv', ['archinstall', '--config', str(config_file)])

	ArchConfigHandler()

	output = capsys.readouterr()
	assert 'boot_loader' in output.out + output.err


def test_config_written_by_another_version_is_reported(
	monkeypatch: MonkeyPatch,
	tmp_path: Path,
	capsys: CaptureFixture[str],
) -> None:
	config_file = _write(tmp_path, {'version': '0.0.0-ancient', 'timezone': 'UTC'})
	monkeypatch.setattr('sys.argv', ['archinstall', '--config', str(config_file)])

	ArchConfigHandler()

	output = capsys.readouterr()
	assert '0.0.0-ancient' in output.out + output.err
