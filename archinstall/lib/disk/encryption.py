from typing import Dict, Optional, Any, TYPE_CHECKING, List

from ..menu.abstract_menu import Selector, AbstractSubMenu
from ..menu.menu import MenuSelectionType
from ..menu.table_selection_menu import TableMenu
from ..models.disk_encryption import EncryptionType, DiskEncryption
from ..user_interaction.partitioning_conf import current_partition_layout
from ..user_interaction.utils import get_password
from ..menu import Menu
from ..general import secret
from ..hsm.fido import Fido2Device, Fido2

if TYPE_CHECKING:
	_: Any


class DiskEncryptionMenu(AbstractSubMenu):
	def __init__(self, data_store: Dict[str, Any], preset: Optional[DiskEncryption], disk_layouts: Dict[str, Any]):
		if preset:
			self._preset = preset
		else:
			self._preset = DiskEncryption()

		self._disk_layouts = disk_layouts
		super().__init__(data_store=data_store)

	def _setup_selection_menu_options(self):
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
				func=lambda preset: select_partitions_to_encrypt(self._disk_layouts, preset),
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

		if not Fido2.get_fido2_devices():
			return str(_('No HSM devices available'))
		return None

	def _prev_disk_layouts(self) -> Optional[str]:
		selector = self._menu_options['partitions']
		if selector.has_selection():
			partitions: List[Any] = selector.current_selection
			output = str(_('Partitions to be encrypted')) + '\n'
			output += current_partition_layout(partitions, with_title=False)
			return output.rstrip()
		return None


def select_encryption_type(preset: EncryptionType) -> Optional[EncryptionType]:
	title = str(_('Select disk encryption option'))
	options = [
		# _type_to_text(EncryptionType.FullDiskEncryption),
		EncryptionType.type_to_text(EncryptionType.Partition)
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
	fido_devices = Fido2.get_fido2_devices()

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


def select_partitions_to_encrypt(disk_layouts: Dict[str, Any], preset: List[Any]) -> List[Any]:
	# If no partitions was marked as encrypted, but a password was supplied and we have some disks to format..
	# Then we need to identify which partitions to encrypt. This will default to / (root).
	all_partitions = []
	for blockdevice in disk_layouts.values():
		if partitions := blockdevice.get('partitions'):
			partitions = [p for p in partitions if p['mountpoint'] != '/boot']
			all_partitions += partitions

	if all_partitions:
		title = str(_('Select which partitions to encrypt'))
		partition_table = current_partition_layout(all_partitions, with_title=False).strip()

		choice = TableMenu(
			title,
			table_data=(all_partitions, partition_table),
			multi=True
		).run()

		match choice.type_:
			case MenuSelectionType.Reset:
				return []
			case MenuSelectionType.Skip:
				return preset
			case MenuSelectionType.Selection:
				return choice.value  # type: ignore

	return []
