from __future__ import annotations

import logging

from pathlib import Path
from typing import Any, Dict, TYPE_CHECKING

from ..general import SysCommand
from ..menu import Menu
from ..menu.menu import MenuSelectionType
from ..output import log
from ..configuration import ConfigurationOutput

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

	if choice.type_ == MenuSelectionType.Skip:
		return

	save_config_value = choice.single_value
	saving_key = [k for k, v in options.items() if v == save_config_value][0]

	dirs_to_exclude = [
		'/bin',
		'/dev',
		'/lib',
		'/lib64',
		'/lost+found',
		'/opt',
		'/proc',
		'/run',
		'/sbin',
		'/srv',
		'/sys',
		'/usr',
		'/var',
	]

	log('Ignore configuration option folders: ' + ','.join(dirs_to_exclude), level=logging.DEBUG)
	log(_('Finding possible directories to save configuration files ...'), level=logging.INFO)

	find_exclude = '-path ' + ' -prune -o -path '.join(dirs_to_exclude) + ' -prune '
	file_picker_command = f'find / {find_exclude} -o -type d -print0'

	directories = SysCommand(file_picker_command).decode()

	if directories is None:
		raise ValueError('Failed to retrieve possible configuration directories')

	possible_save_dirs = list(filter(None, directories.split('\x00')))

	selection = Menu(
		_('Select directory (or directories) for saving configuration files'),
		possible_save_dirs,
		multi=True,
		skip=True,
		allow_reset=False,
	).run()

	match selection.type_:
		case MenuSelectionType.Skip:
			return

	save_dirs = selection.multi_value

	log(f'Saving {saving_key} configuration files to {save_dirs}', level=logging.DEBUG)

	if save_dirs is not None:
		for save_dir_str in save_dirs:
			save_dir = Path(save_dir_str)
			if options['user_config'] == save_config_value:
				config_output.save_user_config(save_dir)
			elif options['user_creds'] == save_config_value:
				config_output.save_user_creds(save_dir)
			elif options['all'] == save_config_value:
				config_output.save_user_config(save_dir)
				config_output.save_user_creds(save_dir)
