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


def _disk_config(partition_overrides: dict | None = None) -> dict:
	partition = {
		'obj_id': 'x',
		'status': 'create',
		'type': 'primary',
		'start': {'value': 1, 'unit': 'MiB', 'sector_size': {'value': 512, 'unit': 'B'}},
		'size': {'value': 100, 'unit': 'MiB', 'sector_size': {'value': 512, 'unit': 'B'}},
		'fs_type': 'ext4',
		'mountpoint': '/',
		'mount_options': [],
		'flags': [],
		'dev_path': None,
		'btrfs': [],
	}
	partition.update(partition_overrides or {})

	return {
		'config_type': 'manual_partitioning',
		'device_modifications': [{'device': '/dev/sda', 'wipe': True, 'partitions': [partition]}],
	}


def test_unknown_keys_are_found_inside_the_disk_configuration(
	monkeypatch: MonkeyPatch,
	tmp_path: Path,
	capsys: CaptureFixture[str],
	probed_devices: list[Path],
) -> None:
	"""A misspelled partition key must be named, not dropped."""
	assert probed_devices, 'the fixture registers a device the config names'

	config_file = _write(
		tmp_path,
		{'timezone': 'UTC', 'disk_config': _disk_config({'mountpiont': '/x'})},
	)
	monkeypatch.setattr('sys.argv', ['archinstall', '--config', str(config_file)])

	ArchConfigHandler()

	assert 'mountpiont' in capsys.readouterr().out + capsys.readouterr().err


def test_unknown_keys_are_found_in_a_nested_size(
	monkeypatch: MonkeyPatch,
	tmp_path: Path,
	capsys: CaptureFixture[str],
	probed_devices: list[Path],
) -> None:
	assert probed_devices, 'the fixture registers a device the config names'

	config = _disk_config()
	config['device_modifications'][0]['partitions'][0]['start']['valu'] = 1

	config_file = _write(tmp_path, {'timezone': 'UTC', 'disk_config': config})
	monkeypatch.setattr('sys.argv', ['archinstall', '--config', str(config_file)])

	ArchConfigHandler()

	assert 'valu' in capsys.readouterr().out + capsys.readouterr().err


def test_a_correct_disk_configuration_is_not_reported(
	monkeypatch: MonkeyPatch,
	tmp_path: Path,
	capsys: CaptureFixture[str],
	probed_devices: list[Path],
) -> None:
	assert probed_devices, 'the fixture registers a device the config names'

	config_file = _write(tmp_path, {'timezone': 'UTC', 'disk_config': _disk_config()})
	monkeypatch.setattr('sys.argv', ['archinstall', '--config', str(config_file)])

	ArchConfigHandler()

	assert 'Ignoring unknown keys in the disk configuration' not in capsys.readouterr().out + capsys.readouterr().err
