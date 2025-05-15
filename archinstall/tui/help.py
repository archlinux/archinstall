from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from archinstall.lib.translationhandler import DeferredTranslation

if TYPE_CHECKING:
	_: Callable[[str], DeferredTranslation]


class HelpTextGroupId(Enum):
	GENERAL = "General"
	NAVIGATION = "Navigation"
	SELECTION = "Selection"
	SEARCH = "Search"


@dataclass
class HelpText:
	description: str
	keys: list[str] = field(default_factory=list)


@dataclass
class HelpGroup:
	group_id: HelpTextGroupId
	group_entries: list[HelpText]

	def get_desc_width(self) -> int:
		return max([len(e.description) for e in self.group_entries])

	def get_key_width(self) -> int:
		return max([len(", ".join(e.keys)) for e in self.group_entries])


class Help:
	# the groups needs to be classmethods not static methods
	# because they rely on the DeferredTranslation setup first;
	# if they are static methods, they will be called before the
	# translation setup is done

	@staticmethod
	def general() -> HelpGroup:
		return HelpGroup(
			group_id=HelpTextGroupId.GENERAL,
			group_entries=[
				HelpText(str(_("Show help")), ["Ctrl+h"]),
				HelpText(str(_("Exit help")), ["Esc"]),
			],
		)

	@staticmethod
	def navigation() -> HelpGroup:
		return HelpGroup(
			group_id=HelpTextGroupId.NAVIGATION,
			group_entries=[
				HelpText(str(_("Preview scroll up")), ["PgUp"]),
				HelpText(str(_("Preview scroll down")), ["PgDown"]),
				HelpText(str(_("Move up")), ["k", "↑"]),
				HelpText(str(_("Move down")), ["j", "↓"]),
				HelpText(str(_("Move right")), ["l", "→"]),
				HelpText(str(_("Move left")), ["h", "←"]),
				HelpText(str(_("Jump to entry")), ["1..9"]),
			],
		)

	@staticmethod
	def selection() -> HelpGroup:
		return HelpGroup(
			group_id=HelpTextGroupId.SELECTION,
			group_entries=[
				HelpText(str(_("Skip selection (if available)")), ["Esc"]),
				HelpText(str(_("Reset selection (if available)")), ["Ctrl+c"]),
				HelpText(str(_("Select on single select")), ["Enter"]),
				HelpText(str(_("Select on multi select")), ["Space", "Tab"]),
				HelpText(str(_("Reset")), ["Ctrl-C"]),
				HelpText(str(_("Skip selection menu")), ["Esc"]),
			],
		)

	@staticmethod
	def search() -> HelpGroup:
		return HelpGroup(
			group_id=HelpTextGroupId.SEARCH,
			group_entries=[
				HelpText(str(_("Start search mode")), ["/"]),
				HelpText(str(_("Exit search mode")), ["Esc"]),
			],
		)

	@staticmethod
	def get_help_text() -> str:
		help_output = ""
		help_texts = [
			Help.general(),
			Help.navigation(),
			Help.selection(),
			Help.search(),
		]
		max_desc_width = max([help.get_desc_width() for help in help_texts]) + 2
		max_key_width = max([help.get_key_width() for help in help_texts])

		for help_group in help_texts:
			help_output += f"{help_group.group_id.value}\n"
			divider_len = max_desc_width + max_key_width
			help_output += "-" * divider_len + "\n"

			for entry in help_group.group_entries:
				help_output += entry.description.ljust(max_desc_width, " ") + ", ".join(entry.keys) + "\n"

			help_output += "\n"

		return help_output
