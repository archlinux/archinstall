import json
from pathlib import Path

from pytest import MonkeyPatch

from archinstall.lib.args import ArchConfigHandler
from archinstall.lib.configuration import ConfigurationHandler


def test_user_config_roundtrip(
	monkeypatch: MonkeyPatch,
	config_fixture: Path,
) -> None:
	monkeypatch.setattr('sys.argv', ['archinstall', '--config', str(config_fixture)])

	handler = ArchConfigHandler()
	arch_config = handler.config

	# the version is retrieved dynamically from an installed archinstall package
	# as there is no version present in the test environment we'll set it manually
	arch_config.version = '3.0.2'

	config_output = ConfigurationHandler(arch_config)

	test_out_dir = Path('/tmp/')
	test_out_file = test_out_dir / config_output.user_configuration_file

	config_output.save(test_out_dir)

	result = json.loads(test_out_file.read_text())
	expected = json.loads(config_fixture.read_text())

	# the parsed config will check if the given device exists otherwise
	# it will ignore the modification; as this test will run on various local systems
	# and the CI pipeline there's no good way specify a real device so we'll simply
	# copy the expected result to the actual result
	result['disk_config']['config_type'] = expected['disk_config']['config_type']
	result['disk_config']['device_modifications'] = expected['disk_config']['device_modifications']

	assert json.dumps(
		result['mirror_config'],
		sort_keys=True,
	) == json.dumps(
		expected['mirror_config'],
		sort_keys=True,
	)


def test_creds_roundtrip(
	monkeypatch: MonkeyPatch,
	creds_fixture: Path,
) -> None:
	monkeypatch.setattr('sys.argv', ['archinstall', '--creds', str(creds_fixture)])

	handler = ArchConfigHandler()
	arch_config = handler.config

	config_output = ConfigurationHandler(arch_config)

	test_out_dir = Path('/tmp/')
	test_out_file = test_out_dir / config_output.user_credentials_file

	config_output.save(test_out_dir, creds=True)

	result = json.loads(test_out_file.read_text())
	expected = json.loads(creds_fixture.read_text())

	assert sorted(result.items()) == sorted(expected.items())
