import os
import logging
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
from archinstall.lib.models import NetworkConfiguration
import archinstall.examples.guided as guided

if archinstall.arguments.get('help', None):
	archinstall.log(" - Alternate disk layout    via -- disk_layouts = <json_file>")
	archinstall.log(" - Optional disk encryption via --!encryption-password=<password>")
	archinstall.log(" - Optional systemd network via --network")
	archinstall.log(" - Optional keyboard layout via --keyboard-layout=<code>")

nomen = getsourcefile(lambda: 0)
script_name = nomen[nomen.rfind(os.path.sep) + 1:nomen.rfind('.')]
#
# script specific code
#
def ask_user_questions():
	arguments = archinstall.arguments
	# storage = archinstall.storage
	# if we have a disk layouts files we use it (thus we create a minimal test environment fuor a given setup)
	if not arguments['disk_layouts']:
		arguments['harddrives'] = archinstall.select_harddrives(None)
		if len(arguments['harddrives']) == 1:
			arguments['disk_layouts'] = archinstall.suggest_single_disk_layout(arguments['harddrives'][0])
		else:
			arguments['disk_layouts'] = archinstall.suggest_multi_disk_layout(arguments['harddrives'])
	arguments['hostname'] = 'arch-minimal'
	arguments['!root-password'] = 'airoot'
	arguments['additional-packages'] = ['nano','wget','vim']
	arguments['!users'] = [archinstall.User('devel', 'devel', False)]
	arguments['profile'] = archinstall.Profile(None, 'minimal')
	if archinstall.has_uefi():
		arguments['bootloader'] = 'systemd-bootctl'
	else:
		arguments['bootloader'] = 'grub-install'
	# TODO network setup
	if arguments.get('network'):
		arguments['nic'] = [NetworkConfiguration(dhcp=True,
			dns=None,
			gateway=None,
			iface=None,
			ip=None,
			type="iso")]


if __name__ in ('__main__',script_name):
	if not archinstall.arguments.get('silent'):
		ask_user_questions()

	config_output = archinstall.ConfigurationOutput(archinstall.arguments)
	if not archinstall.arguments.get('silent'):
		config_output.show()
	config_output.save()

	if archinstall.arguments.get('dry_run'):
		exit(0)

	if not archinstall.arguments.get('silent'):
		input(str(_('Press Enter to continue.')))

	archinstall.configuration_sanity_check()
	guided.perform_installation(archinstall.storage.get('MOUNT_POINT', '/mnt'))
	# For support reasons, we'll log the disk layout post installation (crash or no crash)
	archinstall.log(f"Disk states after installing: {archinstall.disk_layouts()}", level=logging.DEBUG)
	# Once this is done, we output some useful information to the user
	# And the installation is complete.
	archinstall.log("There are two new accounts in your installation after reboot:")
	archinstall.log(" * root (password: airoot)")
	archinstall.log(" * devel (password: devel)")
