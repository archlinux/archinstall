import os
from .general import sys_command
from .networking import list_interfaces, enrichIfaceTypes

def hasWifi():
	return 'WIRELESS' in enrichIfaceTypes(list_interfaces().values()).values()

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
	return any('nvidia' in x for x in graphicsDevices())

def hasAmdGraphics():
	return any('amd' in x for x in graphicsDevices())

def hasIntelGraphics():
	return any('intel' in x for x in graphicsDevices())

# TODO: Add more identifiers
