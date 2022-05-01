import pytest
import subprocess
import string
import random
import pathlib

def simple_exec(cmd):
	proc = subprocess.Popen(
		cmd,
		shell=True,
		stdout=subprocess.PIPE,
		stderr=subprocess.STDOUT
	)

	while proc.poll() is None:
		pass

	result = proc.stdout.read()
	proc.stdout.close()

	return {'exit_code' : proc.poll(), 'data' : result.decode().strip()}

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
		# Actual test starts here:
		block_device = archinstall.BlockDevice(loopdev)

		# Make sure the backfile reported by BlockDevice() is the same we mounted
		if block_device.device_or_backfile != str(filename):
			raise AssertionError(f"archinstall.BlockDevice().device_or_backfile differs from loopdev path: {block_device.device_or_backfile} vs {filename}")

		# Make sure the device path equals to the device we setup (/dev/loop0)
		if block_device.device != loopdev:
			raise AssertionError(f"archinstall.BlockDevice().device difers from {loopdev}")

		# Check that the BlockDevice is clear of partitions
		if block_device.partitions:
			raise AssertionError(f"BlockDevice().partitions reported partitions, despire being a new trunkfile")

		if block_device.has_partitions():
			raise AssertionError(f"BlockDevice().has_partitions() reported partitions, despire being a new trunkfile")

		# Check that BlockDevice().size returns a float of the size in GB
		if block_device.size != 20.0:
			raise AssertionError(f"The size reported by BlockDevice().size is not 20.0 as expected")

		if block_device.bus_type != None:
			raise AssertionError(f"The .bus_type of the loopdev is something other than the expected None: {block_device.bus_type}")

		if block_device.spinning != False:
			raise AssertionError(f"The expected BlockDevice().spinnig was False, but got True")

		# if list(block_device.free_space) != [[0, 20, 20]]:
		# 	raise AssertionError(f"The reported free space of the loopdev was not [0, 20, 20]")

		# print(block_device.largest_free_space)
		if block_device.first_free_sector != '512MB':
			raise AssertionError(f"First free sector of BlockDevice() was not 512MB")

		if block_device.first_end_sector != '20.0GB':
			raise AssertionError(f"Last sector of BlockDevice() was not 20.0GB")

		if not block_device.partprobe():
			raise AssertionError(f"Could not partprobe BlockDevice() of loopdev")

		if block_device.has_mount_point('/'):
			raise AssertionError(f"BlockDevice() reported a mountpoint despite never being mounted")

		try:
			if block_device.get_partition('FAKE-UUID-TEST'):
				raise AssertionError(f"BlockDevice() reported a partition despite never having any")
		except archinstall.DiskError:
			pass # We're supposed to not find any

		# Test ended, cleanup commences
		if not detach_loopdev(loopdev):
			raise AssertionError(f"Could not detach {loopdev} after performing tests on {filename}.")
	else:
		raise AssertionError(f"Could not retrieve a loopdev for testing on {filename}")

	pathlib.Path(filename).resolve().unlink()