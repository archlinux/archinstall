from pathlib import Path
from typing import override

from archinstall.lib.menu.helpers import Input, Selection, Table
from archinstall.lib.menu.menu_helper import MenuHelper
from archinstall.lib.models.device import (
	DeviceModification,
	DiskEncryption,
	EncryptionType,
	LvmConfiguration,
	LvmVolume,
	PartitionModification,
)
from archinstall.lib.translationhandler import tr
from archinstall.tui.ui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.ui.result import ResultType

from ..menu.abstract_menu import AbstractSubMenu
from ..models.device import DEFAULT_ITER_TIME, Fido2Device
from ..models.users import Password
from ..output import FormattedOutput
from ..utils.util import get_password
from .fido import Fido2


class DiskEncryptionMenu(AbstractSubMenu[DiskEncryption]):
	def __init__(
		self,
		device_modifications: list[DeviceModification],
		lvm_config: LvmConfiguration | None = None,
		preset: DiskEncryption | None = None,
	):
		if preset:
			self._enc_config = preset
		else:
			self._enc_config = DiskEncryption()

		self._device_modifications = device_modifications
		self._lvm_config = lvm_config

		menu_options = self._define_menu_options()
		self._item_group = MenuItemGroup(menu_options, sort_items=False, checkmarks=True)

		super().__init__(
			self._item_group,
			self._enc_config,
			allow_reset=True,
		)

	def _define_menu_options(self) -> list[MenuItem]:
		return [
			MenuItem(
				text=tr('Encryption type'),
				action=lambda x: select_encryption_type(self._lvm_config, x),
				value=self._enc_config.encryption_type,
				preview_action=self._prev_type,
				key='encryption_type',
			),
			MenuItem(
				text=tr('Encryption password'),
				action=lambda x: select_encrypted_password(),
				value=self._enc_config.encryption_password,
				dependencies=[self._check_dep_enc_type],
				preview_action=self._prev_password,
				key='encryption_password',
			),
			MenuItem(
				text=tr('Iteration time'),
				action=select_iteration_time,
				value=self._enc_config.iter_time,
				dependencies=[self._check_dep_enc_type],
				preview_action=self._prev_iter_time,
				key='iter_time',
			),
			MenuItem(
				text=tr('Partitions'),
				action=lambda x: select_partitions_to_encrypt(self._device_modifications, x),
				value=self._enc_config.partitions,
				dependencies=[self._check_dep_partitions],
				preview_action=self._prev_partitions,
				key='partitions',
			),
			MenuItem(
				text=tr('LVM volumes'),
				action=self._select_lvm_vols,
				value=self._enc_config.lvm_volumes,
				dependencies=[self._check_dep_lvm_vols],
				preview_action=self._prev_lvm_vols,
				key='lvm_volumes',
			),
			MenuItem(
				text=tr('HSM'),
				action=select_hsm,
				value=self._enc_config.hsm_device,
				dependencies=[self._check_dep_enc_type],
				preview_action=self._prev_hsm,
				key='hsm_device',
			),
		]

	def _select_lvm_vols(self, preset: list[LvmVolume]) -> list[LvmVolume]:
		if self._lvm_config:
			return select_lvm_vols_to_encrypt(self._lvm_config, preset=preset)
		return []

	def _check_dep_enc_type(self) -> bool:
		enc_type: EncryptionType | None = self._item_group.find_by_key('encryption_type').value
		if enc_type and enc_type != EncryptionType.NoEncryption:
			return True
		return False

	def _check_dep_partitions(self) -> bool:
		enc_type: EncryptionType | None = self._item_group.find_by_key('encryption_type').value
		if enc_type and enc_type in [EncryptionType.Luks, EncryptionType.LvmOnLuks]:
			return True
		return False

	def _check_dep_lvm_vols(self) -> bool:
		enc_type: EncryptionType | None = self._item_group.find_by_key('encryption_type').value
		if enc_type and enc_type == EncryptionType.LuksOnLvm:
			return True
		return False

	@override
	def run(self) -> DiskEncryption | None:
		enc_config = super().run()
		if enc_config is None:
			return None

		enc_type: EncryptionType | None = self._item_group.find_by_key('encryption_type').value
		enc_password: Password | None = self._item_group.find_by_key('encryption_password').value
		iter_time: int | None = self._item_group.find_by_key('iter_time').value
		enc_partitions = self._item_group.find_by_key('partitions').value
		enc_lvm_vols = self._item_group.find_by_key('lvm_volumes').value

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
				hsm_device=enc_config.hsm_device,
				iter_time=iter_time or DEFAULT_ITER_TIME,
			)

		return None

	def _preview(self, item: MenuItem) -> str | None:
		output = ''

		if (enc_type := self._prev_type(item)) is not None:
			output += enc_type

		if (enc_pwd := self._prev_password(item)) is not None:
			output += f'\n{enc_pwd}'

		if (iter_time := self._prev_iter_time(item)) is not None:
			output += f'\n{iter_time}'

		if (fido_device := self._prev_hsm(item)) is not None:
			output += f'\n{fido_device}'

		if (partitions := self._prev_partitions(item)) is not None:
			output += f'\n\n{partitions}'

		if (lvm := self._prev_lvm_vols(item)) is not None:
			output += f'\n\n{lvm}'

		if not output:
			return None

		return output

	def _prev_type(self, item: MenuItem) -> str | None:
		enc_type = self._item_group.find_by_key('encryption_type').value

		if enc_type:
			enc_text = enc_type.type_to_text()
			return f'{tr("Encryption type")}: {enc_text}'

		return None

	def _prev_password(self, item: MenuItem) -> str | None:
		if item.value:
			return f'{tr("Encryption password")}: {item.value.hidden()}'

		return None

	def _prev_partitions(self, item: MenuItem) -> str | None:
		if item.value:
			output = tr('Partitions to be encrypted') + '\n'
			output += FormattedOutput.as_table(item.value)
			return output.rstrip()

		return None

	def _prev_lvm_vols(self, item: MenuItem) -> str | None:
		if item.value:
			output = tr('LVM volumes to be encrypted') + '\n'
			output += FormattedOutput.as_table(item.value)
			return output.rstrip()

		return None

	def _prev_hsm(self, item: MenuItem) -> str | None:
		if not item.value:
			return None

		fido_device: Fido2Device = item.value

		output = str(fido_device.path)
		output += f' ({fido_device.manufacturer}, {fido_device.product})'
		return f'{tr("HSM device")}: {output}'

	def _prev_iter_time(self, item: MenuItem) -> str | None:
		if item.value:
			iter_time = item.value
			enc_type = self._item_group.find_by_key('encryption_type').value

			if iter_time and enc_type != EncryptionType.NoEncryption:
				return f'{tr("Iteration time")}: {iter_time}ms'

		return None


def select_encryption_type(
	lvm_config: LvmConfiguration | None = None,
	preset: EncryptionType | None = None,
) -> EncryptionType | None:
	options: list[EncryptionType] = []

	if lvm_config:
		options = [EncryptionType.LvmOnLuks, EncryptionType.LuksOnLvm]
	else:
		options = [EncryptionType.Luks]

	if not preset:
		preset = options[0]

	preset_value = preset.type_to_text()

	items = [MenuItem(o.type_to_text(), value=o) for o in options]
	group = MenuItemGroup(items)
	group.set_focus_by_value(preset_value)

	result = Selection[EncryptionType](
		group,
		header=tr('Select encryption type'),
		allow_skip=True,
		allow_reset=True,
	).show()

	match result.type_:
		case ResultType.Reset:
			return None
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return result.get_value()


def select_encrypted_password() -> Password | None:
	header = tr('Enter disk encryption password (leave blank for no encryption)') + '\n'
	password = get_password(
		header=header,
		allow_skip=True,
	)

	return password


def select_hsm(preset: Fido2Device | None = None) -> Fido2Device | None:
	header = tr('Select a FIDO2 device to use for HSM') + '\n'

	try:
		fido_devices = Fido2.get_cryptenroll_devices()
	except ValueError:
		return None

	if fido_devices:
		group = MenuHelper(data=fido_devices).create_menu_group()

		result = Selection[Fido2Device](
			group,
			header=header,
			allow_skip=True,
		).show()

		match result.type_:
			case ResultType.Reset:
				return None
			case ResultType.Skip:
				return preset
			case ResultType.Selection:
				return result.get_value()

	return None


def select_partitions_to_encrypt(
	modification: list[DeviceModification],
	preset: list[PartitionModification],
) -> list[PartitionModification]:
	partitions: list[PartitionModification] = []

	# do not allow encrypting the boot partition
	for mod in modification:
		partitions += [p for p in mod.partitions if p.mountpoint != Path('/boot') and not p.is_swap()]

	# do not allow encrypting existing partitions that are not marked as wipe
	avail_partitions = [p for p in partitions if not p.exists()]

	if avail_partitions:
		group = MenuItemGroup.from_objects(partitions)
		group.set_selected_by_value(preset)

		result = Table[PartitionModification](
			header=tr('Select disks for the installation'),
			group=group,
			allow_skip=True,
			multi=True,
		).show()

		match result.type_:
			case ResultType.Reset:
				return []
			case ResultType.Skip:
				return preset
			case ResultType.Selection:
				partitions = result.get_values()
				return partitions

	return []


def select_lvm_vols_to_encrypt(
	lvm_config: LvmConfiguration,
	preset: list[LvmVolume],
) -> list[LvmVolume]:
	volumes: list[LvmVolume] = lvm_config.get_all_volumes()

	if volumes:
		group = MenuItemGroup.from_objects(volumes)
		group.set_selected_by_value(preset)

		result = Table[LvmVolume](
			header=tr('Select disks for the installation'),
			group=group,
			allow_skip=True,
			multi=True,
		).show()

		match result.type_:
			case ResultType.Reset:
				return []
			case ResultType.Skip:
				return preset
			case ResultType.Selection:
				volumes = result.get_values()
				return volumes

	return []


def select_iteration_time(preset: int | None = None) -> int | None:
	header = tr('Enter iteration time for LUKS encryption (in milliseconds)') + '\n'
	header += tr('Higher values increase security but slow down boot time') + '\n'
	header += tr(f'Default: {DEFAULT_ITER_TIME}ms, Recommended range: 1000-60000') + '\n'

	def validate_iter_time(value: str) -> str | None:
		try:
			iter_time = int(value)
			if iter_time < 100:
				return tr('Iteration time must be at least 100ms')
			if iter_time > 120000:
				return tr('Iteration time must be at most 120000ms')
			return None
		except ValueError:
			return tr('Please enter a valid number')

	result = Input(
		header=header,
		allow_skip=True,
		default_value=str(preset) if preset else str(DEFAULT_ITER_TIME),
		validator_callback=validate_iter_time,
	).show()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			if not result.get_value():
				return preset
			return int(result.get_value())
		case ResultType.Reset:
			return None
