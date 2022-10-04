from pathlib import Path
from typing import Dict, Optional, Any, TYPE_CHECKING

from ..menu.abstract_menu import Selector, AbstractSubMenu
from ..menu.menu import MenuSelectionType
from ..models.disk_encryption import EncryptionType, DiskEncryption
from ..user_interaction.utils import get_password
from ..menu import Menu
from ..general import secret
from ..hsm.fido import get_fido2_devices

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
				func=lambda preset: select_disk_encryption(preset),
				display_func=
				dependencies=['encryption_password'],
				enabled=True
			)
		self._menu_options['HSM'] = \
			Selector(
				description=_('Use HSM to unlock encrypted drive'),
				func=lambda preset: select_hsm(preset),
				dependencies=['encryption_password'],
				default=None,
				enabled=True
			)

	def run(self):
		super().run()
		return DiskEncryption(
			encryption_type=self._data_store['encryption_type'],
			encryption_password=self._data_store['encryption_password'],
			partitions=self._data_store.get('partitions', None),
			hsm_device=self._data_store['hsm_device']
		)


def _encryption_type_mapper


def select_disk_encryption(preset: Optional[DiskEncryption]) -> Optional[DiskEncryption]:
	title = str(_('Select disk encryption option'))
	options = {
		str(_('Full disk encryption')): EncryptionType.FullDiskEncryption,
		str(_('Partition encryption')): EncryptionType.Partition
	}

	choice = Menu(title, options, raise_error_on_interrupt=True).run()

	match choice.type_:
		case MenuSelectionType.Ctrl_c: return None
		case MenuSelectionType.Esc: return preset
		case MenuSelectionType.Selection: return options[choice.value]


def select_encrypted_password() -> Optional[str]:
	if passwd := get_password(prompt=str(_('Enter disk encryption password (leave blank for no encryption): '))):
		return passwd
	return None


def select_hsm(preset: Optional[Path] = None) -> Optional[Path]:
	title = _('Select which partitions to mark for formatting:')
	title += '\n'

	fido_devices = get_fido2_devices()

	indexes = []
	for index, path in enumerate(fido_devices.keys()):
		title += f"{index}: {path} ({fido_devices[path]['manufacturer']} - {fido_devices[path]['product']})"
		indexes.append(f"{index}|{fido_devices[path]['product']}")

	title += '\n'

	choice = Menu(title, indexes).run()

	match choice.type_:
		case MenuSelectionType.Esc: return preset
		case MenuSelectionType.Selection:
			selection: Any = choice.value
			index = int(selection.split('|', 1)[0])
			return Path(list(fido_devices.keys())[index])

	return None
