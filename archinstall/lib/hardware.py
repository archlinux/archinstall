import os
from .general import sys_command
from .networking import list_interfaces, enrichIfaceTypes

def hasWifi():
	if 'WIRELESS' in enrichIfaceTypes(list_interfaces().values()).values():
		return True
	return False

def hasUEFI():
	return os.path.isdir('/sys/firmware/efi')

def graphicsDevices():
	cards = {}
	for line in sys_command(f"lspci"):
		if b' VGA ' in line:
			_, identifier = line.split(b': ',1)
			cards[identifier.strip().lower().decode('UTF-8')] = line
	return cards

def hasNvidiaGraphics():
	if [x for x in graphicsDevices() if 'nvidia' in x]:
		return True
	return False

def hasAmdGraphics():
	if [x for x in graphicsDevices() if 'amd' in x]:
		return True
	return False

def hasIntelGraphics():
	if [x for x in graphicsDevices() if 'intel' in x]:
		return True
	return False

# TODO: Add more identifiers