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

	if choice.type_ == MenuSelectionType.Skip:
		return

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
	log(
		_('When picking a directory to save configuration files to,'
		' by default we will ignore the following folders: ') + ','.join(dirs_to_exclude),
		level=logging.DEBUG
	)

	log(_('Finding possible directories to save configuration files ...'), level=logging.INFO)
	
	find_exclude = '-path ' + ' -prune -o -path '.join(dirs_to_exclude) + ' -prune '
	file_picker_command = f'find / {find_exclude} -o -type d -print0'
	possible_save_dirs = list(
		filter(None, SysCommand(file_picker_command).decode().split('\x00'))
	)

	selection = Menu(
		_('Select directory (or directories) for saving configuration files'),
		possible_save_dirs,
		multi=True,
		skip=True,
	).run()

	match selection.type_:
		case MenuSelectionType.Reset:
			save_dirs = []
		case _:
			save_dirs = selection.value

	prompt = _('Do you want to save {} configuration file(s) in the following locations?\n\n{}').format(
		list(options.keys())[list(options.values()).index(choice.value)],
		save_dirs
	)
	save_confirmation = Menu(prompt, Menu.yes_no(), default_option=Menu.yes()).run()
	if save_confirmation == Menu.no():
		return
	
	log(
		_('Saving {} configuration files to {}').format(
			list(options.keys())[list(options.values()).index(choice.value)],
			save_dirs
		),
		level=logging.DEBUG
	)
	
	if save_dirs is not None:
		for save_dir_str in save_dirs:
			save_dir = Path(save_dir_str)
			if options['user_config'] == choice.value:
				config_output.save_user_config(save_dir)
			elif options['user_creds'] == choice.value:
				config_output.save_user_creds(save_dir)
			elif options['disk_layout'] == choice.value:
				config_output.save_disk_layout(save_dir)
			elif options['all'] == choice.value:
				config_output.save_user_config(save_dir)
				config_output.save_user_creds(save_dir)
				config_output.save_disk_layout(save_dir)
