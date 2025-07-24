from __future__ import annotations

import getpass
from pathlib import Path
from typing import ClassVar

from archinstall.lib.models.device import Fido2Device

from ..exceptions import SysCallError
from ..general import SysCommand, SysCommandWorker, clear_vt100_escape_codes_from_str
from ..models.users import Password
from ..output import error, info


class Fido2:
	_loaded_cryptsetup: bool = False
	_loaded_u2f: bool = False
	_cryptenroll_devices: ClassVar[list[Fido2Device]] = []
	_u2f_devices: ClassVar[list[Fido2Device]] = []

	@classmethod
	def get_fido2_devices(cls) -> list[Fido2Device]:
		"""
		fido2-tool output example:

		/dev/hidraw4: vendor=0x1050, product=0x0407 (Yubico YubiKey OTP+FIDO+CCID)
		"""

		if not cls._loaded_u2f:
			cls._loaded_u2f = True
			try:
				ret = SysCommand('fido2-token -L').decode()
			except Exception as e:
				error(f'failed to read fido2 devices: {e}')
				return []

			fido_devices = clear_vt100_escape_codes_from_str(ret)

			if not fido_devices:
				return []

			for line in fido_devices.splitlines():
				path, details = line.replace(',', '').split(':', maxsplit=1)
				_, product, manufacturer = details.strip().split(' ', maxsplit=2)

				cls._u2f_devices.append(Fido2Device(Path(path.strip()), manufacturer.strip(), product.strip().split('=')[1]))

		return cls._u2f_devices

	@classmethod
	def get_cryptenroll_devices(cls, reload: bool = False) -> list[Fido2Device]:
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
		if not cls._loaded_cryptsetup or reload:
			try:
				ret = SysCommand('systemd-cryptenroll --fido2-device=list').decode()
			except SysCallError:
				error('fido2 support is most likely not installed')
				raise ValueError('HSM devices can not be detected, is libfido2 installed?')

			fido_devices = clear_vt100_escape_codes_from_str(ret)

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
					Fido2Device(Path(path), manufacturer, product),
				)

			cls._loaded_cryptsetup = True
			cls._cryptenroll_devices = devices

		return cls._cryptenroll_devices

	@classmethod
	def fido2_enroll(
		cls,
		hsm_device: Fido2Device,
		dev_path: Path,
		password: Password,
	) -> None:
		worker = SysCommandWorker(f'systemd-cryptenroll --fido2-device={hsm_device.path} {dev_path}', peek_output=True)
		pw_inputted = False
		pin_inputted = False

		while worker.is_alive():
			if pw_inputted is False:
				if bytes(f'please enter current passphrase for disk {dev_path}', 'UTF-8') in worker._trace_log.lower():
					worker.write(bytes(password.plaintext, 'UTF-8'))
					pw_inputted = True
			elif pin_inputted is False:
				if bytes('please enter security token pin', 'UTF-8') in worker._trace_log.lower():
					worker.write(bytes(getpass.getpass(' '), 'UTF-8'))
					pin_inputted = True

				info('You might need to touch the FIDO2 device to unlock it if no prompt comes up after 3 seconds')
