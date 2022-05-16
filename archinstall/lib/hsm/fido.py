from ..general import SysCommand

def get_fido2_devices():
	worker = SysCommand(f"systemd-cryptenroll --fido2-device=list")
	print(worker)