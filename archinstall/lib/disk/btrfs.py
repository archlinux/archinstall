from ..general import SysCommand

def create_subvolume(installation):
	SysCommand(f"btrfs subvolume create {installation.target}/@")