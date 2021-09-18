def create_subvolume(partition):
	if partition['mountpoint'] == '/':
		partition['filesystem']['subvolume'] = '@'
	elif partition['mountpoint'] == '/home':
		partition['filesystem']['subvolume'] = '@home'

	# @.snapshots /.snapshots
	# @log /var/log
	# @pkg /var/cache/pacman/pkg