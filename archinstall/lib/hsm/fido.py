import typing
from ..general import SysCommand, clear_vt100_escape_codes

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
	