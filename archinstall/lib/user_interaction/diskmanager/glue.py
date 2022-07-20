from typing import Any, Dict, TYPE_CHECKING, List
if TYPE_CHECKING:
	_: Any

from ..system_conf import select_harddrives
from ..partitioning_conf import get_default_partition_layout
from ...menu import Menu
from ...output import log

from .discovery import layout_to_map, hw_discover
from .generator import generate_layout
from .partition_list import DevList


def diskmanager(arguments :Dict[str, Any], storage:Dict[str, Any]):
	""" Main entry point to the disk manager routines

	parameters expected
	param: arguments:  archinstall.arguments
	param: storage  :  archinstall.storage (needed for the MountPoint at frontend)
	"""
	status = 'show'
	while status == 'show':
		status,list_layout = frontpage(arguments,storage)
		if not status:
			exit()
		if status == 'direct':  # no special diskmanager processing will be done (either unneeded or user loves previous version
			return

	dl = DevList('*** Disk Layout ***', list_layout)
	result, partitions_to_delete = dl.run()
	if not result or dl.last_choice.value != dl._confirm_action:
		exit()
	arguments['harddrives'],arguments['disk_layouts'] = generate_layout(result)
	# TODO partitions to delete handling
	handle_partitions_to_delete(arguments,partitions_to_delete)

# TODO for list or menu ... vfat handling as it is not supported
# TODO for menu  changed fs and wipe is not activated. and size allocation is a disaster
def handle_partitions_to_delete(arguments: Dict, partitions_to_delete: list):
	if partitions_to_delete:
		delete_msg = _("\n To use the selected configuration you need to delete via os system tools following partitions: \n")
		log(delete_msg)
		for partition in partitions_to_delete:
			log(_(" Path {}  - Device {} - Start sector {} Size {}").format(partition.path, partition.device, partition.start, partition.sizeN))
		exit_warning = (_("\n after you have completed all configuration, the program will stop. Then \n 1- Proceed to delete the partitions\n"
					   " 2 - reexecute the installation procedure with following parameters \n"
					   " \t\t --config /var/log/archinstall/user_configuration.json \ \n"
					   " \t\t --disk_layouts /var/log/archinstall/user_disk_layout.json \ \n"
					   " \t\t --creds /var/log/archinstall/user_credentials.json\n"
					   "\n this are the default config filenames\n"))
		log(exit_warning)
		input()
		arguments['dry_run'] = True

def frontpage(arguments: Dict[str, Any], storage: Dict[str, Any]) -> [str, List[Any]]:
	""" Menu with selection of which action the user wants to perform
	parameters expectedB
	param: arguments:  archinstall.arguments
	param: storage  :  archinstall.storage (needed for the MountPoint at frontend)
	returns:
	status (str). One of
		ok 		-processing ended correctly
		direct - processing ended correcty but result won't be processed by diskmanager
		show   - processing is incomplete, shall return to the module
		None value:  direct exit from processing
	layout_list a list of StorageSlots for further processing
	"""
	layout = {}
	if arguments.get('disk_layouts'):
		# TODO check if disks still exist
		layout = arguments.get('disk_layouts')
		return 'ok',layout_to_map(layout)
	else:
		prompt = _('*** Disk Management ***')
		options = [
			str(_("Use whatever is defined at {} as the instalation target".format(storage['MOUNT_POINT']))),
			str(_('Select full disk(s), delete its contents and use a suggested layout')),
			str(_('Select disk(s) and manually manage them')),
			str(_('View full disk structure')),
			str(_('Use old interface'))
		]
		result = Menu(prompt,options,skip=True,sort=False).run()
		if result.value:
			harddrives = []
			# go to old interface
			if result.value == options[4]:
				return 'direct',None  # old interface
			# use whatever exists at /mnt/archinstall
			if result.value == options[0]:
				# TODO should we check if the directory exists as a mountpoint ?
				arguments['harddrives'] = []
				if 'disk_layout' in arguments:
					del arguments['disk_layout']
				arguments['preset_mount'] = True
				return "direct",None  # no disk to handle

			# select one or more disks and apply a standard layout
			standard_layout = None
			if result.value in (options[1], options[2]):
				# TODO handle unintended gaps
				# TODO check with current structure ¿?
				# TODO in option 2 is there an option to get standard layout viable ¿? Is there need
				old_harddrives = arguments.get('harddrives', [])
				harddrives = select_harddrives(old_harddrives)
				if not harddrives:
					return 'show',None
				arguments['harddrives'] = harddrives
				# in case the harddrives got changed we have to reset the disk layout as well
				# TODO is that needed now ?
				if old_harddrives != harddrives:
					arguments['disk_layouts'] = {}
				if result.value == options[1]:
					# we will create an standard layout, but will left open, editing it
					standard_layout = layout_to_map(get_default_partition_layout(harddrives))
			elif result.value == options[3]:
				harddrives = []
			else:
				pass

			my_layout = hw_discover(harddrives)
			if standard_layout:
				# TODO merge structure and standard
				return 'ok',standard_layout
			else:
				return 'ok',my_layout
		else:
			return None,None
