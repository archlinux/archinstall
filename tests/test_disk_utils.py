from pathlib import Path

from pytest import MonkeyPatch

from archinstall.lib.disk.utils import get_unique_path_for_device


def test_get_unique_path_for_device_prefers_wwn_and_nvme_eui(
	tmp_path: Path,
	monkeypatch: MonkeyPatch,
) -> None:
	dev_dir = tmp_path / 'dev'
	by_id_dir = dev_dir / 'disk' / 'by-id'
	by_id_dir.mkdir(parents=True)

	sda = dev_dir / 'sda'
	sda.touch()
	nvme0n1 = dev_dir / 'nvme0n1'
	nvme0n1.touch()
	sdb = dev_dir / 'sdb'
	sdb.touch()

	ata_link = by_id_dir / 'ata-Samsung_SSD_1234'
	wwn_link = by_id_dir / 'wwn-0x5002538e00000000'
	ata_link.symlink_to(sda)
	wwn_link.symlink_to(sda)

	nvme_model_link = by_id_dir / 'nvme-Samsung_SSD_980_PRO_ABCD'
	nvme_eui_link = by_id_dir / 'nvme-eui.002538b123456789'
	nvme_model_link.symlink_to(nvme0n1)
	nvme_eui_link.symlink_to(nvme0n1)

	usb_link = by_id_dir / 'usb-Generic_Flash_Disk-0:0'
	usb_link.symlink_to(sdb)

	orig_glob = Path.glob

	def fake_glob(self: Path, pattern: str) -> list[Path]:
		if self == Path('/dev/disk/by-id'):
			return [
				wwn_link,
				ata_link,
				nvme_eui_link,
				nvme_model_link,
				usb_link,
			]
		return list(orig_glob(self, pattern))

	monkeypatch.setattr(Path, 'glob', fake_glob)

	assert get_unique_path_for_device(sda) == wwn_link
	assert get_unique_path_for_device(nvme0n1) == nvme_eui_link
	assert get_unique_path_for_device(sdb) == usb_link
	assert get_unique_path_for_device(dev_dir / 'sdc') is None
