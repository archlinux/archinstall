from pathlib import Path
from typing import TYPE_CHECKING, assert_never, override

from archinstall.lib.models.device_model import SubvolumeModification
from archinstall.tui.curses_menu import EditMenu
from archinstall.tui.result import ResultType
from archinstall.tui.types import Alignment

from ..menu.list_manager import ListManager
from ..utils.util import prompt_dir

if TYPE_CHECKING:
	from collections.abc import Callable

	from archinstall.lib.translationhandler import DeferredTranslation

	_: Callable[[str], DeferredTranslation]


class SubvolumeMenu(ListManager[SubvolumeModification]):
	def __init__(
		self,
		btrfs_subvols: list[SubvolumeModification],
		prompt: str | None = None,
	):
		self._actions = [
			str(_("Add subvolume")),
			str(_("Edit subvolume")),
			str(_("Delete subvolume")),
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
		result = EditMenu(
			str(_("Subvolume name")),
			alignment=Alignment.CENTER,
			allow_skip=True,
			default_text=str(preset.name) if preset else None,
		).input()

		match result.type_:
			case ResultType.Skip:
				return preset
			case ResultType.Selection:
				name = result.text()
			case ResultType.Reset:
				raise ValueError("Unhandled result type")
			case _:
				assert_never(result.type_)

		header = f"{_('Subvolume name')}: {name}\n"

		path = prompt_dir(
			str(_("Subvolume mountpoint")),
			header=header,
			allow_skip=True,
			validate=False,
		)

		if not path:
			return None

		return SubvolumeModification(Path(name), path)

	@override
	def handle_action(
		self,
		action: str,
		entry: SubvolumeModification | None,
		data: list[SubvolumeModification],
	) -> list[SubvolumeModification]:
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
