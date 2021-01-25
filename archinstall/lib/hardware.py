import os
from .networking import list_interfaces, enrichIfaceTypes

def hasWifi():
	if 'WIRELESS' in enrichIfaceTypes(list_interfaces().values()).values():
		return True
	return False

def hasUEFI():
	return os.path.isdir('/sys/firmware/efi')