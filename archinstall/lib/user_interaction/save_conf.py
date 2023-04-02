from __future__ import annotations

import logging

from pathlib import Path
from typing import Any, Dict, TYPE_CHECKING

from ..configuration import ConfigurationOutput
from ..general import SysCommand
from ..menu import Menu
from ..menu.menu import MenuSelectionType
from ..output import log

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

	save_config_value: str = [k for k, v in options.items() if v == choice.single_value][0]

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

	log('When picking a directory to save configuration files to, by default we will ignore the following folders: ' + ','.join(dirs_to_exclude), level=logging.DEBUG)

	log(_('Finding possible directories to save configuration files ...'), level=logging.INFO)

	find_exclude = '-path ' + ' -prune -o -path '.join(dirs_to_exclude) + ' -prune '
	file_picker_command = f'find / {find_exclude} -o -type d -print0'
	decoded = SysCommand(file_picker_command).decode()

	if not decoded:
		raise ValueError(f'Error decoding command result: {file_picker_command}')

	possible_save_dirs = list(filter(None, decoded.split('\x00')))

	choice = Menu(
		_('Select directory (or directories) for saving configuration files'),
		possible_save_dirs,
		multi=True,
		skip=True,
		allow_reset=False,
	).run()

	if choice.type_ == MenuSelectionType.Skip:
		return

	save_dirs = choice.single_value

	prompt = _('Do you want to save {} configuration file(s) in the following locations?\n\n{}').format(
		save_config_value,
		', '.join(save_dirs)
	)

	save_confirmation = Menu(prompt, Menu.yes_no(), default_option=Menu.yes()).run()
	if save_confirmation == Menu.no():
		return

	log('Saving {} configuration files to {}'.format(save_config_value, save_dirs), level=logging.DEBUG)

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
