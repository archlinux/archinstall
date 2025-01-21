from dataclasses import dataclass, field
from enum import Enum


class HelpTextGroupId(Enum):
	GENERAL = 'General'
	NAVIGATION = 'Navigation'
	SELECTION = 'Selection'
	SEARCH = 'Search'


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
			HelpText('Preview scroll up', ['PgUp']),
			HelpText('Preview scroll down', ['PgDown']),
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
			HelpText('Skip selection (if available)', ['Esc']),
			HelpText('Reset selection (if available)', ['Ctrl+c']),
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

		for help_group in help_texts:
			help_output += f'{help_group.group_id.value}\n'
			divider_len = max_desc_width + max_key_width
			help_output += '-' * divider_len + '\n'

			for entry in help_group.group_entries:
				help_output += (
					entry.description.ljust(max_desc_width, ' ')
					+ ', '.join(entry.keys) + '\n'
				)

			help_output += '\n'

		return help_output
