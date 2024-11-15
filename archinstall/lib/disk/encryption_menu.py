from pathlib import Path
from typing import Dict, Optional, Any, TYPE_CHECKING

from . import LvmConfiguration, LvmVolume
from ..disk import (
	DeviceModification,
	DiskLayoutConfiguration,
	PartitionModification,
	DiskEncryption,
	EncryptionType
)
from ..menu import AbstractSubMenu
from .fido import Fido2Device, Fido2
from ..output import FormattedOutput
from ..utils.util import get_password

from archinstall.tui import (
	MenuItemGroup, MenuItem, SelectMenu,
	FrameProperties, Alignment, ResultType
)
from archinstall.lib.menu.menu_helper import MenuHelper


if TYPE_CHECKING:
	_: Any


class DiskEncryptionMenu(AbstractSubMenu):
	def __init__(
		self,
		disk_config: DiskLayoutConfiguration,
		preset: Optional[DiskEncryption] = None
	):
		if preset:
			self._preset = preset
		else:
			self._preset = DiskEncryption()

		self._data_store: Dict[str, Any] = {}
		self._disk_config = disk_config

		menu_optioons = self._define_menu_options()
		self._item_group = MenuItemGroup(menu_optioons, sort_items=False, checkmarks=True)

		super().__init__(self._item_group, data_store=self._data_store, allow_reset=True)

	def _define_menu_options(self) -> list[MenuItem]:
		return [
			MenuItem(
				text=str(_('Encryption type')),
				action=lambda x: select_encryption_type(self._disk_config, x),
				value=self._preset.encryption_type,
				preview_action=self._preview,
				key='encryption_type'
			),
			MenuItem(
				text=str(_('Encryption password')),
				action=lambda x: select_encrypted_password(),
				value=self._preset.encryption_password,
				dependencies=[self._check_dep_enc_type],
				preview_action=self._preview,
				key='encryption_password'
			),
			MenuItem(
				text=str(_('Partitions')),
				action=lambda x: select_partitions_to_encrypt(self._disk_config.device_modifications, x),
				value=self._preset.partitions,
				dependencies=[self._check_dep_partitions],
				preview_action=self._preview,
				key='partitions'
			),
			MenuItem(
				text=str(_('LVM volumes')),
				action=lambda x: self._select_lvm_vols(x),
				value=self._preset.lvm_volumes,
				dependencies=[self._check_dep_lvm_vols],
				preview_action=self._preview,
				key='lvm_vols'
			),
			MenuItem(
				text=str(_('HSM')),
				action=lambda x: select_hsm(x),
				value=self._preset.hsm_device,
				dependencies=[self._check_dep_enc_type],
				preview_action=self._preview,
				key='HSM'
			),
		]

	def _select_lvm_vols(self, preset: list[LvmVolume]) -> list[LvmVolume]:
		if self._disk_config.lvm_config:
			return select_lvm_vols_to_encrypt(self._disk_config.lvm_config, preset=preset)
		return []

	def _check_dep_enc_type(self) -> bool:
		enc_type: Optional[EncryptionType] = self._item_group.find_by_key('encryption_type').value
		if enc_type and enc_type != EncryptionType.NoEncryption:
			return True
		return False

	def _check_dep_partitions(self) -> bool:
		enc_type: Optional[EncryptionType] = self._item_group.find_by_key('encryption_type').value
		if enc_type and enc_type in [EncryptionType.Luks, EncryptionType.LvmOnLuks]:
			return True
		return False

	def _check_dep_lvm_vols(self) -> bool:
		enc_type: Optional[EncryptionType] = self._item_group.find_by_key('encryption_type').value
		if enc_type and enc_type == EncryptionType.LuksOnLvm:
			return True
		return False

	def run(self) -> Optional[DiskEncryption]:
		super().run()

		enc_type: Optional[EncryptionType] = self._item_group.find_by_key('encryption_type').value
		enc_password: Optional[str] = self._item_group.find_by_key('encryption_password').value
		enc_partitions = self._item_group.find_by_key('partitions').value
		enc_lvm_vols = self._item_group.find_by_key('lvm_vols').value

		assert enc_type is not None
		assert enc_partitions is not None
		assert enc_lvm_vols is not None

		if enc_type in [EncryptionType.Luks, EncryptionType.LvmOnLuks] and enc_partitions:
			enc_lvm_vols = []

		if enc_type == EncryptionType.LuksOnLvm:
			enc_partitions = []

		if enc_type != EncryptionType.NoEncryption and enc_password and (enc_partitions or enc_lvm_vols):
			return DiskEncryption(
				encryption_password=enc_password,
				encryption_type=enc_type,
				partitions=enc_partitions,
				lvm_volumes=enc_lvm_vols,
				hsm_device=self._data_store.get('HSM', None)
			)

		return None

	def _preview(self, item: MenuItem) -> Optional[str]:
		output = ''

		if (enc_type := self._prev_type()) is not None:
			output += enc_type

		if (enc_pwd := self._prev_password()) is not None:
			output += f'\n{enc_pwd}'

		if (fido_device := self._prev_hsm()) is not None:
			output += f'\n{fido_device}'

		if (partitions := self._prev_partitions()) is not None:
			output += f'\n\n{partitions}'

		if (lvm := self._prev_lvm_vols()) is not None:
			output += f'\n\n{lvm}'

		if not output:
			return None

		return output

	def _prev_type(self) -> Optional[str]:
		enc_type = self._item_group.find_by_key('encryption_type').value

		if enc_type:
			enc_text = EncryptionType.type_to_text(enc_type)
			return f'{str(_("Encryption type"))}: {enc_text}'

		return None

	def _prev_password(self) -> Optional[str]:
		enc_pwd = self._item_group.find_by_key('encryption_password').value

		if enc_pwd:
			pwd_text = '*' * len(enc_pwd)
			return f'{str(_("Encryption password"))}: {pwd_text}'

		return None

	def _prev_partitions(self) -> Optional[str]:
		partitions: Optional[list[PartitionModification]] = self._item_group.find_by_key('partitions').value

		if partitions:
			output = str(_('Partitions to be encrypted')) + '\n'
			output += FormattedOutput.as_table(partitions)
			return output.rstrip()

		return None

	def _prev_lvm_vols(self) -> Optional[str]:
		volumes: Optional[list[PartitionModification]] = self._item_group.find_by_key('lvm_vols').value

		if volumes:
			output = str(_('LVM volumes to be encrypted')) + '\n'
			output += FormattedOutput.as_table(volumes)
			return output.rstrip()

		return None

	def _prev_hsm(self) -> Optional[str]:
		fido_device: Optional[Fido2Device] = self._item_group.find_by_key('HSM').value

		if not fido_device:
			return None

		output = str(fido_device.path)
		output += f' ({fido_device.manufacturer}, {fido_device.product})'
		return f'{str(_("HSM device"))}: {output}'


def select_encryption_type(disk_config: DiskLayoutConfiguration, preset: EncryptionType) -> Optional[EncryptionType]:
	options: list[EncryptionType] = []
	preset_value = EncryptionType.type_to_text(preset)

	if disk_config.lvm_config:
		options = [EncryptionType.LvmOnLuks, EncryptionType.LuksOnLvm]
	else:
		options = [EncryptionType.Luks]

	items = [MenuItem(EncryptionType.type_to_text(o), value=o) for o in options]
	group = MenuItemGroup(items)
	group.set_focus_by_value(preset_value)

	result = SelectMenu(
		group,
		allow_skip=True,
		allow_reset=True,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(str(_('Encryption type')))
	).run()

	match result.type_:
		case ResultType.Reset: return None
		case ResultType.Skip: return preset
		case ResultType.Selection:
			return result.get_value()


def select_encrypted_password() -> Optional[str]:
	header = str(_('Enter disk encryption password (leave blank for no encryption)')) + '\n'
	password = get_password(
		text=str(_('Disk encryption password')),
		header=header,
		allow_skip=True
	)

	return password


def select_hsm(preset: Optional[Fido2Device] = None) -> Optional[Fido2Device]:
	header = str(_('Select a FIDO2 device to use for HSM'))

	try:
		fido_devices = Fido2.get_fido2_devices()
	except ValueError:
		return None

	if fido_devices:
		group, table_header = MenuHelper.create_table(data=fido_devices)
		header = f'{header}\n\n{table_header}'

		result = SelectMenu(
			group,
			header=header,
			alignment=Alignment.CENTER,
		).run()

		match result.type_:
			case ResultType.Reset: return None
			case ResultType.Skip: return preset
			case ResultType.Selection:
				return result.get_value()

	return None


def select_partitions_to_encrypt(
	modification: list[DeviceModification],
	preset: list[PartitionModification]
) -> list[PartitionModification]:
	partitions: list[PartitionModification] = []

	# do not allow encrypting the boot partition
	for mod in modification:
		partitions += list(filter(lambda x: x.mountpoint != Path('/boot'), mod.partitions))

	# do not allow encrypting existing partitions that are not marked as wipe
	avail_partitions = list(filter(lambda x: not x.exists(), partitions))

	if avail_partitions:
		group, header = MenuHelper.create_table(data=avail_partitions)

		result = SelectMenu(
			group,
			header=header,
			alignment=Alignment.CENTER,
			multi=True
		).run()

		match result.type_:
			case ResultType.Reset: return []
			case ResultType.Skip: return preset
			case ResultType.Selection:
				partitions = result.get_values()
				return partitions

	return []


def select_lvm_vols_to_encrypt(
	lvm_config: LvmConfiguration,
	preset: list[LvmVolume]
) -> list[LvmVolume]:
	volumes: list[LvmVolume] = lvm_config.get_all_volumes()

	if volumes:
		group, header = MenuHelper.create_table(data=volumes)

		result = SelectMenu(
			group,
			header=header,
			alignment=Alignment.CENTER,
			multi=True
		).run()

		match result.type_:
			case ResultType.Reset: return []
			case ResultType.Skip: return preset
			case ResultType.Selection:
				volumes = result.get_values()
				return volumes

	return []
