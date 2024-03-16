from pathlib import Path
from typing import List, Optional, Any, TYPE_CHECKING

from .device_model import SubvolumeModification
from ..menu import TextInput, ListManager

if TYPE_CHECKING:
	_: Any


class SubvolumeMenu(ListManager):
	def __init__(self, prompt: str, btrfs_subvols: List[SubvolumeModification]):
		self._actions = [
			str(_('Add subvolume')),
			str(_('Edit subvolume')),
			str(_('Delete subvolume'))
		]
		super().__init__(prompt, btrfs_subvols, [self._actions[0]], self._actions[1:])

	def selected_action_display(self, subvolume: SubvolumeModification) -> str:
		return str(subvolume.name)

	def _add_subvolume(self, editing: Optional[SubvolumeModification] = None) -> Optional[SubvolumeModification]:
		name = TextInput(f'\n\n{_("Subvolume name")}: ', editing.name if editing else '').run()

		if not name:
			return None

		mountpoint = TextInput(f'{_("Subvolume mountpoint")}: ', str(editing.mountpoint) if editing else '').run()

		if not mountpoint:
			return None

		return SubvolumeModification(Path(name), Path(mountpoint))

	def handle_action(
		self,
		action: str,
		entry: Optional[SubvolumeModification],
		data: List[SubvolumeModification]
	) -> List[SubvolumeModification]:
		if action == self._actions[0]:  # add
			new_subvolume = self._add_subvolume()

			if new_subvolume is not None:
				# in case a user with the same username as an existing user
				# was created we'll replace the existing one
				data = [d for d in data if d.name != new_subvolume.name]
				data += [new_subvolume]
		elif entry is not None:
			if action == self._actions[1]:  # edit subvolume
				new_subvolume = self._add_subvolume(entry)

				if new_subvolume is not None:
					# we'll remove the original subvolume and add the modified version
					data = [d for d in data if d.name != entry.name and d.name != new_subvolume.name]
					data += [new_subvolume]
			elif action == self._actions[2]:  # delete
				data = [d for d in data if d != entry]

		return data
