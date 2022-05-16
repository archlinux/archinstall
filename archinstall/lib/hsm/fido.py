from ..general import SysCommand, clear_vt100_escape_codes

def get_fido2_devices():
	worker = clear_vt100_escape_codes(SysCommand(f"systemd-cryptenroll --fido2-device=list").decode('UTF-8'))
	for line in worker.split('\r\n'):
		if '/dev' not in line:
			print(line)
			continue

		print(line)
	