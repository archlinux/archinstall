from pathlib import Path
from unittest.mock import MagicMock, patch

from archinstall.lib.disk.device_handler import DeviceHandler
from archinstall.lib.disk.utils import mount
from archinstall.lib.models.device import LsblkInfo


def _make_lsblk_info(mountpoint: Path | None, mountpoints: list[Path], fsroots: list[Path]) -> LsblkInfo:
	return LsblkInfo.model_validate(
		{
			'name': 'sda1',
			'path': '/dev/sda1',
			'pkname': 'sda',
			'log-sec': 512,
			'size': 1024 * 1024,
			'pttype': 'gpt',
			'ptuuid': None,
			'rota': False,
			'tran': 'sata',
			'partn': 1,
			'partuuid': None,
			'parttype': None,
			'uuid': None,
			'fstype': 'btrfs',
			'fsver': None,
			'fsavail': None,
			'fsuse%': None,
			'type': 'part',
			'mountpoint': mountpoint,
			'mountpoints': mountpoints,
			'fsroots': fsroots,
		}
	)


def test_get_btrfs_info_with_space_in_mountpoint() -> None:
	mountpoint = Path('/mnt/Cleartext Storage')
	lsblk_info = _make_lsblk_info(
		mountpoint=mountpoint,
		mountpoints=[mountpoint],
		fsroots=[Path('/@data')],
	)

	mock_cmd = MagicMock()
	mock_cmd.decode.return_value = 'ID 256 gen 16 top level 5 path @data\n'

	handler = DeviceHandler.__new__(DeviceHandler)

	with patch('archinstall.lib.disk.device_handler.SysCommand', return_value=mock_cmd) as sys_cmd:
		subvols = handler.get_btrfs_info('/dev/sda1', lsblk_info=lsblk_info)

	sys_cmd.assert_called_once_with(['btrfs', 'subvolume', 'list', '/mnt/Cleartext Storage'])
	assert len(subvols) == 1
	assert subvols[0].name == Path('@data')
	assert subvols[0].mountpoint == mountpoint


def test_mount_with_space_in_target_mountpoint(tmp_path: Path) -> None:
	target = tmp_path / 'Cleartext Storage'
	lsblk_info = _make_lsblk_info(mountpoint=None, mountpoints=[], fsroots=[])

	with (
		patch('archinstall.lib.disk.utils.get_lsblk_info', return_value=lsblk_info),
		patch('archinstall.lib.disk.utils.SysCommand') as sys_cmd,
	):
		mount('/dev/sda1', target, options=['subvol=@'])

	sys_cmd.assert_called_once_with(['mount', '-o', 'subvol=@', '/dev/sda1', str(target)])
