#!/usr/bin/python3
import traceback
import os, re, struct, sys, json
import urllib.request, urllib.parse, ssl
from glob import glob
#from select import epoll, EPOLLIN, EPOLLHUP
from socket import socket, inet_ntoa, AF_INET, AF_INET6, AF_PACKET
from collections import OrderedDict as oDict
from subprocess import Popen, STDOUT, PIPE
from time import sleep

try:
	import psutil
except:
	## Time to monkey patch in all the stats and psutil fuctions if it isn't installed.

	class mem():
		def __init__(self, free, percent=-1):
			self.free = free
			self.percent = percent

	class disk():
		def __init__(self, size, free, percent):
			self.size = size
			self.free = free
			self.percent = percent

	class iostat():
		def __init__(self, interface, bytes_sent=0, bytes_recv=0):
			self.interface = interface
			self.bytes_recv = int(bytes_recv)
			self.bytes_sent = int(bytes_sent)
		def __repr__(self, *args, **kwargs):
			return f'iostat@{self.interface}[bytes_sent: {self.bytes_sent}, bytes_recv: {self.bytes_recv}]'

	class psutil():
		def cpu_percent(interval=0):
			## This just counts the ammount of time the CPU has spent. Find a better way!
			with cmd("grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$4+$5)} END {print usage}'") as output:
				for line in output:
					return float(line.strip().decode('UTF-8'))
		
		def virtual_memory():
			with cmd("grep 'MemFree: ' /proc/meminfo | awk '{free=($2)} END {print free}'") as output:
				for line in output:
					return mem(float(line.strip().decode('UTF-8')))

		def disk_usage(partition):
			disk_stats = os.statvfs(partition)
			free_size = disk_stats.f_bfree * disk_stats.f_bsize
			disk_size = disk_stats.f_blocks * disk_stats.f_bsize
			percent = (100/disk_size)*free_size
			return disk(disk_size, free_size, percent)

		def net_if_addrs():
			interfaces = {}
			for root, folders, files in os.walk('/sys/class/net/'):
				for name in folders:
					interfaces[name] = {}
			return interfaces

		def net_io_counters(pernic=True):
			data = {}
			for interface in psutil.net_if_addrs().keys():
				with cmd("grep '{interface}:' /proc/net/dev | awk '{{recv=$2}}{{send=$10}} END {{print send,recv}}'".format(interface=interface)) as output:
					for line in output:
						data[interface] = iostat(interface, *line.strip().decode('UTF-8').split(' ',1))
			return data

## FIXME: dependency checks (fdisk, lsblk etc)

rootdir_pattern = re.compile('^.*?/devices')
harddrives = oDict()

## == Profiles Path can be set via --profiles-path=/path
##    This just sets the default path if the parameter is omitted.
profiles_path = 'https://raw.githubusercontent.com/Torxed/archinstall/master/deployments'

args = {}
positionals = []
for arg in sys.argv[1:]:
	if '--' == arg[:2]:
		if '=' in arg:
			key, val = [x.strip() for x in arg[2:].split('=')]
		else:
			key, val = arg[2:], True
		args[key] = val
	else:
		positionals.append(arg)

def get_default_gateway_linux():
	"""Read the default gateway directly from /proc."""
	with open("/proc/net/route") as fh:
		for line in fh:
			fields = line.strip().split()
			if fields[1] != '00000000' or not int(fields[3], 16) & 2:
				continue

			return inet_ntoa(struct.pack("<L", int(fields[2], 16)))

def get_local_MACs():
	macs = {}
	for nic, opts in psutil.net_if_addrs().items():
		for addr in opts:
			#if addr.family in (AF_INET, AF_INET6) and addr.address:
			if addr.family == AF_PACKET: # MAC
				macs[addr.address] = nic
	return macs

def gen_yubikey_password():
	return None #TODO: Implement

def run(cmd, echo=False, opts=None, *args, **kwargs):
	if not opts: opts = {}
	if echo or 'debug' in opts:
		print('[!] {}'.format(cmd))
	handle = Popen(cmd, shell='True', stdout=PIPE, stderr=STDOUT, **kwargs)
	output = b''
	while handle.poll() is None:
		data = handle.stdout.read()
		if len(data):
			if echo or 'debug' in opts:
				print(data.decode('UTF-8'), end='')
		#	print(data.decode('UTF-8'), end='')
			output += data
	data = handle.stdout.read()
	if echo or 'debug' in opts:
		print(data.decode('UTF-8'), end='')
	output += data
	handle.stdout.close()
	return output

def update_git():
	default_gw = get_default_gateway_linux()
	if(default_gw):
		## Not the most elegant way to make sure git conflicts doesn't occur (yea fml)
		#os.remove('/root/archinstall/archinstall.py')
		#os.remove('/root/archinstall/README.md')
		output = run('(cd /root/archinstall; git fetch --all)') # git reset --hard origin/<branch_name>
		
		if b'error:' in output:
			print('[N] Could not update git source for some reason.')
			return

		# b'From github.com:Torxed/archinstall\n   339d687..80b97f3  master     -> origin/master\nUpdating 339d687..80b97f3\nFast-forward\n README.md | 2 +-\n 1 file changed, 1 insertion(+), 1 deletion(-)\n'
		tmp = re.findall(b'[0-9]+ file changed', output)
		if len(tmp):
			num_changes = int(tmp[0].split(b' ',1)[0])
			if(num_changes):
				## Reboot the script (in same context)
				os.execv('/usr/bin/python3', ['archinstall.py', 'archinstall.py'] + sys.argv[1:])

def device_state(name):
	# Based out of: https://askubuntu.com/questions/528690/how-to-get-list-of-all-non-removable-disk-device-names-ssd-hdd-and-sata-ide-onl/528709#528709
	if os.path.isfile('/sys/block/{}/device/block/{}/removable'.format(name, name)):
		with open('/sys/block/{}/device/block/{}/removable'.format(name, name)) as f:
			if f.read(1) == '1':
				return

	path = rootdir_pattern.sub('', os.readlink('/sys/block/{}'.format(name)))
	hotplug_buses = ("usb", "ieee1394", "mmc", "pcmcia", "firewire")
	for bus in hotplug_buses:
		if os.path.exists('/sys/bus/{}'.format(bus)):
			for device_bus in os.listdir('/sys/bus/{}/devices'.format(bus)):
				device_link = rootdir_pattern.sub('', os.readlink('/sys/bus/{}/devices/{}'.format(bus, device_bus)))
				if re.search(device_link, path):
					return
	return True

def grab_partitions(dev):
	drive_name = os.path.basename(dev)
	parts = oDict()
	o = run('lsblk -o name -J -b {dev}'.format(dev=dev))
	if b'not a block device' in o:
		## TODO: Replace o = run() with code, o = run()
		##       and make run() return the exit-code, way safer than checking output strings :P
		return {}
	r = json.loads(o)
	if len(r['blockdevices']) and 'children' in r['blockdevices'][0]:
		for part in r['blockdevices'][0]['children']:
			parts[part['name'][len(drive_name):]] = {
				# TODO: Grab partition info and store here?
			}

	return parts

def update_drive_list():
	for path in glob('/sys/block/*/device'):
		name = re.sub('.*/(.*?)/device', '\g<1>', path)
		if device_state(name):
			harddrives['/dev/{}'.format(name)] = psutil.disk_usage('/dev/{}'.format(name))

def multisplit(s, splitters):
	s = [s,]
	for key in splitters:
		ns = []
		for obj in s:
			x = obj.split(key)
			for index, part in enumerate(x):
				if len(part):
					ns.append(part)
				if index < len(x)-1:
					ns.append(key)
		s = ns
	return s

def grab_url_data(path):
	safe_path = path[:path.find(':')+1]+''.join([item if item in ('/', '?', '=', '&') else urllib.parse.quote(item) for item in multisplit(path[path.find(':')+1:], ('/', '?', '=', '&'))])
	ssl_context = ssl.create_default_context()
	ssl_context.check_hostname = False
	ssl_context.verify_mode=ssl.CERT_NONE
	response = urllib.request.urlopen(safe_path, context=ssl_context)
	return response.read()

def get_instructions(target):
	instructions = {}
	try:
		instructions = grab_url_data('{}/{}.json'.format(args['profiles-path'], target))
	except urllib.error.HTTPError:
		print('[N] No instructions found called: {}'.format(target))
		return instructions
	
	print('[N] Found net-deploy instructions called: {}'.format(target))
	try:
		instructions = json.loads(instructions.decode('UTF-8'), object_pairs_hook=oDict)
	except:
		print('[E] JSON syntax error in {}'.format('{}/{}.json'.format(args['profiles-path'], target)))
		traceback.print_exc()
		exit(1)

	return instructions

def merge_dicts(d1, d2, before=True, overwrite=False):
	""" Merges d2 into d1 """
	if before:
		d1, d2 = d2.copy(), d1.copy()
		overwrite = True

	for key, val in d2.items():
		if key in d1:
			if type(d1[key]) in [dict, oDict] and type(d2[key]) in [dict, oDict]:
				d1[key] = merge_dicts(d1[key] if not before else d2[key], d2[key] if not before else d1[key], before=before, overwrite=overwrite)
			elif overwrite:
				d1[key] = val
		else:
			d1[key] = val

	return d1

if __name__ == '__main__':
	update_git() # Breaks and restarts the script if an update was found.
	update_drive_list()
	if not os.path.isdir('/sys/firmware/efi'):
		print('[E] This script only supports UEFI-booted machines.')
		exit(1)

	## Setup some defaults (in case no command-line parameters or netdeploy-params were given)
	if not 'drive' in args: args['drive'] = list(harddrives.keys())[0] # First drive found
	if not 'size' in args: args['size'] = '100%'
	if not 'start' in args: args['start'] = '513MiB'
	if not 'pwfile' in args: args['pwfile'] = '/tmp/diskpw'
	if not 'hostname' in args: args['hostname'] = 'Arcinstall'
	if not 'country' in args: args['country'] = 'SE' # 'all' if we don't want country specific mirrors.
	if not 'packages' in args: args['packages'] = '' # extra packages other than default
	if not 'post' in args: args['post'] = 'reboot'
	if not 'password' in args: args['password'] = '0000' # Default disk passord, can be <STDIN> or a fixed string
	if not 'default' in args: args['default'] = False
	if not 'profile' in args: args['profile'] = None
	if not 'profiles-path' in args: args['profiles-path'] = profiles_path

	## == If we got networking,
	#     Try fetching instructions for this box and execute them.
	instructions = {}
	if get_default_gateway_linux():
		locmac = get_local_MACs()
		if not len(locmac):
			print('[N] No network interfaces - No net deploy.')
		else:
			for mac in locmac:
				instructions = get_instructions(mac)

				if 'args' in instructions:
					## == Recursively fetch instructions if "include" is found under {args: ...}
					while 'include' in instructions['args']:
						includes = instructions['args']['include']
						print('[!] Importing net-deploy target: {}'.format(includes))
						del(instructions['args']['include'])
						if type(includes) in (dict, list):
							for include in includes:
								instructions = merge_dicts(instructions, get_instructions(include), before=True)
						else:
							instructions = merge_dicts(instructions, get_instructions(includes), before=True)

					## Update arguments if we found any
					for key, val in instructions['args'].items():
						args[key] = val
	else:
		print('[N] No gateway - No net deploy')

	if args['profile'] and not args['default']:
		instructions = get_instructions(args['profile'])
		if len(instructions) <= 0:
			print('[E] No instructions by the name of {} was found.'.format(args['profile']))
			print('    Installation won\'t continue until a valid profile is given.')
			print('   (this is because --profile was given and a --default is not given)')
			exit(1)
	else:
		first = True
		while not args['default'] and not args['profile'] and len(instructions) <= 0:
			profile = input('What template do you want to install: ')
			instructions = get_instructions(profile)
			if first and len(instructions) <= 0:
				print('[E] No instructions by the name of {} was found.'.format(profile))
				print('    Installation won\'t continue until a valid profile is given.')
				print('   (this is because --default is not instructed and no --profile given)')
				first = False


	if 'args' in instructions:
		## == Recursively fetch instructions if "include" is found under {args: ...}
		while 'include' in instructions['args']:
			includes = instructions['args']['include']
			print('[!] Importing net-deploy target: {}'.format(includes))
			del(instructions['args']['include'])
			if type(includes) in (dict, list):
				for include in includes:
					instructions = merge_dicts(instructions, get_instructions(include), before=True)
			else:
				instructions = merge_dicts(instructions, get_instructions(includes), before=True)

		## Update arguments if we found any
		for key, val in instructions['args'].items():
			args[key] = val

	if 'args' in instructions:
		## TODO: Reuseable code, there's to many get_instructions, merge_dictgs and args updating going on.
		## Update arguments if we found any
		for key, val in instructions['args'].items():
			args[key] = val

	if args['password'] == '<STDIN>': args['password'] = input('Enter a disk (and root) password: ')
	elif args['password'] == '<YUBIKEY>':
		args['password'] = gen_yubikey_password()
		if not args['password']:
			print('[E] Failed to setup a yubikey password, is it plugged in?')
			exit(1)

	print(json.dumps(args, indent=4))

	if not os.path.isfile(args['pwfile']):
		#PIN = '0000'
		with open(args['pwfile'], 'w') as pw:
			pw.write(args['password'])
	#else:
	#	## TODO: Convert to `rb` instead.
	#	#        We shouldn't discriminate \xfu from being a passwd phrase.
	#	with open(args['pwfile'], 'r') as pw:
	#		PIN = pw.read().strip()

	print()
	print('[!] Disk PASSWORD is: {}'.format(args['password']))
	print()
	print('[N] Setting up {drive}.'.format(**args))
	# dd if=/dev/random of=args['drive'] bs=4096 status=progress
	# https://github.com/dcantrell/pyparted	would be nice, but isn't officially in the repo's #SadPanda
	o = run('parted -s {drive} mklabel gpt'.format(**args))
	o = run('parted -s {drive} mkpart primary FAT32 1MiB {start}'.format(**args))
	o = run('parted -s {drive} name 1 "EFI"'.format(**args))
	o = run('parted -s {drive} set 1 esp on'.format(**args))
	o = run('parted -s {drive} set 1 boot on'.format(**args))
	o = run('parted -s {drive} mkpart primary {start} {size}'.format(**args))
	
	args['paritions'] = grab_partitions(args['drive'])
	if len(args['paritions']) <= 0:
		print('[E] No paritions were created on {drive}'.format(**args), o)
		exit(1)
	for index, part_name in enumerate(args['paritions']):
		args['partition_{}'.format(index+1)] = part_name

	o = run('mkfs.vfat -F32 {drive}{partition_1}'.format(**args))
	if (b'mkfs.fat' not in o and b'mkfs.vfat' not in o) or b'command not found' in o:
		print('[E] Could not setup {drive}{partition_1}'.format(**args), o)
		exit(1)

	# "--cipher sha512" breaks the shit.
	# TODO: --use-random instead of --use-urandom
	print('[N] Adding encryption to {drive}{partition_2}.'.format(**args))
	o = run('cryptsetup -q -v --type luks2 --pbkdf argon2i --hash sha512 --key-size 512 --iter-time 10000 --key-file {pwfile} --use-urandom luksFormat {drive}{partition_2}'.format(**args))
	if not 'Command successful.' in o.decode('UTF-8').strip():
		print('[E] Failed to setup disk encryption.', o)
		exit(1)

	o = run('cryptsetup open {drive}{partition_2} luksdev --key-file {pwfile} --type luks2'.format(**args))
	o = run('file /dev/mapper/luksdev') # /dev/dm-0
	if b'cannot open' in o:
		print('[E] Could not mount encrypted device.', o)
		exit(1)

	print('[N] Creating btrfs filesystem inside {drive}{partition_2}'.format(**args))
	o = run('mkfs.btrfs /dev/mapper/luksdev')
	if not b'UUID' in o:
		print('[E] Could not setup btrfs filesystem.', o)
		exit(1)
	o = run('mount /dev/mapper/luksdev /mnt')

	os.makedirs('/mnt/boot')
	o = run('mount {drive}{partition_1} /mnt/boot'.format(**args))

	print('[N] Reordering mirrors.')
	if 'mirrors' in args and args['mirrors'] and get_default_gateway_linux():
		o = run("wget 'https://www.archlinux.org/mirrorlist/?country={country}&protocol=https&ip_version=4&ip_version=6&use_mirror_status=on' -O /root/mirrorlist".format(**args))
		o = run("sed -i 's/#Server/Server/' /root/mirrorlist")
		o = run('rankmirrors -n 6 /root/mirrorlist > /etc/pacman.d/mirrorlist')

	pre_conf = {}
	if 'pre' in instructions:
		pre_conf = instructions['pre']
	elif 'prerequisits' in instructions:
		pre_conf = instructions['prerequisits']

	## Prerequisit steps needs to NOT be executed in arch-chroot.
	## Mainly because there's no root structure to chroot into.
	## But partly because some configurations need to be done against the live CD.
	## (For instance, modifying mirrors are done on LiveCD and replicated intwards)
	for title in pre_conf:
		print('[N] Network prerequisit step: {}'.format(title))
		for command in pre_conf[title]:
			raw_command = command
			opts = pre_conf[title][raw_command] if type(pre_conf[title][raw_command]) in (dict, oDict) else {}
			if len(opts):
				if 'pass-args' in opts or 'format' in opts:
					command = command.format(**args)
					## FIXME: Instead of deleting the two options
					##        in order to mute command output further down,
					##        check for a 'debug' flag per command and delete these two
					if 'pass-args' in opts:
						del(opts['pass-args'])
					elif 'format' in opts:
						del(opts['format'])
				elif 'debug' in opts and opts['debug']:
					print('[N] Complete command-string: '.format(command))
				else:
					print('[-] Options: {}'.format(opts))

			#print('[N] Command: {} ({})'.format(raw_command, opts))
			o = run('{c}'.format(c=command), opts)
			if type(conf[title][raw_command]) == bytes and len(conf[title][raw_command]) and not conf[title][raw_command] in o:
				print('[W] Prerequisit step failed: {}'.format(o.decode('UTF-8')))
			#print(o)

	print('[N] Straping in packages.')
	o = run('pacman -Syy')
	o = run('pacstrap /mnt base base-devel btrfs-progs efibootmgr nano wpa_supplicant dialog {packages}'.format(**args))

	if not os.path.isdir('/mnt/etc'):
		print('[E] Failed to strap in packages', o)
		exit(1)

	o = run('genfstab -pU /mnt >> /mnt/etc/fstab')
	with open('/mnt/etc/fstab', 'a') as fstab:
		fstab.write('\ntmpfs /tmp tmpfs defaults,noatime,mode=1777 0 0\n') # Redundant \n at the start? who knoes?

	o = run('arch-chroot /mnt rm /etc/localtime')
	o = run('arch-chroot /mnt ln -s /usr/share/zoneinfo/Europe/Stockholm /etc/localtime')
	o = run('arch-chroot /mnt hwclock --hctosys --localtime')
	#o = run('arch-chroot /mnt echo "{hostname}" > /etc/hostname'.format(**args))
	#o = run("arch-chroot /mnt sed -i 's/#\(en_US\.UTF-8\)/\1/' /etc/locale.gen")
	o = run("arch-chroot /mnt sh -c \"echo '{hostname}' > /etc/hostname\"".format(**args))
	o = run("arch-chroot /mnt sh -c \"echo 'en_US.UTF-8 UTF-8' > /etc/locale.gen\"")
	o = run("arch-chroot /mnt sh -c \"echo 'LANG=en_US.UTF-8' > /etc/locale.conf\"")
	o = run('arch-chroot /mnt locale-gen')
	o = run('arch-chroot /mnt chmod 700 /root')

	with open('/mnt/etc/mkinitcpio.conf', 'w') as mkinit:
		## TODO: Don't replace it, in case some update in the future actually adds something.
		mkinit.write('MODULES=(btrfs)\n')
		mkinit.write('BINARIES=(/usr/bin/btrfs)\n')
		mkinit.write('FILES=()\n')
		mkinit.write('HOOKS=(base udev autodetect modconf block encrypt filesystems keyboard fsck)\n')
	o = run('arch-chroot /mnt mkinitcpio -p linux')
	o = run('arch-chroot /mnt bootctl --path=/boot install')

	with open('/mnt/boot/loader/loader.conf', 'w') as loader:
		loader.write('default arch\n')
		loader.write('timeout 5\n')

	## For some reason, blkid and /dev/disk/by-uuid are not getting along well.
	## And blkid is wrong in terms of LUKS.
	#UUID = run('blkid -s PARTUUID -o value {drive}{partition_2}'.format(**args)).decode('UTF-8').strip()
	UUID = run("ls -l /dev/disk/by-uuid/ | grep {basename}{partition_2} | awk '{{print $9}}'".format(basename=os.path.basename(args['drive']), **args)).decode('UTF-8').strip()
	with open('/mnt/boot/loader/entries/arch.conf', 'w') as entry:
		entry.write('title Arch Linux\n')
		entry.write('linux /vmlinuz-linux\n')
		entry.write('initrd /initramfs-linux.img\n')
		entry.write('options cryptdevice=UUID={UUID}:luksdev root=/dev/mapper/luksdev rw intel_pstate=no_hwp\n'.format(UUID=UUID))

	conf = {}
	if 'post' in instructions:
		conf = instructions['post']
	elif not 'args' in instructions and len(instructions):
		conf = instructions

	for title in conf:
		print('[N] Network Deploy: {}'.format(title))
		for command in conf[title]:
			raw_command = command
			opts = conf[title][command] if type(conf[title][command]) in (dict, oDict) else {}
			if len(opts):
				if 'pass-args' in opts or 'format' in opts:
					command = command.format(**args)
					## FIXME: Instead of deleting the two options
					##        in order to mute command output further down,
					##        check for a 'debug' flag per command and delete these two
					if 'pass-args' in opts:
						del(opts['pass-args'])
					elif 'format' in opts:
						del(opts['format'])
				else:
					print('[-] Options: {}'.format(opts))
			if 'pass-args' in opts and opts['pass-args']:
				command = command.format(**args)

			#print('[N] Command: {} ({})'.format(command, opts))

			## https://superuser.com/questions/1242978/start-systemd-nspawn-and-execute-commands-inside
			## !IMPORTANT
			##
			## arch-chroot mounts /run into the chroot environment, this breaks name resolves for some reason.
			## Either skipping mounting /run and using traditional chroot is an option, but using
			## `systemd-nspawn -D /mnt --machine temporary` might be a more flexible solution in case of file structure changes.
			if 'no-chroot' in opts and opts['no-chroot']:
				o = run(command, opts)
			elif 'chroot' in opts and opts['chroot']:
				## Run in a manually set up version of arch-chroot (arch-chroot will break namespaces).
				## This is a bit risky in case the file systems changes over the years, but we'll probably be safe adding this as an option.
				## **> Prefer if possible to use 'no-chroot' instead which "live boots" the OS and runs the command.
				o = run("mount /dev/mapper/luksdev /mnt")
				o = run("cd /mnt; cp /etc/resolv.conf etc")
				o = run("cd /mnt; mount -t proc /proc proc")
				o = run("cd /mnt; mount --make-rslave --rbind /sys sys")
				o = run("cd /mnt; mount --make-rslave --rbind /dev dev")
				o = run('chroot /mnt /bin/bash -c "{c}"'.format(c=command))
				o = run("cd /mnt; umount -R dev")
				o = run("cd /mnt; umount -R sys")
				o = run("cd /mnt; umount -R proc")
			else:
				if 'boot' in opts and opts['boot']:
					o = run('systemd-nspawn -D /mnt -b --machine temporary {c}'.format(c=command), opts)
				else:
					o = run('systemd-nspawn -D /mnt --machine temporary {c}'.format(c=command), opts)
			if type(conf[title][raw_command]) == bytes and len(conf[title][raw_command]) and not conf[title][raw_command] in o:
				print('[W] Post install command failed: {}'.format(o.decode('UTF-8')))
			#print(o)

	## == Passwords
	# o = run('arch-chroot /mnt usermod --password {} root'.format(args['password']))
	# o = run("arch-chroot /mnt sh -c 'echo {pin} | passwd --stdin root'".format(pin='"{pin}"'.format(**args, pin=args['password'])), echo=True)
	o = run("arch-chroot /mnt sh -c \"echo 'root:{pin}' | chpasswd\"".format(**args, pin=args['password']))
	if 'user' in args:
		o = run('arch-chroot /mnt useradd -m -G wheel {user}'.format(**args))
		o = run("arch-chroot /mnt sh -c \"echo '{user}:{pin}' | chpasswd\"".format(**args, pin=args['password']))

	if args['post'] == 'reboot':
		o = run('umount -R /mnt')
		o = run('reboot now')
	else:
		print('Done. "umount -R /mnt; reboot" when you\'re done tinkering.')
