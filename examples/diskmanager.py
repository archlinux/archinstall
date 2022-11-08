import os
from inspect import getsourcefile

if __name__ == '__main__':
	# to be able to execute simply as python examples/guided.py or (from inside examples python guided.py)
	# will work only with the copy at examples
	# this solution was taken from https://stackoverflow.com/questions/714063/importing-modules-from-parent-folder/33532002#33532002
	import sys
	current_path = os.path.abspath(getsourcefile(lambda: 0))
	current_dir = os.path.dirname(current_path)
	parent_dir = current_dir[:current_dir.rfind(os.path.sep)]
	sys.path.append(parent_dir)

import archinstall
from archinstall import ConfigurationOutput
from archinstall.lib.user_interaction.diskmanager.glue import diskmanager
from archinstall.examples.guided import perform_filesystem_operations, perform_installation

def ask_user_questions():
	"""
		First, we'll ask the user for a bunch of user input.
		Not until we're satisfied with what we want to install
		will we continue with the actual installation steps.
	"""
	diskmanager(archinstall.arguments,archinstall.storage)
	# ref: https://github.com/archlinux/archinstall/pull/831
	# we'll set NTP to true by default since this is also
	# the default value specified in the menu options; in
	# case it will be changed by the user we'll also update
	# the system immediately
	global_menu = archinstall.GlobalMenu(data_store=archinstall.arguments)
	if archinstall.arguments.get('preset_mount',False):
		global_menu._disk_check = False

	global_menu.enable('archinstall-language')

	global_menu.enable('keyboard-layout')

	# Set which region to download packages from during the installation
	global_menu.enable('mirror-region')

	global_menu.enable('sys-language')
	global_menu.enable('sys-encoding')

	# Ask which harddrives/block-devices we will install to
	# and convert them into archinstall.BlockDevice() objects.
	if global_menu._disk_check:
		if archinstall.arguments.get('disk_layouts'):
			for item in ['harddrives','disk_layouts']:
				global_menu.option(item).func = None
		global_menu.enable('harddrives')
		global_menu.enable('disk_layouts')
		# Get disk encryption password (or skip if blank)
		global_menu.enable('!encryption-password')
		if archinstall.arguments.get('advanced', False) or archinstall.arguments.get('HSM', None):
			# Enables the use of HSM
			global_menu.enable('HSM')

	# Ask which boot-loader to use (will only ask if we're in UEFI mode, otherwise will default to GRUB)
	global_menu.enable('bootloader')

	global_menu.enable('swap')

	# Get the hostname for the machine
	global_menu.enable('hostname')

	# Ask for a root password (optional, but triggers requirement for super-user if skipped)
	global_menu.enable('!root-password')

	global_menu.enable('!users')

	# Ask for archinstall-specific profiles (such as desktop environments etc)
	global_menu.enable('profile')

	# Ask about audio server selection if one is not already set
	global_menu.enable('audio')

	# Ask for preferred kernel:
	global_menu.enable('kernels')

	global_menu.enable('packages')

	# Ask or Call the helper function that asks the user to optionally configure a network.
	global_menu.enable('nic')

	global_menu.enable('timezone')

	global_menu.enable('ntp')

	global_menu.enable('additional-repositories')

	global_menu.enable('__separator__')

	global_menu.enable('save_config')
	global_menu.enable('install')
	global_menu.enable('abort')

	global_menu.run()


if __name__ in ('__main__', 'diskmanager'):
	if not archinstall.arguments.get('silent'):
		ask_user_questions()

	config_output = ConfigurationOutput(archinstall.arguments)
	if not archinstall.arguments.get('silent'):
		config_output.show()
	config_output.save()

	if archinstall.arguments.get('dry_run'):
		exit(0)

	if not archinstall.arguments.get('silent'):
		input(str(_('Press Enter to continue.')))

	archinstall.configuration_sanity_check()
	perform_filesystem_operations()
	perform_installation(archinstall.storage.get('MOUNT_POINT', '/mnt'))
