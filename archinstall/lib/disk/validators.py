def valid_parted_position(pos :str):
	if not len(pos):
		return False

	if pos.isdigit():
		return True

	if pos[-1] == '%' and pos[:-1].isdigit():
		return True

	if pos[-3:].lower() in ['mib', 'kib', 'b', 'tib'] and pos[:-3].replace(".", "", 1).isdigit():
		return True

	if pos[-2:].lower() in ['kb', 'mb', 'gb', 'tb'] and pos[:-2].replace(".", "", 1).isdigit():
		return True

	return False


def fs_types():
	# https://www.gnu.org/software/parted/manual/html_node/mkpart.html
	# Above link doesn't agree with `man parted` /mkpart documentation:
	"""
		fs-type can
		be  one  of  "btrfs",  "ext2",
		"ext3",    "ext4",    "fat16",
		"fat32",    "hfs",     "hfs+",
		"linux-swap",  "ntfs",  "reis‐
		erfs", "udf", or "xfs".
	"""
	return [
		"btrfs",
		"ext2",
		"ext3", "ext4",  # `man parted` allows these
		"fat16", "fat32",
		"hfs", "hfs+",  # "hfsx", not included in `man parted`
		"linux-swap",
		"ntfs",
		"reiserfs",
		"udf",  # "ufs", not included in `man parted`
		"xfs",  # `man parted` allows this
	]


def valid_fs_type(fstype :str) -> bool:
	return fstype.lower() in fs_types()
