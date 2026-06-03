from typing import override

from archinstall.lib.menu.abstract_menu import AbstractSubMenu
from archinstall.lib.menu.helpers import Confirmation, Input
from archinstall.lib.models.pacman import PacmanConfiguration
from archinstall.lib.pathnames import PACMAN_CONF
from archinstall.lib.translationhandler import tr
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.result import ResultType


class PacmanMenu(AbstractSubMenu[PacmanConfiguration]):
	def __init__(
		self,
		pacman_conf: PacmanConfiguration,
		advanced: bool = False,
	):
		self._pacman_conf = pacman_conf
		self._advanced = advanced
		menu_options = self._define_menu_options()

		self._item_group = MenuItemGroup(menu_options, sort_items=False, checkmarks=True)
		super().__init__(
			self._item_group,
			config=self._pacman_conf,
			allow_reset=True,
		)

	def _define_menu_options(self) -> list[MenuItem]:
		return [
			MenuItem(
				text=tr('Parallel Downloads'),
				action=select_parallel_downloads,
				value=self._pacman_conf.parallel_downloads,
				preview_action=lambda item: str(item.get_value()),
				key='parallel_downloads',
				enabled=self._advanced,
			),
			MenuItem(
				text=tr('Color'),
				action=select_color,
				value=self._pacman_conf.color,
				preview_action=lambda item: str(item.get_value()),
				key='color',
			),
		]

	@override
	async def show(self) -> PacmanConfiguration | None:
		config = await super().show()

		if config is None:
			return PacmanConfiguration.default()

		_apply_to_live(config.parallel_downloads)

		return config


def _apply_to_live(parallel_downloads: int) -> None:
	"""Apply ParallelDownloads to live system pacman.conf for faster installation."""
	with PACMAN_CONF.open() as f:
		pacman_conf = f.read().split('\n')

	with PACMAN_CONF.open('w') as fwrite:
		for line in pacman_conf:
			if 'ParallelDownloads' in line:
				fwrite.write(f'ParallelDownloads = {parallel_downloads}\n')
			else:
				fwrite.write(f'{line}\n')


async def select_parallel_downloads(preset: int = 5) -> int | None:
	max_recommended = 10

	header = tr('Enter the number of parallel downloads (1-{})').format(max_recommended)

	def validator(s: str) -> str | None:
		try:
			value = int(s)
			if 1 <= value <= max_recommended:
				return None
			return tr('Value must be between 1 and {}').format(max_recommended)
		except Exception:
			return tr('Please enter a valid number')

	result = await Input(
		header=header,
		allow_skip=True,
		allow_reset=True,
		validator_callback=validator,
		default_value=str(preset),
	).show()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return 5
		case ResultType.Selection:
			return int(result.get_value())


async def select_color(preset: bool = True) -> bool | None:
	result = await Confirmation(
		header=tr('Enable colored output for pacman'),
		preset=preset,
		allow_skip=True,
	).show()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return True
		case ResultType.Selection:
			return result.get_value()
