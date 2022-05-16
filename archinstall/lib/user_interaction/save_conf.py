from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, TYPE_CHECKING

from ..configuration import ConfigurationOutput
from ..menu import Menu
from ..menu.menu import MenuSelectionType
from ..output import log

if TYPE_CHECKING:
	_: Any


def save_config(config: Dict):

	def preview(selection: str):
		if options['user_config'] == selection:
			json_config = config_output.user_config_to_json()
			return f'{config_output.user_configuration_file}\n{json_config}'
		elif options['user_creds'] == selection:
			if json_config := config_output.user_credentials_to_json():
				return f'{config_output.user_credentials_file}\n{json_config}'
			else:
				return str(_('No configuration'))
		elif options['disk_layout'] == selection:
			if json_config := config_output.disk_layout_to_json():
				return f'{config_output.disk_layout_file}\n{json_config}'
			else:
				return str(_('No configuration'))
		elif options['all'] == selection:
			output = f'{config_output.user_configuration_file}\n'
			if json_config := config_output.user_credentials_to_json():
				output += f'{config_output.user_credentials_file}\n'
			if json_config := config_output.disk_layout_to_json():
				output += f'{config_output.disk_layout_file}\n'
			return output[:-1]
		return None

	config_output = ConfigurationOutput(config)

	options = {
		'user_config': str(_('Save user configuration')),
		'user_creds': str(_('Save user credentials')),
		'disk_layout': str(_('Save disk layout')),
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

	if choice.type_ == MenuSelectionType.Esc:
		return

	while True:
		path = input(_('Enter a directory for the configuration(s) to be saved: ')).strip(' ')
		dest_path = Path(path)
		if dest_path.exists() and dest_path.is_dir():
			break
		log(_('Not a valid directory: {}').format(dest_path), fg='red')

	if options['user_config'] == choice.value:
		config_output.save_user_config(dest_path)
	elif options['user_creds'] == choice.value:
		config_output.save_user_creds(dest_path)
	elif options['disk_layout'] == choice.value:
		config_output.save_disk_layout(dest_path)
	elif options['all'] == choice.value:
		config_output.save_user_config(dest_path)
		config_output.save_user_creds(dest_path)
		config_output.save_disk_layout(dest_path)
