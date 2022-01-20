#!/bin/python
"""
Ancilliary functions to the menu
"""
import archinstall
from typing import Optional, Dict, Any, List

def menu_set_root_password(menu :archinstall.GlobalMenu) -> str:
	prompt = 'Enter root password (leave blank to disable root & create superuser): '
	password = archinstall.get_password(prompt=prompt)

	if password is not None:
		menu.option('!superusers').set_current_selection(None)
		archinstall.arguments['!users'] = {}
		archinstall.arguments['!superusers'] = {}

	return password

def menu_select_harddrives(menu :archinstall.GlobalMenu) -> Optional[str]:
	old_haddrives = archinstall.arguments.get('harddrives')
	harddrives = archinstall.select_harddrives()

	# in case the harddrives got changed we have to reset the disk layout as well
	if old_haddrives != harddrives:
		menu.option('disk_layouts').set_current_selection(None)
		archinstall.arguments['disk_layouts'] = {}

	if not harddrives:
		prompt = 'You decided to skip harddrive selection\n'
		prompt += f"and will use whatever drive-setup is mounted at {archinstall.storage['MOUNT_POINT']} (experimental)\n"
		prompt += "WARNING: Archinstall won't check the suitability of this setup\n"

		prompt += 'Do you wish to continue?'
		choice = archinstall.Menu(prompt, ['yes', 'no'], default_option='yes').run()

		if choice == 'no':
			return menu_select_harddrives(menu)

	return harddrives

def menu_select_profile(menu :archinstall.GlobalMenu) -> Optional[str] :
	profile = archinstall.select_profile()

	# Check the potentially selected profiles preparations to get early checks if some additional questions are needed.
	if profile and profile.has_prep_function():
		namespace = f'{profile.namespace}.py'
		with profile.load_instructions(namespace=namespace) as imported:
			if not imported._prep_function():
				archinstall.log(' * Profile\'s preparation requirements was not fulfilled.', fg='red')
				exit(1)

	return profile

def menu_create_superuser_account(menu :archinstall.GlobalMenu) -> str:
	superuser = archinstall.ask_for_superuser_account('Create a required super-user with sudo privileges: ', forced=True)
	return superuser

def menu_create_user_account(menu :archinstall.GlobalMenu) -> List[Dict[str, Dict[str, str]]]:
	users, superusers = archinstall.ask_for_additional_users('Enter a username to create an additional user: ')
	if not archinstall.arguments.get('!superusers', None):
		archinstall.arguments['!superusers'] = superusers
	else:
		archinstall.arguments['!superusers'] = {**archinstall.arguments['!superusers'], **superusers}

	return users

def menu_missing_configs(menu :archinstall.GlobalMenu) -> int:
	def check(s):
		return menu.option(s).has_selection()
	_, missing = menu.mandatory_overview()
	if not check('!root-password') and not check('!superusers'):
		missing += 1
	if check('harddrives'):
		if not menu.option('harddrives').is_empty() and not check('disk_layouts'):
			missing += 1

	return missing

def menu_install_text(menu :archinstall.GlobalMenu) -> str:
	missing = menu_missing_configs(menu)
	if missing > 0:
		return f'Install ({missing} config(s) missing)'
	return 'Install'

def menu_update_install(menu :archinstall.GlobalMenu):
	text = menu_install_text(menu)
	menu.option('install').update_description(text)

def menu_post_callback(menu :archinstall.GlobalMenu, option, value :Any = None):
	menu_update_install(menu)


""" Define an standard set of menu options"""

def define_base_option_set(menu :archinstall.GlobalMenu):
	menu.set_option('keyboard-layout', archinstall.Selector('Select keyboard layout', lambda: archinstall.select_language('en'), default='en'))
	menu.set_option('mirror-region',
			archinstall.Selector(
				'Select mirror region',
				lambda: archinstall.select_mirror_regions(),
				display_func=lambda x: list(x.keys()) if x else '[]',
				default={}))
	menu.set_option('sys-language',
			archinstall.Selector('Select locale language', lambda: archinstall.select_locale_lang('en_US'), default='en_US'))
	menu.set_option('sys-encoding',
			archinstall.Selector('Select locale encoding', lambda: archinstall.select_locale_enc('utf-8'), default='utf-8'))
	menu.set_option('harddrives',
			archinstall.Selector(
				'Select harddrives',
				lambda: menu_select_harddrives(menu)))
	menu.set_option('disk_layouts',
			archinstall.Selector(
				'Select disk layout',
				lambda: archinstall.select_disk_layout(
					archinstall.arguments['harddrives'],
					archinstall.arguments.get('advanced', False)
				),
				dependencies=['harddrives']))
	menu.set_option('!encryption-password',
			archinstall.Selector(
				'Set encryption password',
				lambda: archinstall.get_password(prompt='Enter disk encryption password (leave blank for no encryption): '),
				display_func=lambda x: archinstall.secret(x) if x else 'None',
				dependencies=['harddrives']))
	menu.set_option('swap',
			archinstall.Selector(
				'Use swap',
				lambda: archinstall.ask_for_swap(),
				default=True))
	menu.set_option('bootloader',
		archinstall.Selector(
			'Select bootloader',
			lambda: archinstall.ask_for_bootloader(archinstall.arguments.get('advanced', False))))
	menu.set_option('hostname',
			archinstall.Selector('Specify hostname', lambda: archinstall.ask_hostname()))
	menu.set_option('!root-password',
			archinstall.Selector(
				'Set root password',
				lambda: menu_set_root_password(menu),
				display_func=lambda x: archinstall.secret(x) if x else 'None'))
	menu.set_option('!superusers',
			archinstall.Selector(
				'Specify superuser account',
				lambda: menu_create_superuser_account(menu),
				dependencies_not=['!root-password'],
				display_func=lambda x: list(x.keys()) if x else ''))
	menu.set_option('!users',
			archinstall.Selector(
				'Specify user account',
				lambda: menu_create_user_account(menu),
				default={},
				display_func=lambda x: list(x.keys()) if x else '[]'))
	menu.set_option('profile',
			archinstall.Selector(
				'Specify profile',
				lambda: menu_select_profile(menu),
				display_func=lambda x: x if x else 'None'))
	menu.set_option('audio',
			archinstall.Selector(
				'Select audio',
				lambda: archinstall.ask_for_audio_selection(
					archinstall.is_desktop_profile(archinstall.arguments.get('profile', None)))))
	menu.set_option('kernels',
			archinstall.Selector(
				'Select kernels',
				lambda: archinstall.select_kernel(),
				default=['linux']))
	menu.set_option('packages',
			archinstall.Selector(
				'Additional packages to install',
				lambda: archinstall.ask_additional_packages_to_install(archinstall.arguments.get('packages', None)),
				default=[]))
	menu.set_option('nic',
			archinstall.Selector(
				'Configure network',
				lambda: archinstall.ask_to_configure_network(),
				display_func=lambda x: x if x else 'Not configured, unavailable unless setup manually',
				default={}))
	menu.set_option('timezone',
			archinstall.Selector('Select timezone', lambda: archinstall.ask_for_a_timezone()))
	menu.set_option('ntp',
			archinstall.Selector(
				'Set automatic time sync (NTP)',
				lambda: archinstall.ask_ntp(),
				default=True))

def define_base_action_set(menu :archinstall.GlobalMenu):
	menu.set_option('', archinstall.Selector('', enabled=True))
	menu.set_option('install',
			archinstall.Selector(
				menu_install_text(menu),
				exec_func=lambda x: True if menu_missing_configs(menu) == 0 else False,
				enabled=True))
	menu.set_option('abort', archinstall.Selector('Abort', exec_func=lambda x: exit(1), enabled=True))
