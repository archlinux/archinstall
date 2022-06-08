import typing
import pathlib
import getpass
import logging
from ..general import SysCommand, SysCommandWorker, clear_vt100_escape_codes
from ..disk.partition import Partition
from ..general import log

def get_fido2_devices() -> typing.Dict[str, typing.Dict[str, str]]:
	"""
	Uses systemd-cryptenroll to list the FIDO2 devices
	connected that supports FIDO2.
	Some devices might show up in udevadm as FIDO2 compliant
	when they are in fact not.

	The drawback of systemd-cryptenroll is that it uses human readable format.
	That means we get this weird table like structure that is of no use.

	So we'll look for `MANUFACTURER` and `PRODUCT`, we take their index
	and we split each line based on those positions.
	"""
	worker = clear_vt100_escape_codes(SysCommand(f"systemd-cryptenroll --fido2-device=list").decode('UTF-8'))

	MANUFACTURER_POS = 0
	PRODUCT_POS = 0
	devices = {}
	for line in worker.split('\r\n'):
		if '/dev' not in line:
			MANUFACTURER_POS = line.find('MANUFACTURER')
			PRODUCT_POS = line.find('PRODUCT')
			continue

		path = line[:MANUFACTURER_POS].rstrip()
		manufacturer = line[MANUFACTURER_POS:PRODUCT_POS].rstrip()
		product = line[PRODUCT_POS:]

		devices[path] = {
			'manufacturer' : manufacturer,
			'product' : product
		}

	return devices

def fido2_enroll(hsm_device_path :pathlib.Path, partition :Partition, password :str) -> bool:
	worker = SysCommandWorker(f"systemd-cryptenroll --fido2-device={hsm_device_path} {partition.real_device}", peak_output=True)
	pw_inputted = False
	pin_inputted = False
	while worker.is_alive():
		if pw_inputted is False and bytes(f"please enter current passphrase for disk {partition.real_device}", 'UTF-8') in worker._trace_log.lower():
			worker.write(bytes(password, 'UTF-8'))
			pw_inputted = True

		elif pin_inputted is False and bytes(f"please enter security token pin", 'UTF-8') in worker._trace_log.lower():
			worker.write(bytes(getpass.getpass(" "), 'UTF-8'))
			pin_inputted = True

			log(f"You might need to touch the FIDO2 device to unlock it if no prompt comes up after 3 seconds.", level=logging.INFO, fg="yellow")