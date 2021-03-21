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


def ask_user_questions():
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
	else:
		selected_region = archinstall.arguments['mirror-region']
		archinstall.arguments['mirror-region'] = {selected_region : archinstall.list_mirrors()[selected_region]}


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
		archinstall.log(f"{archinstall.arguments['harddrive']} contains the following partitions:", fg='yellow')

		# We curate a list pf supported paritions
		# and print those that we don't support.
		partition_mountpoints = {}
		for partition in archinstall.arguments['harddrive']:
			try:
				if partition.filesystem_supported():
					archinstall.log(f" {partition}")
					partition_mountpoints[partition] = None
			except archinstall.UnknownFilesystemFormat as err:
				archinstall.log(f" {partition} (Filesystem not supported)", fg='red')

		# We then ask what to do with the paritions.
		if (option := archinstall.ask_for_disk_layout()) == 'abort':
			archinstall.log(f"Safely aborting the installation. No changes to the disk or system has been made.")
			exit(1)
		elif option == 'keep-existing':
			archinstall.arguments['harddrive'].keep_partitions = True

			archinstall.log(f" ** You will now select which partitions to use by selecting mount points (inside the installation). **")
			archinstall.log(f" ** The root would be a simple / and the boot partition /boot (as all paths are relative inside the installation). **")
			while True:
				# Select a partition
				partition = archinstall.generic_select(partition_mountpoints.keys(),
														"Select a partition by number that you want to set a mount-point for (leave blank when done): ")
				if not partition:
					break

				# Select a mount-point
				mountpoint = input(f"Enter a mount-point for {partition}: ").strip(' ')
				if len(mountpoint):

					# Get a valid & supported filesystem for the parition:
					while 1:
						new_filesystem = input(f"Enter a valid filesystem for {partition} (leave blank for {partition.filesystem}): ").strip(' ')
						if len(new_filesystem) <= 0:
							if partition.encrypted and partition.filesystem == 'crypto_LUKS':
								old_password = archinstall.arguments.get('!encryption-password', None)
								if not old_password:
									old_password = input(f'Enter the old encryption password for {partition}: ')

								if (autodetected_filesystem := partition.detect_inner_filesystem(old_password)):
									new_filesystem = autodetected_filesystem
								else:
									archinstall.log(f"Could not auto-detect the filesystem inside the encrypted volume.", fg='red')
									archinstall.log(f"A filesystem must be defined for the unlocked encrypted partition.")
									continue
							break

						# Since the potentially new filesystem is new
						# we have to check if we support it. We can do this by formatting /dev/null with the partitions filesystem.
						# There's a nice wrapper for this on the partition object itself that supports a path-override during .format()
						try:
							partition.format(new_filesystem, path='/dev/null', log_formating=False, allow_formatting=True)
						except archinstall.UnknownFilesystemFormat:
							archinstall.log(f"Selected filesystem is not supported yet. If you want archinstall to support '{new_filesystem}', please create a issue-ticket suggesting it on github at https://github.com/Torxed/archinstall/issues.")
							archinstall.log(f"Until then, please enter another supported filesystem.")
							continue
						except archinstall.SysCallError:
							pass # Expected exception since mkfs.<format> can not format /dev/null.
								 # But that means our .format() function supported it.
						break

					# When we've selected all three criterias,
					# We can safely mark the partition for formatting and where to mount it.
					# TODO: allow_formatting might be redundant since target_mountpoint should only be
					#       set if we actually want to format it anyway.
					partition.allow_formatting = True
					partition.target_mountpoint = mountpoint
					# Only overwrite the filesystem definition if we selected one:
					if len(new_filesystem):
						partition.filesystem = new_filesystem

			archinstall.log('Using existing partition table reported above.')
		elif option == 'format-all':
			archinstall.arguments['filesystem'] = archinstall.ask_for_main_filesystem_format()
			archinstall.arguments['harddrive'].keep_partitions = False
	else:
		# If the drive doesn't have any partitions, safely mark the disk with keep_partitions = False
		# and ask the user for a root filesystem.
		archinstall.arguments['filesystem'] = archinstall.ask_for_main_filesystem_format()
		archinstall.arguments['harddrive'].keep_partitions = False

	# Get disk encryption password (or skip if blank)
	if not archinstall.arguments.get('!encryption-password', None):
		if passwd := archinstall.get_password(prompt='Enter disk encryption password (leave blank for no encryption): '):
			archinstall.arguments['!encryption-password'] = passwd
			archinstall.arguments['harddrive'].encryption_password = archinstall.arguments['!encryption-password']

	# Get the hostname for the machine
	if not archinstall.arguments.get('hostname', None):
		archinstall.arguments['hostname'] = input('Desired hostname for the installation: ').strip(' ')

	# Ask for a root password (optional, but triggers requirement for super-user if skipped)
	if not archinstall.arguments.get('!root-password', None):
		archinstall.arguments['!root-password'] = archinstall.get_password(prompt='Enter root password (Recommendation: leave blank to leave root disabled): ')

	# Ask for additional users (super-user if root pw was not set)
	archinstall.arguments['users'] = {}
	archinstall.arguments['superusers'] = {}
	if not archinstall.arguments.get('!root-password', None):
		archinstall.arguments['superusers'] = archinstall.ask_for_superuser_account('Create a required super-user with sudo privileges: ', forced=True)

	users, superusers = archinstall.ask_for_additional_users('Enter a username to create a additional user (leave blank to skip & continue): ')
	archinstall.arguments['users'] = users
	archinstall.arguments['superusers'] = {**archinstall.arguments['superusers'], **superusers}

	# Ask for archinstall-specific profiles (such as desktop environments etc)
	if not archinstall.arguments.get('profile', None):
		archinstall.arguments['profile'] = archinstall.select_profile(archinstall.list_profiles())
	else:
		archinstall.arguments['profile'] = archinstall.list_profiles()[archinstall.arguments['profile']]

	# Check the potentially selected profiles preperations to get early checks if some additional questions are needed.
	if archinstall.arguments['profile'] and archinstall.arguments['profile'].has_prep_function():
		with archinstall.arguments['profile'].load_instructions(namespace=f"{archinstall.arguments['profile'].namespace}.py") as imported:
			if not imported._prep_function():
				archinstall.log(
					' * Profile\'s preparation requirements was not fulfilled.',
					bg='black',
					fg='red'
				)
				exit(1)

	# Additional packages (with some light weight error handling for invalid package names)
	if not archinstall.arguments.get('packages', None):
		archinstall.arguments['packages'] = [package for package in input('Write additional packages to install (space separated, leave blank to skip): ').split(' ') if len(package)]

	# Verify packages that were given
	try:
		archinstall.validate_package_list(archinstall.arguments['packages'])
	except archinstall.RequirementError as e:
		archinstall.log(e, fg='red')
		exit(1)

	# Ask or Call the helper function that asks the user to optionally configure a network.
	if not archinstall.arguments.get('nic', None):
		archinstall.arguments['nic'] = archinstall.ask_to_configure_network()
		if not archinstall.arguments['nic']:
			archinstall.log(f"No network configuration was selected. Network is going to be unavailable until configured manually!", fg="yellow")

	if not archinstall.arguments.get('timezone', None):
		archinstall.arguments['timezone'] = archinstall.ask_for_a_timezone()


def perform_installation_steps():
	global SIG_TRIGGER

	print()
	print('This is your chosen configuration:')
	archinstall.log("-- Guided template chosen (with below config) --", level=archinstall.LOG_LEVELS.Debug)
	archinstall.log(json.dumps(archinstall.arguments, indent=4, sort_keys=True, cls=archinstall.JSON), level=archinstall.LOG_LEVELS.Info)
	print()

	input('Press Enter to continue.')

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

	# Put back the default/original signal handler now that we're done catching
	# and interrupting SIGINT with "Do you really want to abort".
	print()
	signal.signal(signal.SIGINT, original_sigint_handler)

	"""
		Setup the blockdevice, filesystem (and optionally encryption).
		Once that's done, we'll hand over to perform_installation()
	"""
	with archinstall.Filesystem(archinstall.arguments['harddrive'], archinstall.GPT) as fs:
		# Wipe the entire drive if the disk flag `keep_partitions`is False.
		if archinstall.arguments['harddrive'].keep_partitions is False:
			fs.use_entire_disk(root_filesystem_type=archinstall.arguments.get('filesystem', 'btrfs'),
								encrypt_root_partition=archinstall.arguments.get('!encryption-password', False))
		# Otherwise, check if encryption is desired and mark the root partition as encrypted.
		elif archinstall.arguments.get('!encryption-password', None):
			root_partition = fs.find_partition('/')
			root_partition.encrypted = True
				
		# After the disk is ready, iterate the partitions and check
		# which ones are safe to format, and format those.
		for partition in archinstall.arguments['harddrive']:
			if partition.safe_to_format():
				# Partition might be marked as encrypted due to the filesystem type crypt_LUKS
				# But we might have omitted the encryption password question to skip encryption.
				# In which case partition.encrypted will be true, but passwd will be false.
				if partition.encrypted and (passwd := archinstall.arguments.get('!encryption-password', None)):
					partition.encrypt(password=passwd)
				else:
					partition.format()
			else:
				archinstall.log(f"Did not format {partition} because .safe_to_format() returned False or .allow_formatting was False.", level=archinstall.LOG_LEVELS.Debug)

		if archinstall.arguments.get('!encryption-password', None):
			# First encrypt and unlock, then format the desired partition inside the encrypted part.
			# archinstall.luks2() encrypts the partition when entering the with context manager, and
			# unlocks the drive so that it can be used as a normal block-device within archinstall.
			with archinstall.luks2(fs.find_partition('/'), 'luksloop', archinstall.arguments.get('!encryption-password', None)) as unlocked_device:
				unlocked_device.format(fs.find_partition('/').filesystem)

				perform_installation(device=unlocked_device,
										boot_partition=fs.find_partition('/boot'),
										language=archinstall.arguments['keyboard-language'],
										mirrors=archinstall.arguments['mirror-region'])
		else:
			perform_installation(device=fs.find_partition('/'),
									boot_partition=fs.find_partition('/boot'),
									language=archinstall.arguments['keyboard-language'],
									mirrors=archinstall.arguments['mirror-region'])


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
			if archinstall.arguments.get('nic', None) == 'Copy ISO network configuration to installation':
				installation.copy_ISO_network_config(enable_services=True) # Sources the ISO network configuration to the install medium.

			# Otherwise, if a interface was selected, configure that interface
			elif archinstall.arguments.get('nic', None):
				installation.configure_nic(**archinstall.arguments.get('nic', {}))
				installation.enable_service('systemd-networkd')
				installation.enable_service('systemd-resolved')


			if archinstall.arguments.get('packages', None) and archinstall.arguments.get('packages', None)[0] != '':
				installation.add_additional_packages(archinstall.arguments.get('packages', None))

			if archinstall.arguments.get('profile', None):
				installation.install_profile(archinstall.arguments.get('profile', None))

			for user, user_info in archinstall.arguments.get('users', {}).items():
				installation.user_create(user, user_info["!password"], sudo=False)
			
			for superuser, user_info in archinstall.arguments.get('superusers', {}).items():
				installation.user_create(superuser, user_info["!password"], sudo=True)

			if (timezone := archinstall.arguments.get('timezone', None)):
				installation.set_timezone(timezone)

			if (root_pw := archinstall.arguments.get('!root-password', None)) and len(root_pw):
				installation.user_set_pw('root', root_pw)


ask_user_questions()
perform_installation_steps()