import os
from .general import SysCommand


def service_state(service_name: str):
	if os.path.splitext(service_name)[1] != '.service':
		service_name += '.service'  # Just to be safe

	state = b''.join(SysCommand(f'systemctl show --no-pager -p SubState --value {service_name}', environment_vars={'SYSTEMD_COLORS': '0'}))

	return state.strip().decode('UTF-8')
