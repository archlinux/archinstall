from .exceptions import *

def select_disk(dict_o_disks):
	drives = sorted(list(dict_o_disks.keys()))
	if len(drives) > 1:
		for index, drive in enumerate(drives):
			print(f"{index}: {drive} ({dict_o_disks[drive]['size'], dict_o_disks[drive].device, dict_o_disks[drive]['label']})")
		drive = input('Select one of the above disks (by number or full path): ')
		if drive.isdigit():
			drive = dict_o_disks[drives[int(drive)]]
		elif drive in dict_o_disks:
			drive = dict_o_disks[drive]
		else:
			raise DiskError(f'Selected drive does not exist: "{drive}"')
		return drive

	raise DiskError('select_disk() requires a non-empty dictionary of disks to select from.')