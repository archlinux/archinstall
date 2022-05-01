import pytest
import subprocess
import string
import random
import pathlib
import json
import time
import sys

def simple_exec(cmd):
	proc = subprocess.Popen(
		cmd,
		shell=True,
		stdout=subprocess.PIPE,
		stderr=subprocess.STDOUT
	)

	output = b''
	while proc.poll() is None:
		line = proc.stdout.read(1024)
		print(line.decode(), end='')
		sys.stdout.flush()
		output += line
		time.sleep(0.01)

	output += proc.stdout.read()
	proc.stdout.close()

	return {'exit_code' : proc.poll(), 'data' : output.decode().strip()}

def random_filename():
	return ''.join([random.choice(string.ascii_letters) for x in range(20)]) + '.img'

def truncate_file(filename):
	result = simple_exec(f"truncate -s 20G {filename}")

	if not result['exit_code'] == 0:
		raise AssertionError(f"Could not generate a testimage with truncate: {result['data']}")

	return filename

def get_loopdev(filename):
	result = simple_exec(f"""losetup -a | grep "{filename}" | awk -F ":" '{{print $1}}'""")
	return result['data']

def detach_loopdev(path):
	result = simple_exec(f"losetup -d {path}")
	return result['exit_code'] == 0

def create_loopdev(path):
	result = simple_exec(f"losetup -fP {path}")
	return result['exit_code'] == 0

def test_stat_blockdev():
	import archinstall

	filename = pathlib.Path(random_filename()).resolve()
	if loopdev := get_loopdev(filename):
		if not detach_loopdev(loopdev):
			raise AssertionError(f"Could not detach {loopdev} before performing test with {filename}.")

	truncate_file(filename)
	if not create_loopdev(filename):
		raise AssertionError(f"Could not create a loopdev for {filename}")

	if loopdev := get_loopdev(filename):
		user_configuration = {
			"audio": "pipewire",
			"config_version": "2.4.2",
			"debug": True,
			"harddrives": [
				loopdev
			],
			"mirror-region": {
				"Sweden": {
					"http://ftp.acc.umu.se/mirror/archlinux/$repo/os/$arch": True,
					"http://ftp.lysator.liu.se/pub/archlinux/$repo/os/$arch": True,
					"http://ftp.myrveln.se/pub/linux/archlinux/$repo/os/$arch": True,
					"http://ftpmirror.infania.net/mirror/archlinux/$repo/os/$arch": True,
					"https://ftp.acc.umu.se/mirror/archlinux/$repo/os/$arch": True,
					"https://ftp.ludd.ltu.se/mirrors/archlinux/$repo/os/$arch": True,
					"https://ftp.lysator.liu.se/pub/archlinux/$repo/os/$arch": True,
					"https://ftp.myrveln.se/pub/linux/archlinux/$repo/os/$arch": True,
					"https://mirror.osbeck.com/archlinux/$repo/os/$arch": True
				}
			},
			"mount_point": None,
			"nic": {
				"dhcp": True,
				"dns": None,
				"gateway": None,
				"iface": None,
				"ip": None,
				"type": "iso"
			},
			"packages": [
				"nano"
			],
			"plugin": None,
			"profile": {
				"path": "/usr/lib/python3.10/site-packages/archinstall/profiles/minimal.py"
			},
			"script": "guided",
			"silent": True,
			"timezone": "Europe/Stockholm",
			"version": "2.4.2"
		}

		user_credentials = {
			"!encryption-password": "test",
			"!superusers": {
				"anton": {
					"!password": "test"
				}
			},
			"!users": {}
		}

		user_disk_layout = {
			loopdev: {
				"partitions": [
					{
						"boot": True,
						"encrypted": False,
						"filesystem": {
							"format": "fat32"
						},
						"mountpoint": "/boot",
						"size": "512MiB",
						"start": "1MiB",
						"type": "primary",
						"wipe": True
					},
					{
						"btrfs": {
							"subvolumes": {
								"@": "/",
								"@.snapshots": "/.snapshots",
								"@home": "/home",
								"@log": "/var/log",
								"@pkg": "/var/cache/pacman/pkg"
							}
						},
						"encrypted": False,
						"filesystem": {
							"format": "btrfs",
							"mount_options": [
								"compress=zstd"
							]
						},
						"mountpoint": None,
						"size": "100%",
						"start": "513MiB",
						"type": "primary",
						"wipe": True
					}
				],
				"wipe": True
			}
		}

		result = archinstall.SysCommand(f'archinstall --silent --config \'{json.dumps(user_configuration)}\' --creds \'{json.dumps(user_credentials)}\' --disk-layout \'{json.dumps(user_disk_layout)}\'', peak_output=True)
		#print(result)

		# Test ended, cleanup commences
		if not detach_loopdev(loopdev):
			raise AssertionError(f"Could not detach {loopdev} after performing tests on {filename}.")
	else:
		raise AssertionError(f"Could not retrieve a loopdev for testing on {filename}")

	pathlib.Path(filename).resolve().unlink()

test_stat_blockdev()