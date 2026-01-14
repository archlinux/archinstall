from pathlib import Path
from typing import assert_never, override

from archinstall.lib.menu.helpers import Input
from archinstall.lib.models.device import SubvolumeModification
from archinstall.lib.translationhandler import tr
from archinstall.tui.ui.result import ResultType

from ..menu.list_manager import ListManager
from ..utils.util import prompt_dir


class SubvolumeMenu(ListManager[SubvolumeModification]):
	def __init__(
		self,
		btrfs_subvols: list[SubvolumeModification],
		prompt: str | None = None,
	):
		self._actions = [
			tr('Add subvolume'),
			tr('Edit subvolume'),
			tr('Delete subvolume'),
		]

		super().__init__(
			btrfs_subvols,
			[self._actions[0]],
			self._actions[1:],
			prompt,
		)

	@override
	def selected_action_display(self, selection: SubvolumeModification) -> str:
		return str(selection.name)

	def _add_subvolume(self, preset: SubvolumeModification | None = None) -> SubvolumeModification | None:
		def validate(value: str | None) -> str | None:
			if value:
				return None
			return tr('Value cannot be empty')

		result = Input(
			header=tr('Enter subvolume name'),
			allow_skip=True,
			default_value=str(preset.name) if preset else None,
			validator_callback=validate,
		).show()

		match result.type_:
			case ResultType.Skip:
				return preset
			case ResultType.Selection:
				name = result.get_value()
			case ResultType.Reset:
				raise ValueError('Unhandled result type')
			case _:
				assert_never(result.type_)

		header = f'{tr("Subvolume name")}: {name}\n\n'
		header += tr('Enter subvolume mountpoint')

		path = prompt_dir(
			header=header,
			allow_skip=True,
			validate=True,
			must_exist=False,
		)

		if not path:
			return preset

		return SubvolumeModification(Path(name), path)

	@override
	def handle_action(
		self,
		action: str,
		entry: SubvolumeModification | None,
		data: list[SubvolumeModification],
	) -> list[SubvolumeModification]:
		if action == self._actions[0]:
			new_subvolume = self._add_subvolume()

			if new_subvolume is not None:
				# in case a user with the same username as an existing user
				# was created we'll replace the existing one
				data = [d for d in data if d.name != new_subvolume.name]
				data += [new_subvolume]
		elif entry is not None:
			if action == self._actions[1]:
				new_subvolume = self._add_subvolume(entry)

				if new_subvolume is not None:
					# we'll remove the original subvolume and add the modified version
					data = [d for d in data if d.name != entry.name and d.name != new_subvolume.name]
					data += [new_subvolume]
			elif action == self._actions[2]:
				data = [d for d in data if d != entry]

		return data
