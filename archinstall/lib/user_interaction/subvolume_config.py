from typing import Dict, List, Optional, Any, TYPE_CHECKING

from ..menu.list_manager import ListManager
from ..menu.menu import MenuSelectionType
from ..menu.text_input import TextInput
from ..menu import Menu
from ..models.subvolume import Subvolume

if TYPE_CHECKING:
	_: Any


class SubvolumeList(ListManager):
	def __init__(self, prompt: str, current_volumes: List[Subvolume]):
		self._actions = [
			str(_('Add subvolume')),
			str(_('Edit subvolume')),
			str(_('Delete subvolume'))
		]
		super().__init__(prompt, current_volumes, self._actions, self._actions[0])

	def reformat(self, data: List[Subvolume]) -> Dict[str, Subvolume]:
		return {e.display(): e for e in data}

	def action_list(self):
		active_user = self.target if self.target else None

		if active_user is None:
			return [self._actions[0]]
		else:
			return self._actions[1:]

	def _prompt_options(self, editing: Optional[Subvolume] = None) -> List[str]:
		preset_options = []
		if editing:
			preset_options = editing.options

		choice = Menu(
			str(_("Select the desired subvolume options ")),
			['nodatacow','compress'],
			skip=True,
			preset_values=preset_options,
			multi=True
		).run()

		if choice.type_ == MenuSelectionType.Selection:
			return choice.value  # type: ignore

		return []

	def _add_subvolume(self, editing: Optional[Subvolume] = None) -> Optional[Subvolume]:
		name = TextInput(f'\n\n{_("Subvolume name")}: ', editing.name if editing else '').run()

		if not name:
			return None

		mountpoint = TextInput(f'\n{_("Subvolume mountpoint")}: ', editing.mountpoint if editing else '').run()

		if not mountpoint:
			return None

		options = self._prompt_options(editing)

		subvolume = Subvolume(name, mountpoint)
		subvolume.compress = 'compress' in options
		subvolume.nodatacow = 'nodatacow' in options

		return subvolume

	def exec_action(self, data: List[Subvolume]) -> List[Subvolume]:
		if self.target:
			active_subvolume = self.target
		else:
			active_subvolume = None

		if self.action == self._actions[0]:  # add
			new_subvolume = self._add_subvolume()

			if new_subvolume is not None:
				# in case a user with the same username as an existing user
				# was created we'll replace the existing one
				data = [d for d in data if d.name != new_subvolume.name]
				data += [new_subvolume]
		elif self.action == self._actions[1]:  # edit subvolume
			new_subvolume = self._add_subvolume(active_subvolume)

			if new_subvolume is not None:
				# we'll remove the original subvolume and add the modified version
				data = [d for d in data if d.name != active_subvolume.name and d.name != new_subvolume.name]
				data += [new_subvolume]
		elif self.action == self._actions[2]:  # delete
			data = [d for d in data if d != active_subvolume]

		return data
