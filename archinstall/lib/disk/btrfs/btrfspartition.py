from ..partition import Partition
from ...storage import storage

class BTRFSPartition(Partition):
	def __init__(self, *args, **kwargs):
		Partition.__init__(*args, **kwargs)

	@property
	def subvolumes(self):
		pass

	def create_subvolume(self, subvolume :str, installation :Optional[Installer] = None):
		"""
		Subvolumes have to be created within a mountpoint.
		This means we need to get the current installation target.
		After we get it, we need to verify it is a btrfs subvolume filesystem.
		Finally, the destination must be empty.
		"""

		# Allow users to override the installation session
		if not installation:
			installation = storage['installation_session']

		



		installation_mountpoint = installation.target
		if type(installation_mountpoint) == str:
			installation_mountpoint = pathlib.Path(installation_mountpoint)
		# Set up the required physical structure
		if type(subvolume_location) == str:
			subvolume_location = pathlib.Path(subvolume_location)

		target = installation_mountpoint / subvolume_location.relative_to(subvolume_location.anchor)

		# Difference from mount_subvolume:
		#  We only check if the parent exists, since we'll run in to "target path already exists" otherwise
		if not target.parent.exists():
			target.parent.mkdir(parents=True)

		if glob.glob(str(target / '*')):
			raise DiskError(f"Cannot create subvolume at {target} because it contains data (non-empty folder target)")

		# Remove the target if it exists
		if target.exists():
			target.rmdir()

		log(f"Creating a subvolume on {target}", level=logging.INFO)
		if (cmd := SysCommand(f"btrfs subvolume create {target}")).exit_code != 0:
			raise DiskError(f"Could not create a subvolume at {target}: {cmd}")