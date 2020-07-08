import archinstall, getpass, time

# Unmount and close previous runs
archinstall.sys_command(f'umount -R /mnt', surpress_errors=True)
archinstall.sys_command(f'cryptsetup close /dev/mapper/luksloop', surpress_errors=True)

"""
  First, we'll ask the user for a bunch of user input.
  Not until we're satisfied with what we want to install
  will we continue with the actual installation steps.
"""
harddrive = archinstall.select_disk(archinstall.all_disks())
while (disk_password := getpass.getpass(prompt='Enter disk encryption password (leave blank for no encryption): ')):
	disk_password_verification = getpass.getpass(prompt='And one more time for verification: ')
	if disk_password != disk_password_verification:
		archinstall.log(' * Passwords did not match * ', bg='black', fg='red')
		continue
	break
hostname = input('Desired hostname for the installation: ')
if len(hostname) == 0: hostname = 'ArchInstall'

while (root_pw := getpass.getpass(prompt='Enter root password (leave blank for no password): ')):
	root_pw_verification = getpass.getpass(prompt='And one more time for verification: ')
	if root_pw != root_pw_verification:
		archinstall.log(' * Passwords did not match * ', bg='black', fg='red')
		continue
	break

users = {}
while 1:
	new_user = input('Any additional users to install (leave blank for no users): ')
	if not len(new_user.strip()): break
	new_user_passwd = getpass.getpass(prompt=f'Password for user {new_user}: ')
	new_user_passwd_verify = getpass.getpass(prompt=f'Enter password again for verification: ')
	if new_user_passwd != new_user_passwd_verify:
		archinstall.log(' * Passwords did not match * ', bg='black', fg='red')
		continue

	users[new_user] = new_user_passwd

aur = input('Would you like AUR support? (leave blank for no): ')
if len(aur.strip()):
	archinstall.log(' - AUR support provided by yay (https://aur.archlinux.org/packages/yay/)', bg='black', fg='white')

profile = input('Any particular profile you want to install: ')
packages = input('Additional packages aside from base (space separated): ').split(' ')


"""
	Issue a final warning before we continue with something un-revertable.
"""
print(f' ! Formatting {harddrive} in 5...')
time.sleep(1)
print(f' ! Formatting {harddrive} in 4...')
time.sleep(1)
print(f' ! Formatting {harddrive} in 3...')
time.sleep(1)
print(f' ! Formatting {harddrive} in 2...')
time.sleep(1)
print(f' ! Formatting {harddrive} in 1...')
time.sleep(1)

def perform_installation(device, boot_partition):
	with archinstall.Installer(device, boot_partition=boot_partition, hostname=hostname) as installation:
		if installation.minimal_installation():
			installation.add_bootloader()

			if len(packages) and packages[0] != '':
				installation.add_additional_packages(packages)

			if len(profile.strip()):
				installation.install_profile(profile)

			for user, password in users.items():
				installation.user_create(user, password)

			if root_pw:
				installation.user_set_pw('root', root_pw)

			if len(aur.strip()):
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