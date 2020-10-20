import os

from .exceptions import *
from .general import *

def service_state(service_name: str):
	if os.path.splitext(service_name)[1] != '.service':
		service_name += '.service'  # Just to be safe

	state = b''.join(sys_command(f'systemctl show -p SubState --value {service_name}'))

	return state.strip().decode('UTF-8')
