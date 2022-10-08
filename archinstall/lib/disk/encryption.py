from pathlib import Path
from typing import Dict, Optional, Any, TYPE_CHECKING, List

from ..menu.abstract_menu import Selector, AbstractSubMenu
from ..menu.menu import MenuSelectionType
from ..menu.table_selection_menu import TableMenu
from ..models.disk_encryption import EncryptionType, DiskEncryption
from ..user_interaction.partitioning_conf import current_partition_layout
from ..user_interaction.utils import get_password
from ..menu import Menu
from ..general import secret
from ..hsm.fido import get_fido2_devices, Fido2Device

if TYPE_CHECKING:
	_: Any


class DiskEncryptionMenu(AbstractSubMenu):
	def __init__(self, data_store: Dict, preset: Optional[DiskEncryption], disk_layouts: Dict[str, Any]):
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
				display_func=lambda x: _type_to_text(x) if x else None,
				dependencies=['encryption_password'],
				default=self._preset.encryption_type,
				enabled=True
			)
		self._menu_options['partitions'] = \
			Selector(
				_('Partitions'),
				func=lambda preset: select_partitions_to_encrypt(self._disk_layouts, preset),
				display_func=lambda x: _type_to_text(x) if x else None,
				dependencies=['encryption_password'],
				default=self._preset.partitions,
				enabled=True
			)
		self._menu_options['HSM'] = \
			Selector(
				description=_('Use HSM to unlock encrypted drive'),
				func=lambda preset: select_hsm(preset),
				display_func=lambda x: _display_hsm(x),
				dependencies=['encryption_password'],
				default=self._preset.hsm_device,
				enabled=True
			)

	def run(self) -> Optional[DiskEncryption]:
		super().run()

		if self._data_store['encryption_password']:
			return DiskEncryption(
				encryption_password=self._data_store.get('encryption_password', None),
				encryption_type=self._data_store['encryption_type'],
				partitions=self._data_store.get('partitions', None),
				hsm_device=self._data_store.get('hsm_device', None)
			)

		return None


def _display_hsm(device: Optional[Fido2Device]) -> Optional[str]:
	if device:
		return device.manufacturer

	if not get_fido2_devices():
		return str(_('No HSM devices available'))
	return None


def _encryption_type_mapper() -> Dict[str, EncryptionType]:
	return {
		# str(_('Full disk encryption')): EncryptionType.FullDiskEncryption,
		str(_('Partition encryption')): EncryptionType.Partition
	}


def _text_to_type(text: str) -> EncryptionType:
	mapping = _encryption_type_mapper()
	return mapping[text]


def _type_to_text(type_: EncryptionType) -> str:
	mapping = _encryption_type_mapper()
	type_to_text = {type_: text for text, type_ in mapping.items()}
	return type_to_text[type_]


def select_encryption_type(preset: Optional[DiskEncryption]) -> Optional[EncryptionType]:
	title = str(_('Select disk encryption option'))
	options = [
		# _type_to_text(EncryptionType.FullDiskEncryption),
		_type_to_text(EncryptionType.Partition)
	]

	choice = Menu(title, options).run()

	match choice.type_:
		case MenuSelectionType.Reset: return None
		case MenuSelectionType.Skip: return preset
		case MenuSelectionType.Selection: return _text_to_type(choice.value)


def select_encrypted_password() -> Optional[str]:
	if passwd := get_password(prompt=str(_('Enter disk encryption password (leave blank for no encryption): '))):
		return passwd
	return None


def select_hsm(preset: Optional[Path] = None) -> Optional[Fido2Device]:
	title = _('Select a FIDO2 device to use for HSM')
	fido_devices = get_fido2_devices()

	if fido_devices:
		maybe_device = TableMenu(title, data=fido_devices, default=preset).run()
		return maybe_device

	return None


def select_partitions_to_encrypt(disk_layouts: Dict[str, Any], preset: Dict[str, Any]) -> List[Any]:
	# If no partitions was marked as encrypted, but a password was supplied and we have some disks to format..
	# Then we need to identify which partitions to encrypt. This will default to / (root).
	all_partitions = []
	for blockdevice in disk_layouts.values():
		if partitions := blockdevice.get('partitions'):
			all_partitions += partitions

	if all_partitions:
		title = str(_('Select which partitions to encrypt'))
		partition_table = current_partition_layout(all_partitions, with_title=False).strip()
		maybe_device = TableMenu(
			title,
			table_data=(all_partitions, partition_table),
			multi=True,
			default=preset
		).run()



		# indexes = select_encrypted_partitions(
		# 	title=_('Select which partitions to encrypt:'),
		# 	partitions=storage['arguments']['disk_layouts'][blockdevice]['partitions'],
		# 	filter_=(lambda p: p['mountpoint'] != '/boot')
		# )
		#
		# for partition_index in indexes:
		# 	partition = storage['arguments']['disk_layouts'][blockdevice]['partitions'][partition_index]
		# 	partition['encrypted'] = True
		# 	partition['!password'] = storage['arguments']['!encryption-password']
		#
		# 	# We make sure generate-encryption-key-file is set on additional partitions
		# 	# other than the root partition. Otherwise they won't unlock properly #1279
		# 	if partition['mountpoint'] != '/':
		# 		partition['generate-encryption-key-file'] = True
