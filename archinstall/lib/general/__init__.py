from archinstall.lib.general.general_menu import (
	select_archinstall_language,
	select_hostname,
	select_ntp,
	select_timezone,
)
from archinstall.lib.general.system_menu import select_driver, select_kernel, select_swap

__all__ = [
	'select_archinstall_language',
	'select_driver',
	'select_hostname',
	'select_kernel',
	'select_ntp',
	'select_swap',
	'select_timezone',
]
