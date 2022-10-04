from pathlib import Path
from typing import Dict, Optional, Any, TYPE_CHECKING

from ..menu.abstract_menu import Selector, AbstractSubMenu
from ..menu.menu import MenuSelectionType
from ..menu.table_selection_menu import TableMenu
from ..models.disk_encryption import EncryptionType, DiskEncryption
from ..user_interaction.utils import get_password
from ..menu import Menu
from ..general import secret
from ..hsm.fido import get_fido2_devices, Fido2Device

if TYPE_CHECKING:
	_: Any


class DiskEncryptionMenu(AbstractSubMenu):
	def __init__(self, data_store: Dict):
		super().__init__(data_store=data_store)

	def _setup_selection_menu_options(self):
		self._menu_options['encryption_password'] = \
			Selector(
				_('Encryption password'),
				lambda x: select_encrypted_password(),
				display_func=lambda x: secret(x) if x else 'None',
				enabled=True
			)
		self._menu_options['encryption_type'] = \
			Selector(
				_('Encryption type'),
				func=lambda preset: select_encryption_type(preset),
				display_func=lambda x: _type_to_text(x) if x else None,
				dependencies=['encryption_password'],
				enabled=True
			)
		self._menu_options['HSM'] = \
			Selector(
				description=_('Use HSM to unlock encrypted drive'),
				func=lambda preset: select_hsm(preset),
				display_func=lambda x: x.manufacturer if x else None,
				dependencies=['encryption_password'],
				enabled=True
			)

	def run(self):
		super().run()
		return DiskEncryption(
			encryption_type=self._data_store['encryption_type'],
			encryption_password=self._data_store['encryption_password'],
			partitions=self._data_store.get('partitions', None),   xxxx implement partition selection
			hsm_device=self._data_store['hsm_device']
		)


def _encryption_type_mapper() -> Dict[str, EncryptionType]:
	return {
		str(_('Full disk encryption')): EncryptionType.FullDiskEncryption,
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
		_type_to_text(EncryptionType.FullDiskEncryption),
		_type_to_text(EncryptionType.Partition)
	]

	choice = Menu(title, options, allow_reset=True).run()

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
	maybe_device = TableMenu(title, fido_devices, default=preset).run()
	return maybe_device
