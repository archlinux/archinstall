#!/usr/bin/python3
import psutil, os, re, struct, sys
from glob import glob
from socket import inet_ntoa, AF_INET, AF_INET6
from collections import OrderedDict as oDict
from subprocess import Popen, STDOUT, PIPE

rootdir_pattern = re.compile('^.*?/devices')
harddrives = oDict()

args = {}
positionals = []
for arg in sys.argv[1:]:
	if '--' == arg[:2]:
		if '=' in arg:
			key, val = [strip(x) for x in arg[2:].split('=')]
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

	#for nic, opts in psutil.net_if_addrs().items():
	#	for addr in opts:
	#		if addr.family in (AF_INET, AF_INET6) and addr.address:
	#			if addr.address in ('127.0.0.1', '::1'): continue
	#			print(addr)

def run(cmd):
	#print('[!] {}'.format(cmd))
	handle = Popen(cmd, shell='True', stdout=PIPE, stderr=STDOUT)
	output = b''
	while handle.poll() is None:
		data = handle.stdout.read()
		if len(data):
		#	print(data.decode('UTF-8'), end='')
			output += data
	output += handle.stdout.read()
	handle.stdout.close()
	return output

def update_git():
	default_gw = get_default_gateway_linux()
	if(default_gw):
		output = run('git pull')
		
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
	o = run('parted -m -s {} p'.format(dev)).decode('UTF-8')
	parts = oDict()
	for line in o.split('\n'):
		if ':' in line:
			data = line.split(':')
			if data[0].isdigit():
				parts[int(data[0])] = {
					'start' : data[1],
					'end' : data[2],
					'size' : data[3],
					'sum' : data[4],
					'label' : data[5],
					'options' : data[6]
				}
	return parts

def update_drive_list():
	for path in glob('/sys/block/*/device'):
		name = re.sub('.*/(.*?)/device', '\g<1>', path)
		if device_state(name):
			harddrives['/dev/{}'.format(name)] = psutil.disk_usage('/dev/{}'.format(name))

if __name__ == '__main__':
	update_git() # Breaks and restarts the script if an update was found.
	update_drive_list()

	if not 'drive' in args: args['drive'] = list(harddrives.keys())[0] # First drive found
	if not 'size' in args: args['size'] = '100%'
	if not 'start' in args: args['start'] = '513MiB'
	if not 'pwfile' in args: args['pwfile'] = '/tmp/diskpw'
	if not 'hostname' in args: args['hostname'] = 'Arcinstall'
	if not 'country' in args: args['country'] = 'SE' #all
	if not 'packages' in args: args['packages'] = ''
	print(args)

	PIN = '0000'
	with open(args['pwfile'], 'w') as pw:
		pw.write(PIN)
	print('[!] Disk PASSWORD is: {}'.format(PIN))

	# dd if=/dev/random of=args['drive'] bs=4096 status=progress
	# https://github.com/dcantrell/pyparted	would be nice, but isn't officially in the repo's #SadPanda
	o = run('parted -s {drive} mklabel gpt'.format(**args))
	o = run('parted -s {drive} mkpart primary FAT32 1MiB {start}'.format(**args))
	o = run('parted -s {drive} name 1 "EFI"'.format(**args))
	o = run('parted -s {drive} set 1 esp on'.format(**args))
	o = run('parted -s {drive} set 1 boot on'.format(**args))
	o = run('parted -s {drive} mkpart primary {start} {size}'.format(**args))
	
	first, second = grab_partitions(args['drive']).keys()
	o = run('mkfs.vfat -F32 {drive}{part1}'.format(**args, part1=first))

	# "--cipher sha512" breaks the shit.
	# TODO: --use-random instead of --use-urandom
	o = run('cryptsetup -q -v --type luks2 --pbkdf argon2i --hash sha512 --key-size 512 --iter-time 10000 --key-file {pwfile} --use-urandom luksFormat {drive}{part2}'.format(**args, part2=second))
	if not o.decode('UTF-8').strip() == 'Command successful.':
		print('[E] Failed to setup disk encryption.')
		exit(1)

	o = run('cryptsetup open {drive}{part2} luksdev --key-file {pwfile} --type luks2'.format(**args, part2=second))
	o = run('file /dev/mapper/luksdev') # /dev/dm-0
	if b'cannot open' in o:
		print('[E] Could not mount encrypted device.')
		exit(1)

	o = run('mkfs.btrfs /dev/mapper/luksdev')
	o = run('mount /dev/mapper/luksdev /mnt')

	os.makedirs('/mnt/boot')
	o = run('mount {drive}{part1} /mnt/boot'.format(**args, part1=first))
	o = run("wget 'https://www.archlinux.org/mirrorlist/?country={country}&protocol=https&ip_version=4&ip_version=6&use_mirror_status=on' -O /root/mirrorlist".format(**args))
	o = run("sed -i 's/#Server/Server/' /root/mirrorlist")
	o = run('rankmirrors -n 6 /root/mirrorlist > /etc/pacman.d/mirrorlist')

	o = run('pacman -Syy')
	o = run('pacstrap /mnt base base-devel btrfs-progs efibootmgr nano wpa_supplicant dialog {packages}'.format(**args))

	o = run('genfstab -pU /mnt >> /mnt/etc/fstab')
	with open('/mnt/etc/fstab', 'a') as fstab:
		fstab.write('\ntmpfs /tmp tmpfs defaults,noatime,mode=1777 0 0\n') # Redundant \n at the start? who knoes?

	o = run('arch-chroot /mnt rm /etc/localtime')
	o = run('arch-chroot /mnt ln -s /usr/share/zoneinfo/Europe/Stockholm /etc/localtime')
	o = run('arch-chroot /mnt hwclock --hctosys --localtime')
	o = run('arch-chroot /mnt {hostname}'.format(**args))
	o = run("arch-chroot /mnt sed -i 's/#\(en_US\.UTF-8\)/\1/' /etc/locale.gen")
	o = run('arch-chroot /mnt locale-gen')
	o = run('arch-chroot /mnt chmod 700 /root')
	o = run('arch-chroot /mnt usermod --password {} root'.format(PIN))
	if 'user' in args:
		o = run('arch-chroot /mnt useradd -m -G wheel {user}'.format(**args))
		o = run('arch-chroot /mnt usermod --password {pin} {user}'.format(**args, pin=PIN))

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
	#UUID = run('blkid -s PARTUUID -o value {drive}{part2}'.format(**args, part2=second)).decode('UTF-8').strip()
	UUID = run("ls -l /dev/disk/by-uuid/ | grep {basename}{part2} | awk '{print $9}'".format(basename=os.path.basename(args['drive']), part2=second)).decode('UTF-8').strip()
	with open('/mnt/boot/loader/entries/arch.conf', 'w') as entry:
		entry.write('title Arch Linux\n')
		entry.write('linux /vmlinuz-linux\n')
		entry.write('initrd /initramfs-linux.img\n')
		entry.write('options cryptdevice=UUID={UUID}:luksdev root=/dev/mapper/luksdev rw intel_pstate=no_hwp\n'.format(UUID=UUID))

	o = run('umount -R /mnt')
	
	print('Done. "reboot" when you\'re done tinkering.')
