import getpass, time, json, os
import archinstall
from archinstall.lib.hardware import hasUEFI
from archinstall.lib.profiles import Profile

if archinstall.arguments.get('help'):
	print("See `man archinstall` for help.")
	exit(0)

def ask_user_questions():
	"""
	  First, we'll ask the user for a bunch of user input.
	  Not until we're satisfied with what we want to install
	  will we continue with the actual installation steps.
	"""
	if not archinstall.arguments.get('keyboard-language', None):
		while True:
			try:
				archinstall.arguments['keyboard-language'] = archinstall.select_language(archinstall.list_keyboard_languages()).strip()
				break
			except archinstall.RequirementError as err:
				archinstall.log(err, fg="red")

	# Before continuing, set the preferred keyboard layout/language in the current terminal.
	# This will just help the user with the next following questions.
	if len(archinstall.arguments['keyboard-language']):
		archinstall.set_keyboard_language(archinstall.arguments['keyboard-language'])

	# Set which region to download packages from during the installation
	if not archinstall.arguments.get('mirror-region', None):
		while True:
			try:
				archinstall.arguments['mirror-region'] = archinstall.select_mirror_regions(archinstall.list_mirrors())
				break
			except archinstall.RequirementError as e:
				archinstall.log(e,  fg="red")
	else:
		selected_region = archinstall.arguments['mirror-region']
		archinstall.arguments['mirror-region'] = {selected_region : archinstall.list_mirrors()[selected_region]}


	# Ask which harddrive/block-device we will install to
	if archinstall.arguments.get('harddrive', None):
		archinstall.arguments['harddrive'] = archinstall.BlockDevice(archinstall.arguments['harddrive'])
	else:
		archinstall.arguments['harddrive'] = archinstall.select_disk(archinstall.all_disks())
		if archinstall.arguments['harddrive'] is None:
			archinstall.arguments['target-mount'] = '/mnt'

	# Perform a quick sanity check on the selected harddrive.
	# 1. Check if it has partitions
	# 3. Check that we support the current partitions
	# 2. If so, ask if we should keep them or wipe everything
	if archinstall.arguments['harddrive'] and archinstall.arguments['harddrive'].has_partitions():
		archinstall.log(f"{archinstall.arguments['harddrive']} contains the following partitions:", fg='yellow')

		# We curate a list pf supported partitions
		# and print those that we don't support.
		partition_mountpoints = {}
		for partition in archinstall.arguments['harddrive']:
			try:
				if partition.filesystem_supported():
					archinstall.log(f" {partition}")
					partition_mountpoints[partition] = None
			except archinstall.UnknownFilesystemFormat as err:
				archinstall.log(f" {partition} (Filesystem not supported)", fg='red')

		# We then ask what to do with the partitions.
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

					# Get a valid & supported filesystem for the partition:
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
							archinstall.log(f"Selected filesystem is not supported yet. If you want archinstall to support '{new_filesystem}', please create a issue-ticket suggesting it on github at https://github.com/archlinux/archinstall/issues.")
							archinstall.log(f"Until then, please enter another supported filesystem.")
							continue
						except archinstall.SysCallError:
							pass # Expected exception since mkfs.<format> can not format /dev/null.
								 # But that means our .format() function supported it.
						break

					# When we've selected all three criteria,
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
	elif archinstall.arguments['harddrive']:
		# If the drive doesn't have any partitions, safely mark the disk with keep_partitions = False
		# and ask the user for a root filesystem.
		archinstall.arguments['filesystem'] = archinstall.ask_for_main_filesystem_format()
		archinstall.arguments['harddrive'].keep_partitions = False

	# Get disk encryption password (or skip if blank)
	if archinstall.arguments['harddrive'] and archinstall.arguments.get('!encryption-password', None) is None:
		if (passwd := archinstall.get_password(prompt='Enter disk encryption password (leave blank for no encryption): ')):
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
		archinstall.arguments['profile'] = archinstall.select_profile(filter(lambda profile: (Profile(None, profile).is_top_level_profile()), archinstall.list_profiles()))
	else:
		archinstall.arguments['profile'] = archinstall.list_profiles()[archinstall.arguments['profile']]

	# Check the potentially selected profiles preparations to get early checks if some additional questions are needed.
	if archinstall.arguments['profile'] and archinstall.arguments['profile'].has_prep_function():
		with archinstall.arguments['profile'].load_instructions(namespace=f"{archinstall.arguments['profile'].namespace}.py") as imported:
			if not imported._prep_function():
				archinstall.log(
					' * Profile\'s preparation requirements was not fulfilled.',
					fg='red'
				)
				exit(1)

	# Ask about audio server selection if one is not already set
	if not archinstall.arguments.get('audio', None):
		
		# only ask for audio server selection on a desktop profile 
		if str(archinstall.arguments['profile']) == 'Profile(desktop)':
			archinstall.arguments['audio'] = archinstall.ask_for_audio_selection()
		else:
			# packages installed by a profile may depend on audio and something may get installed anyways, not much we can do about that.
			# we will not try to remove packages post-installation to not have audio, as that may cause multiple issues
			archinstall.arguments['audio'] = None

	# Additional packages (with some light weight error handling for invalid package names)
	while True:
		if not archinstall.arguments.get('packages', None):
			print("Only packages such as base, base-devel, linux, linux-firmware, efibootmgr and optional profile packages are installed.")
			print("If you desire a web browser, such as firefox or chromium, you may specify it in the following prompt.")
			archinstall.arguments['packages'] = [package for package in input('Write additional packages to install (space separated, leave blank to skip): ').split(' ') if len(package)]

		if len(archinstall.arguments['packages']):
			# Verify packages that were given
			try:
				archinstall.log(f"Verifying that additional packages exist (this might take a few seconds)")
				archinstall.validate_package_list(archinstall.arguments['packages'])
				break
			except archinstall.RequirementError as e:
				archinstall.log(e, fg='red')
				archinstall.arguments['packages'] = None # Clear the packages to trigger a new input question
		else:
			# no additional packages were selected, which we'll allow
			break

	# Ask or Call the helper function that asks the user to optionally configure a network.
	if not archinstall.arguments.get('nic', None):
		archinstall.arguments['nic'] = archinstall.ask_to_configure_network()
		if not archinstall.arguments['nic']:
			archinstall.log(f"No network configuration was selected. Network is going to be unavailable until configured manually!", fg="yellow")

	if not archinstall.arguments.get('timezone', None):
		archinstall.arguments['timezone'] = archinstall.ask_for_a_timezone()


def perform_installation_steps():
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

	if archinstall.arguments.get('harddrive', None):
		print(f" ! Formatting {archinstall.arguments['harddrive']} in ", end='')
		archinstall.do_countdown()

		"""
			Setup the blockdevice, filesystem (and optionally encryption).
			Once that's done, we'll hand over to perform_installation()
		"""
		mode = archinstall.GPT
		if hasUEFI() is False:
			mode = archinstall.MBR

		with archinstall.Filesystem(archinstall.arguments['harddrive'], mode) as fs:
			# Wipe the entire drive if the disk flag `keep_partitions`is False.
			if archinstall.arguments['harddrive'].keep_partitions is False:
				fs.use_entire_disk(root_filesystem_type=archinstall.arguments.get('filesystem', 'btrfs'))
			
			# Check if encryption is desired and mark the root partition as encrypted.
			if archinstall.arguments.get('!encryption-password', None):
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

			fs.find_partition('/boot').format('vfat')

			if archinstall.arguments.get('!encryption-password', None):
				# First encrypt and unlock, then format the desired partition inside the encrypted part.
				# archinstall.luks2() encrypts the partition when entering the with context manager, and
				# unlocks the drive so that it can be used as a normal block-device within archinstall.
				with archinstall.luks2(fs.find_partition('/'), 'luksloop', archinstall.arguments.get('!encryption-password', None)) as unlocked_device:
					unlocked_device.format(fs.find_partition('/').filesystem)
					unlocked_device.mount('/mnt')
			else:
				fs.find_partition('/').format(fs.find_partition('/').filesystem)
				fs.find_partition('/').mount('/mnt')

			fs.find_partition('/boot').mount('/mnt/boot')
	
	perform_installation('/mnt')


def perform_installation(mountpoint):
	"""
	Performs the installation steps on a block device.
	Only requirement is that the block devices are
	formatted and setup prior to entering this function.
	"""
	with archinstall.Installer(mountpoint) as installation:
		## if len(mirrors):
		# Certain services might be running that affects the system during installation.
		# Currently, only one such service is "reflector.service" which updates /etc/pacman.d/mirrorlist
		# We need to wait for it before we continue since we opted in to use a custom mirror/region.
		installation.log(f'Waiting for automatic mirror selection (reflector) to complete.', level=archinstall.LOG_LEVELS.Info)
		while archinstall.service_state('reflector') not in ('dead', 'failed'):
			time.sleep(1)

		# Set mirrors used by pacstrap (outside of installation)
		if archinstall.arguments.get('mirror-region', None):
			archinstall.use_mirrors(archinstall.arguments['mirror-region']) # Set the mirrors for the live medium

		if installation.minimal_installation():
			installation.set_hostname(archinstall.arguments['hostname'])
			if archinstall.arguments['mirror-region'].get("mirrors",{})!= None:
				installation.set_mirrors(archinstall.arguments['mirror-region']) # Set the mirrors in the installation medium
			installation.set_keyboard_language(archinstall.arguments['keyboard-language'])
			installation.add_bootloader()

			# If user selected to copy the current ISO network configuration
			# Perform a copy of the config
			if archinstall.arguments.get('nic', {}) == 'Copy ISO network configuration to installation':
				installation.copy_ISO_network_config(enable_services=True) # Sources the ISO network configuration to the install medium.
			elif archinstall.arguments.get('nic', {}).get('NetworkManager',False):
				installation.add_additional_packages("networkmanager")
				installation.enable_service('NetworkManager.service')
			# Otherwise, if a interface was selected, configure that interface
			elif archinstall.arguments.get('nic', {}):
				installation.configure_nic(**archinstall.arguments.get('nic', {}))
				installation.enable_service('systemd-networkd')
				installation.enable_service('systemd-resolved')

			if archinstall.arguments.get('audio', None) != None:
				installation.log(f"This audio server will be used: {archinstall.arguments.get('audio', None)}", level=archinstall.LOG_LEVELS.Info)
				if archinstall.arguments.get('audio', None) == 'pipewire':
					print('Installing pipewire ...')

					installation.add_additional_packages(["pipewire", "pipewire-alsa", "pipewire-jack", "pipewire-media-session", "pipewire-pulse", "gst-plugin-pipewire", "libpulse"])
				elif archinstall.arguments.get('audio', None) == 'pulseaudio':
					print('Installing pulseaudio ...')
					installation.add_additional_packages("pulseaudio")
			else:
				installation.log("No audio server will be installed.", level=archinstall.LOG_LEVELS.Info)
			
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

			if archinstall.arguments['profile'] and archinstall.arguments['profile'].has_post_install():
				with archinstall.arguments['profile'].load_instructions(namespace=f"{archinstall.arguments['profile'].namespace}.py") as imported:
					if not imported._post_install():
						archinstall.log(
							' * Profile\'s post configuration requirements was not fulfilled.',
							fg='red'
						)
						exit(1)

		installation.log("For post-installation tips, see https://wiki.archlinux.org/index.php/Installation_guide#Post-installation", fg="yellow")
		choice = input("Would you like to chroot into the newly created installation and perform post-installation configuration? [Y/n] ")
		if choice.lower() in ("y", ""):
			try:
				installation.drop_to_shell()
			except:
				pass

ask_user_questions()
perform_installation_steps()