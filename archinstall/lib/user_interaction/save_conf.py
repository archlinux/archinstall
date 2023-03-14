from __future__ import annotations

from typing import Any, Dict, TYPE_CHECKING

from ..configuration import ConfigurationOutput
from ..menu import Menu
from ..menu.menu import MenuSelectionType
from ..utils.util import prompt_dir

if TYPE_CHECKING:
	_: Any


def save_config(config: Dict):

	def preview(selection: str):
		if options['user_config'] == selection:
			serialized = config_output.user_config_to_json()
			return f'{config_output.user_configuration_file}\n{serialized}'
		elif options['user_creds'] == selection:
			if maybe_serial := config_output.user_credentials_to_json():
				return f'{config_output.user_credentials_file}\n{maybe_serial}'
			else:
				return str(_('No configuration'))
		elif options['all'] == selection:
			output = f'{config_output.user_configuration_file}\n'
			if config_output.user_credentials_to_json():
				output += f'{config_output.user_credentials_file}\n'
			return output[:-1]
		return None

	config_output = ConfigurationOutput(config)

	options = {
		'user_config': str(_('Save user configuration')),
		'user_creds': str(_('Save user credentials')),
		'all': str(_('Save all'))
	}

	choice = Menu(
		_('Choose which configuration to save'),
		list(options.values()),
		sort=False,
		skip=True,
		preview_size=0.75,
		preview_command=preview
	).run()

	if choice.type_ == MenuSelectionType.Skip:
		return

	dest_path = prompt_dir(str(_('Enter a directory for the configuration(s) to be saved: ')))

	if options['user_config'] == choice.value:
		config_output.save_user_config(dest_path)
	elif options['user_creds'] == choice.value:
		config_output.save_user_creds(dest_path)
	elif options['all'] == choice.value:
		config_output.save_user_config(dest_path)
		config_output.save_user_creds(dest_path)
