from dataclasses import dataclass, field
from enum import Enum
from typing import List


class HelpTextGroupId(Enum):
	GENERAL = 'General'
	NAVIGATION = 'Navigation'
	SELECTION = 'Selection'
	SEARCH = 'Search'


@dataclass
class HelpText:
	description: str
	keys: List[str] = field(default_factory=list)


@dataclass
class HelpGroup:
	group_id: HelpTextGroupId
	group_entries: List[HelpText]

	def get_desc_width(self) -> int:
		return max([len(e.description) for e in self.group_entries])

	def get_key_width(self) -> int:
		return max([len(', '.join(e.keys)) for e in self.group_entries])


class Help:
	general = HelpGroup(
		group_id=HelpTextGroupId.GENERAL,
		group_entries=[
			HelpText('Show help', ['Ctrl+h']),
			HelpText('Exit help', ['Esc']),
		]
	)

	navigation = HelpGroup(
		group_id=HelpTextGroupId.NAVIGATION,
		group_entries=[
			HelpText('Scroll up', ['Ctrl+↑']),
			HelpText('Scroll down', ['Ctrl+↓']),
			HelpText('Move up', ['k', '↑']),
			HelpText('Move down', ['j', '↓']),
			HelpText('Move right', ['l', '→']),
			HelpText('Move left', ['h', '←']),
			HelpText('Jump to entry', ['1..9'])
		]
	)

	selection = HelpGroup(
		group_id=HelpTextGroupId.SELECTION,
		group_entries=[
			HelpText('Select on single select', ['Enter']),
			HelpText('Select on select', ['Space', 'Tab']),
			HelpText('Reset', ['Ctrl-C']),
			HelpText('Skip selection menu', ['Esc']),
		]
	)

	search = HelpGroup(
		group_id=HelpTextGroupId.SEARCH,
		group_entries=[
			HelpText('Start search mode', ['/']),
			HelpText('Exit search mode', ['Esc']),
		]
	)

	@staticmethod
	def get_help_text() -> str:
		help_output = ''
		help_texts = [Help.general, Help.navigation, Help.selection, Help.search]
		max_desc_width = max([help.get_desc_width() for help in help_texts])
		max_key_width = max([help.get_key_width() for help in help_texts])

		margin = ' ' * 3

		for help in help_texts:
			help_output += f'{margin}{help.group_id.value}\n'
			divider_len = max_desc_width + max_key_width + len(margin * 2)
			help_output += margin + '-' * divider_len + '\n'

			for entry in help.group_entries:
				help_output += (
					margin +
					entry.description.ljust(max_desc_width, ' ') +
					margin +
					', '.join(entry.keys) + '\n'
				)

			help_output += '\n'

		return help_output
