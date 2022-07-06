import archinstall
from archinstall.diskmanager.dataclasses import DiskSlot, PartitionSlot


def generate_layout(storage_map):
	# """ This routine converts the abstract internal layout into a standard disk layout """
	def emount(partition):
		""" partition has mountpoint. Btrfs subvolumes are to be checked  """
		if partition.mountpoint:
			return True
		for subvolume in partition.btrfs:  # expect normalized contents
			if subvolume.mountpoint:
				return True
	# TODO if i reuse a btrfs volume. How I do it
	harddrives = []
	disk_layouts = {}
	disk_entries = [entry for entry in storage_map if isinstance(entry, DiskSlot)]
	for disk in disk_entries:
		# determine if the disk is to be extracted
		in_set = False
		if disk.wipe:
			in_set = True
		# we filter the partitions which are to be written (those to be wiped out or have a designated mountpoint
		disk_partitions = [entry for entry in storage_map if
								entry.device == disk.device and isinstance(entry, PartitionSlot)
								and (entry.wipe or emount(entry))]
		if len(disk_partitions) > 0:
			in_set = True
		if not in_set:
			continue  # disk information will not be used

		harddrives.append(archinstall.BlockDevice(disk.device))
		disk_dict = {disk.device: {"partitions": []}}
		part_list = disk_dict[disk.device]['partitions']
		for part in disk_partitions:
			part_list.append(part.to_layout())

		disk_layouts.update(disk_dict)
	return harddrives, disk_layouts
