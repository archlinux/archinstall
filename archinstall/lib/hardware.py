import os, subprocess, json
from .general import sys_command
from .networking import list_interfaces, enrichIfaceTypes
from typing import Optional
def hasWifi()->bool:
	return 'WIRELESS' in enrichIfaceTypes(list_interfaces().values()).values()

def hasAMDCPU()->bool:
	if subprocess.check_output("lscpu | grep AMD", shell=True).strip().decode():
		return True
	return False

def hasUEFI()->bool:
	return os.path.isdir('/sys/firmware/efi')

def graphicsDevices()->dict:
	cards = {}
	for line in sys_command(f"lspci"):
		if b' VGA ' in line:
			_, identifier = line.split(b': ',1)
			cards[identifier.strip().lower().decode('UTF-8')] = line
	return cards

def hasNvidiaGraphics()->bool:
	return any('nvidia' in x for x in graphicsDevices())

def hasAmdGraphics()->bool:
	return any('amd' in x for x in graphicsDevices())

def hasIntelGraphics()->bool:
	return any('intel' in x for x in graphicsDevices())


def cpuVendor()-> Optional[str]:
	cpu_info = json.loads(subprocess.check_output("lscpu -J", shell=True).decode('utf-8'))['lscpu']
	for info in cpu_info:
		if info.get('field',None):
			if info.get('field',None) == "Vendor ID:":
				return info.get('data',None)
# TODO: Add more identifiers
