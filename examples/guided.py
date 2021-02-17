import getpass, time, json, sys, signal, os
import archinstall

"""
This signal-handler chain (and global variable)
is used to trigger the "Are you sure you want to abort?" question further down.
It might look a bit odd, but have a look at the line: "if SIG_TRIGGER:"
"""
SIG_TRIGGER = False
def kill_handler(sig, frame):
	print()
	exit(0)

def sig_handler(sig, frame):
	global SIG_TRIGGER
	SIG_TRIGGER = True
	signal.signal(signal.SIGINT, kill_handler)

original_sigint_handler = signal.getsignal(signal.SIGINT)
signal.signal(signal.SIGINT, sig_handler)


def perform_installation(device, boot_partition, language, mirrors):
	"""
	Performs the installation steps on a block device.
	Only requirement is that the block devices are
	formatted and setup prior to entering this function.
	"""
	with archinstall.Installer(device, boot_partition=boot_partition, hostname=archinstall.arguments.get('hostname', 'Archinstall')) as installation:
		## if len(mirrors):
		# Certain services might be running that affects the system during installation.
		# Currently, only one such service is "reflector.service" which updates /etc/pacman.d/mirrorlist
		# We need to wait for it before we continue since we opted in to use a custom mirror/region.
		installation.log(f'Waiting for automatic mirror selection has completed before using custom mirrors.')
		while 'dead' not in (status := archinstall.service_state('reflector')):
			time.sleep(1)

		archinstall.use_mirrors(mirrors) # Set the mirrors for the live medium
		if installation.minimal_installation():
			installation.set_mirrors(mirrors) # Set the mirrors in the installation medium
			installation.set_keyboard_language(language)
			installation.add_bootloader()

			# If user selected to copy the current ISO network configuration
			# Perform a copy of the config
			if archinstall.storage['_guided']['network'] == 'Copy ISO network configuration to installation':
				installation.copy_ISO_network_config(enable_services=True) # Sources the ISO network configuration to the install medium.

			# Otherwise, if a interface was selected, configure that interface
			elif archinstall.storage['_guided']['network']:
				installation.configure_nic(**archinstall.storage['_guided']['network'])
				installation.enable_service('systemd-networkd')
				installation.enable_service('systemd-resolved')


			if archinstall.storage['_guided']['packages'] and archinstall.storage['_guided']['packages'][0] != '':
				installation.add_additional_packages(archinstall.storage['_guided']['packages'])

			if 'profile' in archinstall.storage['_guided'] and len(profile := archinstall.storage['_guided']['profile']['path'].strip()):
				installation.install_profile(profile)

			if archinstall.storage['_guided']['users']:
				for user in archinstall.storage['_guided']['users']:
					password = users[user]

					sudo = False
					if 'root_pw' not in archinstall.storage['_guided_hidden'] or len(archinstall.storage['_guided_hidden']['root_pw'].strip()) == 0:
						sudo = True

					installation.user_create(user, password, sudo=sudo)

			if 'root_pw' in archinstall.storage['_guided_hidden'] and archinstall.storage['_guided_hidden']['root_pw']:
				installation.user_set_pw('root', archinstall.storage['_guided_hidden']['root_pw'])

"""
  First, we'll ask the user for a bunch of user input.
  Not until we're satisfied with what we want to install
  will we continue with the actual installation steps.
"""
if not archinstall.arguments.get('keyboard-language', None):
	archinstall.arguments['keyboard-language'] = archinstall.select_language(archinstall.list_keyboard_languages()).strip()

# Before continuing, set the preferred keyboard layout/language in the current terminal.
# This will just help the user with the next following questions.
if len(archinstall.arguments['keyboard-language']):
	archinstall.set_keyboard_language(archinstall.arguments['keyboard-language'])

# Set which region to download packages from during the installation
if not archinstall.arguments.get('mirror-region', None):
	archinstall.arguments['mirror-region'] = archinstall.select_mirror_regions(archinstall.list_mirrors())

# Ask which harddrive/block-device we will install to
if archinstall.arguments.get('harddrive', None):
	archinstall.arguments['harddrive'] = archinstall.BlockDevice(archinstall.arguments['harddrive'])
else:
	archinstall.arguments['harddrive'] = archinstall.select_disk(archinstall.all_disks())

# Perform a quick sanity check on the selected harddrive.
# 1. Check if it has partitions
# 3. Check that we support the current partitions
# 2. If so, ask if we should keep them or wipe everything
if archinstall.arguments['harddrive'].has_partitions():
	archinstall.log(f" ! {archinstall.arguments['harddrive']} contains existing partitions", fg='red')
	partition_mountpoints = {}
	for partition in archinstall.arguments['harddrive']:
		try:
			if partition.filesystem_supported():
				archinstall.log(f" {partition}")
				partition_mountpoints[partition] = None
		except archinstall.UnknownFilesystemFormat as err:
			archinstall.log(f" {partition} (Filesystem not supported)", fg='red')
			#archinstall.log(f"Current filesystem is not supported: {err}", fg='red')
		#input(f"Do you wish to erase all data? (y/n):")

	if (option := input('Do you wish to keep one/more existing partitions or format entire drive? (k/f): ')).lower() in ('k', 'keep'):
		archinstall.arguments['harddrive'].keep_partitions = True

		archinstall.log(f" ** You will now select where (inside the installation) to mount partitions. **")
		archinstall.log(f" ** The root would be a simple / and the boot partition /boot as it's relative paths. **")
		while True:
			partition = archinstall.generic_select(partition_mountpoints.keys(), "Select a partition to assign mount-point to (leave blank when done): ")
			if not partition:
				break

			mountpoint = input(f"Enter a mount-point for {partition}: ").strip(' ')

			while 1:
				new_filesystem = input(f"Enter a valid filesystem for {partition} (leave blank for {partition.filesystem}): ").strip(' ')
				if len(new_filesystem) <= 0:
					break

				try:
					partition.format(new_filesystem, path='/dev/null', log_formating=False, allow_formatting=True)
				except archinstall.UnknownFilesystemFormat:
					archinstall.log(f"Selected filesystem is not supported yet, if you wish archinstall should support '{new_filesystem}' please create a issue-ticket suggesting it on github at https://github.com/Torxed/archinstall/issues.")
					archinstall.log(f"Until then, please enter another supported filesystem.")
					continue
				except archinstall.SysCallError:
					pass # Supported, but mkfs could not format /dev/null which is the whole point of /dev/null in path :)
				break

			if len(mountpoint):
				partition.allow_formatting = True
				partition.target_mountpoint = mountpoint
				if len(new_filesystem):
					partition.filesystem = new_filesystem

		archinstall.log('Using existing partition table reported above.')
	else:
		archinstall.arguments['harddrive'].keep_partitions = False

# Get disk encryption password (or skip if blank)
if not archinstall.arguments.get('encryption-password', None):
	archinstall.arguments['encryption-password'] = archinstall.get_password(prompt='Enter disk encryption password (leave blank for no encryption): ')
archinstall.arguments['harddrive'].encryption_password = archinstall.arguments['encryption-password']

# Get the hostname for the machine
if not archinstall.arguments.get('hostname', None):
	archinstall.arguments['hostname'] = input('Desired hostname for the installation: ').strip(' ')

# Ask for a root password (optional, but triggers requirement for super-user if skipped)
if not archinstall.arguments.get('!root-password', None):
	archinstall.arguments['!root-password'] = archinstall.get_password(prompt='Enter root password (Recommended: leave blank to leave root disabled): ')

#	# Storing things in _guided_hidden helps us avoid printing it
#	# when echoing user configuration: archinstall.storage['_guided']
#	archinstall.storage['_guided_hidden']['root_pw'] = root_pw
#	archinstall.storage['_guided']['root_unlocked'] = True
#	break

# Ask for additional users (super-user if root pw was not set)
archinstall.arguments['users'] = {}
archinstall.arguments['superusers'] = {}
if not archinstall.arguments.get('!root-password', None):
	archinstall.arguments['superusers'] = archinstall.ask_for_superuser_account('Create a required super-user with sudo privileges: ', forced=True)

users, superusers = archinstall.ask_for_additional_users('Any additional users to install (leave blank for no users): ')
archinstall.arguments['users'] = users
archinstall.arguments['superusers'] = {**archinstall.arguments['superusers'], **superusers}

# Ask for archinstall-specific profiles (such as desktop environments etc)
if not archinstall.arguments.get('profile', None):
	while 1:
		profile = archinstall.select_profile(archinstall.list_profiles())
		print(profile)
		if profile:
			archinstall.storage['_guided']['profile'] = profile

			if type(profile) != str:  # Got a imported profile
				archinstall.storage['_guided']['profile'] = profile[0]  # The second return is a module, and not a handle/object.
				if not profile[1]._prep_function():
					# TODO: See how we can incorporate this into
					#       the general log flow. As this is pre-installation
					#       session setup. Which creates the installation.log file.
					archinstall.log(
						' * Profile\'s preparation requirements was not fulfilled.',
						bg='black',
						fg='red'
					)
					continue
				break
		else:
			break

# Additional packages (with some light weight error handling for invalid package names)
if not archinstall.arguments.get('packages', None):
	archinstall.arguments['packages'] = [package for package in input('Additional packages aside from base (space separated): ').split(' ') if len(package)]

# Verify packages that were given
try:
	archinstall.validate_package_list(archinstall.arguments['packages'])
except archinstall.RequirementError as e:
	archinstall.log(e, fg='red')
	exit(1)

# Ask or Call the helper function that asks the user to optionally configure a network.
if not archinstall.arguments.get('nic', None):
	archinstall.arguments['nic'] = archinstall.ask_to_configure_network()

print()
print('This is your chosen configuration:')
archinstall.log("-- Guided template chosen (with below config) --", level=archinstall.LOG_LEVELS.Debug)
archinstall.log(json.dumps(archinstall.storage['_guided'], indent=4, sort_keys=True, cls=archinstall.JSON), level=archinstall.LOG_LEVELS.Info)
archinstall.log(json.dumps(archinstall.arguments, indent=4, sort_keys=True, cls=archinstall.JSON), level=archinstall.LOG_LEVELS.Info)
print()

input('Press Enter to continue.')
exit(0)

"""
	Issue a final warning before we continue with something un-revertable.
	We mention the drive one last time, and count from 5 to 0.
"""

print(f" ! Formatting {archinstall.arguments['harddrive']} in ", end='')

for i in range(5, 0, -1):
	print(f"{i}", end='')

	for x in range(4):
		sys.stdout.flush()
		time.sleep(0.25)
		print(".", end='')

	if SIG_TRIGGER:
		abort = input('\nDo you really want to abort (y/n)? ')
		if abort.strip() != 'n':
			exit(0)

		if SIG_TRIGGER is False:
			sys.stdin.read()
		SIG_TRIGGER = False
		signal.signal(signal.SIGINT, sig_handler)
print()
signal.signal(signal.SIGINT, original_sigint_handler)

"""
	Setup the blockdevice, filesystem (and optionally encryption).
	Once that's done, we'll hand over to perform_installation()
"""
with archinstall.Filesystem(harddrive, archinstall.GPT) as fs:
	# Use partitioning helper to set up the disk partitions.
	if disk_password:
		fs.use_entire_disk('luks2')
	else:
		fs.use_entire_disk('ext4')

	if harddrive.partition[1].size == '512M':
		raise OSError('Trying to encrypt the boot partition for petes sake..')
	harddrive.partition[0].format('vfat')

	if disk_password:
		# First encrypt and unlock, then format the desired partition inside the encrypted part.
		# archinstall.luks2() encrypts the partition when entering the with context manager, and
		# unlocks the drive so that it can be used as a normal block-device within archinstall.
		with archinstall.luks2(harddrive.partition[1], 'luksloop', disk_password) as unlocked_device:
			unlocked_device.format('btrfs')

			perform_installation(unlocked_device,
									harddrive.partition[0],
									archinstall.arguments['keyboard-language'],
									archinstall.arguments['mirror-region'])
	else:
		harddrive.partition[1].format('ext4')
		perform_installation(harddrive.partition[1],
								harddrive.partition[0],
								archinstall.arguments['keyboard-language'],
								archinstall.arguments['mirror-region'])