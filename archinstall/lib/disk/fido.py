from __future__ import annotations

import getpass
from pathlib import Path
from typing import List

from .device_model import PartitionModification, Fido2Device
from ..general import SysCommand, SysCommandWorker, clear_vt100_escape_codes
from ..output import error, info
from ..exceptions import SysCallError


class Fido2:
	_loaded: bool = False
	_fido2_devices: List[Fido2Device] = []

	@classmethod
	def get_fido2_devices(cls, reload: bool = False) -> List[Fido2Device]:
		"""
		Uses systemd-cryptenroll to list the FIDO2 devices
		connected that supports FIDO2.
		Some devices might show up in udevadm as FIDO2 compliant
		when they are in fact not.

		The drawback of systemd-cryptenroll is that it uses human readable format.
		That means we get this weird table like structure that is of no use.

		So we'll look for `MANUFACTURER` and `PRODUCT`, we take their index
		and we split each line based on those positions.

		Output example:

		PATH         MANUFACTURER PRODUCT
		/dev/hidraw1 Yubico       YubiKey OTP+FIDO+CCID
		"""

		# to prevent continuous reloading which will slow
		# down moving the cursor in the menu
		if not cls._loaded or reload:
			try:
				ret = SysCommand("systemd-cryptenroll --fido2-device=list").decode()
			except SysCallError:
				error('fido2 support is most likely not installed')
				raise ValueError('HSM devices can not be detected, is libfido2 installed?')

			fido_devices: str = clear_vt100_escape_codes(ret)  # type: ignore

			manufacturer_pos = 0
			product_pos = 0
			devices = []

			for line in fido_devices.split('\r\n'):
				if '/dev' not in line:
					manufacturer_pos = line.find('MANUFACTURER')
					product_pos = line.find('PRODUCT')
					continue

				path = line[:manufacturer_pos].rstrip()
				manufacturer = line[manufacturer_pos:product_pos].rstrip()
				product = line[product_pos:]

				devices.append(
					Fido2Device(Path(path), manufacturer, product)
				)

			cls._loaded = True
			cls._fido2_devices = devices

		return cls._fido2_devices

	@classmethod
	def fido2_enroll(
		cls,
		hsm_device: Fido2Device,
		part_mod: PartitionModification,
		password: str
	):
		worker = SysCommandWorker(f"systemd-cryptenroll --fido2-device={hsm_device.path} {part_mod.dev_path}", peek_output=True)
		pw_inputted = False
		pin_inputted = False

		while worker.is_alive():
			if pw_inputted is False:
				if bytes(f"please enter current passphrase for disk {part_mod.dev_path}", 'UTF-8') in worker._trace_log.lower():
					worker.write(bytes(password, 'UTF-8'))
					pw_inputted = True
			elif pin_inputted is False:
				if bytes(f"please enter security token pin", 'UTF-8') in worker._trace_log.lower():
					worker.write(bytes(getpass.getpass(" "), 'UTF-8'))
					pin_inputted = True

				info('You might need to touch the FIDO2 device to unlock it if no prompt comes up after 3 seconds')
