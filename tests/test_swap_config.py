import json
from pathlib import Path
from typing import Any

import pytest
from pytest import MonkeyPatch

from archinstall.lib.args import ArchConfigHandler
from archinstall.lib.hardware import MemInfo
from archinstall.lib.installer import _swapfile_size
from archinstall.lib.models.application import SwapConfiguration, ZramAlgorithm, ZramConfiguration
from archinstall.lib.models.device import SectorSize, Size, Unit


@pytest.mark.parametrize(
	'arg, expected',
	[
		# the option held nothing but the zram configuration before the swap file was
		# added, so every shape it used to accept has to keep parsing the same way
		(True, SwapConfiguration(zram=ZramConfiguration(enabled=True))),
		(False, SwapConfiguration(zram=ZramConfiguration(enabled=False))),
		({'enabled': False}, SwapConfiguration(zram=ZramConfiguration(enabled=False))),
		(
			{'enabled': True, 'algorithm': 'lz4'},
			SwapConfiguration(zram=ZramConfiguration(enabled=True, algorithm=ZramAlgorithm.LZ4)),
		),
		# and the current shape
		({'zram': True}, SwapConfiguration(zram=ZramConfiguration(enabled=True))),
		({'swapfile': True}, SwapConfiguration(zram=ZramConfiguration(enabled=False), swapfile=True)),
		(
			{'zram': {'enabled': True, 'algorithm': 'lz4'}, 'swapfile': True},
			SwapConfiguration(zram=ZramConfiguration(enabled=True, algorithm=ZramAlgorithm.LZ4), swapfile=True),
		),
	],
)
def test_swap_config_parsing(arg: bool | dict[str, Any], expected: SwapConfiguration) -> None:
	assert SwapConfiguration.parse_arg(arg) == expected


@pytest.mark.parametrize(
	'config',
	[
		SwapConfiguration(),
		SwapConfiguration(zram=ZramConfiguration(enabled=False)),
		SwapConfiguration(zram=ZramConfiguration(enabled=False), swapfile=True),
		SwapConfiguration(zram=ZramConfiguration(enabled=True, algorithm=ZramAlgorithm.LZ4), swapfile=True),
	],
)
def test_swap_config_round_trip(config: SwapConfiguration) -> None:
	assert SwapConfiguration.parse_arg(config.json()) == config


def test_swap_config_from_config_file(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
	config_file = tmp_path / 'config.json'
	config_file.write_text(json.dumps({'swap': {'zram': {'enabled': True, 'algorithm': 'lz4'}, 'swapfile': True}}))

	monkeypatch.setattr('sys.argv', ['archinstall', '--config', str(config_file)])

	assert ArchConfigHandler().config.swap == SwapConfiguration(
		zram=ZramConfiguration(enabled=True, algorithm=ZramAlgorithm.LZ4),
		swapfile=True,
	)


@pytest.mark.parametrize(
	'mem_total, expected_mib',
	[
		(8125656, 7936),
		(1024 * 1024, 1024),
		(1024 * 1024 + 1, 1025),
	],
)
def test_swapfile_size(monkeypatch: MonkeyPatch, mem_total: int, expected_mib: int) -> None:
	monkeypatch.setattr(
		'archinstall.lib.installer.read_meminfo',
		lambda: MemInfo(mem_total=mem_total, mem_free=0, mem_available=0),
	)

	size = _swapfile_size()

	assert size == Size(expected_mib, Unit.MiB, SectorSize.default())
	# a hibernation image can be as large as the memory it came from, so rounding the
	# size down would leave the last of it with nowhere to go
	assert size >= Size(mem_total, Unit.KiB, SectorSize.default())
