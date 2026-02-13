from archinstall.lib.interactions.disk_conf import (
	get_default_partition_layout,
	select_devices,
	select_disk_config,
	select_main_filesystem_format,
	suggest_multi_disk_layout,
	suggest_single_disk_layout,
)
from archinstall.lib.interactions.general_conf import (
	add_number_of_parallel_downloads,
	select_archinstall_language,
	select_hostname,
	select_ntp,
	select_timezone,
)
from archinstall.lib.interactions.system_conf import select_driver, select_kernel, select_swap

__all__ = [
	'add_number_of_parallel_downloads',
	'get_default_partition_layout',
	'select_archinstall_language',
	'select_devices',
	'select_disk_config',
	'select_driver',
	'select_hostname',
	'select_kernel',
	'select_main_filesystem_format',
	'select_ntp',
	'select_swap',
	'select_timezone',
	'suggest_multi_disk_layout',
	'suggest_single_disk_layout',
]
