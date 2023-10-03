from pathlib import Path
from typing import Dict, Optional, Any, TYPE_CHECKING, List

from ..disk import (
	DeviceModification,
	DiskLayoutConfiguration,
	PartitionModification,
	DiskEncryption,
	EncryptionType
)
from ..menu import (
	Selector,
	AbstractSubMenu,
	MenuSelectionType,
	TableMenu
)
from ..interactions.utils import get_password
from ..menu import Menu
from ..general import secret
from .fido import Fido2Device, Fido2
from ..output import FormattedOutput

if TYPE_CHECKING:
	_: Any


class DiskEncryptionMenu(AbstractSubMenu):
	def __init__(
		self,
		disk_config: DiskLayoutConfiguration,
		data_store: Dict[str, Any],
		preset: Optional[DiskEncryption] = None
	):
		if preset:
			self._preset = preset
		else:
			self._preset = DiskEncryption()

		self._disk_config = disk_config
		super().__init__(data_store=data_store)

	def setup_selection_menu_options(self):
		self._menu_options['encryption_password'] = \
			Selector(
				_('Encryption password'),
				lambda x: select_encrypted_password(),
				display_func=lambda x: secret(x) if x else '',
				default=self._preset.encryption_password,
				enabled=True
			)
		self._menu_options['encryption_type'] = \
			Selector(
				_('Encryption type'),
				func=lambda preset: select_encryption_type(preset),
				display_func=lambda x: EncryptionType.type_to_text(x) if x else None,
				dependencies=['encryption_password'],
				default=self._preset.encryption_type,
				enabled=True
			)
		self._menu_options['partitions'] = \
			Selector(
				_('Partitions'),
				func=lambda preset: select_partitions_to_encrypt(self._disk_config.device_modifications, preset),
				display_func=lambda x: f'{len(x)} {_("Partitions")}' if x else None,
				dependencies=['encryption_password'],
				default=self._preset.partitions,
				preview_func=self._prev_disk_layouts,
				enabled=True
			)
		self._menu_options['HSM'] = \
			Selector(
				description=_('Use HSM to unlock encrypted drive'),
				func=lambda preset: select_hsm(preset),
				display_func=lambda x: self._display_hsm(x),
				preview_func=self._prev_hsm,
				dependencies=['encryption_password'],
				default=self._preset.hsm_device,
				enabled=True
			)

	def run(self, allow_reset: bool = True) -> Optional[DiskEncryption]:
		super().run(allow_reset=allow_reset)

		if self._data_store.get('encryption_password', None):
			return DiskEncryption(
				encryption_password=self._data_store.get('encryption_password', None),
				encryption_type=self._data_store['encryption_type'],
				partitions=self._data_store.get('partitions', None),
				hsm_device=self._data_store.get('HSM', None)
			)

		return None

	def _display_hsm(self, device: Optional[Fido2Device]) -> Optional[str]:
		if device:
			return device.manufacturer

		return None

	def _prev_disk_layouts(self) -> Optional[str]:
		partitions: Optional[List[PartitionModification]] = self._menu_options['partitions'].current_selection
		if partitions:
			output = str(_('Partitions to be encrypted')) + '\n'
			output += FormattedOutput.as_table(partitions)
			return output.rstrip()

		return None

	def _prev_hsm(self) -> Optional[str]:
		try:
			Fido2.get_fido2_devices()
		except ValueError:
			return str(_('Unable to determine fido2 devices. Is libfido2 installed?'))

		fido_device: Optional[Fido2Device] = self._menu_options['HSM'].current_selection

		if fido_device:
			output = '{}: {}'.format(str(_('Path')), fido_device.path)
			output += '{}: {}'.format(str(_('Manufacturer')), fido_device.manufacturer)
			output += '{}: {}'.format(str(_('Product')), fido_device.product)
			return output

		return None


def select_encryption_type(preset: EncryptionType) -> Optional[EncryptionType]:
	title = str(_('Select disk encryption option'))
	options = [
		EncryptionType.type_to_text(EncryptionType.Luks)
	]

	preset_value = EncryptionType.type_to_text(preset)
	choice = Menu(title, options, preset_values=preset_value).run()

	match choice.type_:
		case MenuSelectionType.Reset: return None
		case MenuSelectionType.Skip: return preset
		case MenuSelectionType.Selection: return EncryptionType.text_to_type(choice.value)  # type: ignore


def select_encrypted_password() -> Optional[str]:
	if passwd := get_password(prompt=str(_('Enter disk encryption password (leave blank for no encryption): '))):
		return passwd
	return None


def select_hsm(preset: Optional[Fido2Device] = None) -> Optional[Fido2Device]:
	title = _('Select a FIDO2 device to use for HSM')

	try:
		fido_devices = Fido2.get_fido2_devices()
	except ValueError:
		return None

	if fido_devices:
		choice = TableMenu(title, data=fido_devices).run()
		match choice.type_:
			case MenuSelectionType.Reset:
				return None
			case MenuSelectionType.Skip:
				return preset
			case MenuSelectionType.Selection:
				return choice.value  # type: ignore

	return None


def select_partitions_to_encrypt(
	modification: List[DeviceModification],
	preset: List[PartitionModification]
) -> List[PartitionModification]:
	partitions: List[PartitionModification] = []

	# do not allow encrypting the boot partition
	for mod in modification:
		partitions += list(filter(lambda x: x.mountpoint != Path('/boot'), mod.partitions))

	# do not allow encrypting existing partitions that are not marked as wipe
	avail_partitions = list(filter(lambda x: not x.exists(), partitions))

	if avail_partitions:
		title = str(_('Select which partitions to encrypt'))
		partition_table = FormattedOutput.as_table(avail_partitions)

		choice = TableMenu(
			title,
			table_data=(avail_partitions, partition_table),
			preset=preset,
			multi=True
		).run()

		match choice.type_:
			case MenuSelectionType.Reset:
				return []
			case MenuSelectionType.Skip:
				return preset
			case MenuSelectionType.Selection:
				return choice.multi_value
	return []
