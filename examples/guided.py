import archinstall, getpass

# Unmount and close previous runs
archinstall.sys_command(f'umount -R /mnt', surpress_errors=True)
archinstall.sys_command(f'cryptsetup close /dev/mapper/luksloop', surpress_errors=True)

# Select a harddrive and a disk password
harddrive = archinstall.select_disk(archinstall.all_disks())
while (disk_password := getpass.getpass(prompt='Enter disk encryption password (leave blank for no encryption): ')):
	disk_password_verification = getpass.getpass(prompt='And one more time for verification: ')
	if disk_password != disk_password_verification:
		archinstall.log(' * Passwords did not match * ', bg='black', fg='red')
		continue
	break

def perform_installation(device, boot_partition):
	hostname = input('Desired hostname for the installation: ')
	with archinstall.Installer(device, hostname=hostname) as installation:
		if installation.minimal_installation():
			installation.add_bootloader(boot_partition)

			packages = input('Additional packages aside from base (space separated): ').split(' ')
			if len(packages) and packages[0] != '':
				installation.add_additional_packages(packages)

			profile = input('Any particular profile you want to install: ')
			if len(profile.strip()):
				installation.install_profile(profile)

			while 1:
				new_user = input('Any additional users to install (leave blank for no users): ')
				if not len(new_user.strip()): break
				new_user_passwd = getpass.getpass(prompt=f'Password for user {new_user}: ')
				new_user_passwd_verify = getpass.getpass(prompt=f'Enter password again for verification: ')
				if new_user_passwd != new_user_passwd_verify:
					archinstall.log(' * Passwords did not match * ', bg='black', fg='red')
					continue

				installation.user_create(new_user, new_user_passwd)

			while (root_pw := getpass.getpass(prompt='Enter root password (leave blank for no password): ')):
				root_pw_verification = getpass.getpass(prompt='And one more time for verification: ')
				if root_pw != root_pw_verification:
					archinstall.log(' * Passwords did not match * ', bg='black', fg='red')
					continue
				installation.user_set_pw('root', root_pw)
				break

			aur = input('Would you like AUR support? (leave blank for no): ')
			if len(aur.strip()):
				archinstall.log(' - AUR support provided by yay (https://aur.archlinux.org/packages/yay/)', bg='black', fg='white')
				installation.add_AUR_support()

with archinstall.Filesystem(harddrive, archinstall.GPT) as fs:
	# Use partitioning helper to set up the disk partitions.
	if disk_password:
		fs.use_entire_disk('luks2')
	else:
		fs.use_entire_disk('ext4')

	if harddrive.partition[1].size == '512M':
		raise OSError('Trying to encrypt the boot partition for petes sake..')
	harddrive.partition[0].format('fat32')

	if disk_password:
		# First encrypt and unlock, then format the desired partition inside the encrypted part.
		with archinstall.luks2(harddrive.partition[1], 'luksloop', disk_password) as unlocked_device:
			unlocked_device.format('btrfs')
			
			perform_installation(unlocked_device, harddrive.partition[0])
	else:
		harddrive.partition[1].format('ext4')
		perform_installation(harddrive.partition[1], harddrive.partition[0])