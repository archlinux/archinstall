import archinstall
import json
import urllib.request
import git

# Unmount and close previous runs (Mainly only used for re-runs, but won't hurt.)
archinstall.sys_command(f'umount -R /mnt', suppress_errors=True)
archinstall.sys_command(f'cryptsetup close /dev/mapper/luksloop', suppress_errors=True)

# Select a harddrive and a disk password
harddrive = archinstall.all_disks()['/dev/sda']
disk_password = '1234'

with archinstall.Filesystem(harddrive, archinstall.GPT) as fs:
	# Use the entire disk instead of setting up partitions on your own
	fs.use_entire_disk('luks2')

	if harddrive.partition[1].size == '512M':
		raise OSError('Trying to encrypt the boot partition for petes sake..')
	harddrive.partition[0].format('fat32')

	with archinstall.luks2(harddrive.partition[1], 'luksloop', disk_password) as unlocked_device:
		unlocked_device.format('btrfs')
		
		with archinstall.Installer(
				unlocked_device,
				boot_partition=harddrive.partition[0],
				hostname="testmachine"
		) as installation:
			if installation.minimal_installation():
				installation.add_bootloader()

				installation.add_additional_packages(['nano', 'wget', 'git'])
				installation.install_profile('awesome')

				installation.user_create('anton', 'test')
				installation.user_set_pw('root', 'toor')

				repo = git.Repo('./')
				commit = repo.head.commit.hexsha[:7]

				print(f'Submitting {commit}: success')

				conditions = {
					"project": "archinstall",
					"profile": "52-54-00-12-34-56",
					"status": "success",
					"commit": commit
				}
				req = urllib.request.Request("https://api.archlinux.life/build/success",
												data=json.dumps(conditions).encode('utf8'),
												headers={'content-type': 'application/json'})
				try:
					urllib.request.urlopen(req, timeout=5)
				except:
					pass