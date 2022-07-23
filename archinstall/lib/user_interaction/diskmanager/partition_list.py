
from ...menu.list_manager import ListManager
from ...output import log, FormattedOutput
from ...storage import storage
from ...hardware import has_uefi

from .dataclasses import DiskSlot, GapSlot, PartitionSlot, parent_from_list, StorageSlot
from .discovery import hw_discover
from .partition_menu import PartitionMenu
# from diskmanager.generator import generate_layout
from typing import List, Any, Dict, Optional, TYPE_CHECKING

from ...menu.menu import Menu, MenuSelectionType

if TYPE_CHECKING:
	_: Any


def slot_formatter(target: StorageSlot, filter: List[str] = None) -> Dict:
	""" returns a dict with the *Slot target attributes formatted as strings, with special formatting for some fields """
	result = {}
	base_results = target.as_dict(filter)
	for k in filter:
		value = base_results.get(k,None)
		if k == 'size':
			value = f"{target.sizeN:12}" if isinstance(target,DiskSlot) else f"{target.sizeN:>12}"
		elif k == 'crypt':
			value = target.encrypted if isinstance(target,PartitionSlot) else None
		elif k == 'path':
			prefix = '└─'
			if isinstance(target, GapSlot):
				value = prefix
			elif isinstance(target, PartitionSlot):
				if target.uuid:
					value = prefix + value.split('/')[-1]
				else:
					value = prefix + '(new)'
			else:
				pass
		elif k == 'start':
			value = int(value)
		elif k == 'fs' and isinstance(target,PartitionSlot):
			value = target.filesystem
		elif k == 'actual_mountpoint' and isinstance(target,PartitionSlot):
			value = target.actual_mount()
		elif k == 'in use' and isinstance(target,PartitionSlot):
			if target.actual_mount():
				value = True
			else:
				value = False
		elif k == 'mountpoint' and isinstance(target,PartitionSlot):
			value = target.proposed_mount()

		if not value:
			value = ''
		elif type(value) == bool:
			value = k

		result[k] = str(value)
	return result

def format_to_list_manager(data: List[StorageSlot], field_list: List[str] = None) -> List[str]:
	""" does the specific formatting of the storage list to be shown at ListManager derivatives
	"""
	if field_list is None:
		if storage['arguments'].get('dm_long_form'):
			filter = ['path','start','size','type','wipe','crypt','boot','fs','mountpoint', 'actual_mountpoint','uuid']
		else:
			filter = ['path','size','type','wipe','crypt','boot','fs','mountpoint', 'in use']
	else:
		filter = field_list
	table = FormattedOutput.as_table(data, slot_formatter, filter)
	rows = table.split('\n')
	# these are the header rows of the table and do not map to any User obviously
	# we're adding 2 spaces as prefix because the menu selector '> ' will be put before
	# the selectable rows so the header has to be aligned
	display_data = {f'  {rows[0]}': None, f'  {rows[1]}': None}

	for row, payload in zip(rows[2:], data):
		row = row.replace('|', '\\|')
		display_data[row] = payload

	return display_data


def create_gap_list(mapa: List[StorageSlot]) -> List[StorageSlot]:
	""" takes a list of slots and creates an equivalent list with (updated) gaps """
	new_mapa = []
	for disk in sorted([entry for entry in mapa if isinstance(entry,DiskSlot)]):
		new_mapa.append(disk)
		new_mapa += disk.device_map(mapa)
	return new_mapa


class DevList(ListManager):

	def __init__(
		self,
		prompt: str,
		entries: List[Any]
	):
		self._object_actions = [
			'Add disk to installation set',          # 0
			'Add partition',                         # 1
			'Clear disk (delete disk contents)',     # 2
			'Clear Partition & edit attributes',     # 3
			'Edit partition attributes',             # 4
			'Exclude disk from installation set',    # 5
			'Delete partition'                       # 6
		]
		entries = create_gap_list(entries)  # list will be substituted with one with gaps
		self._default_action = 'Reset'
		self.partitions_to_delete = []
		super().__init__(prompt, entries, [self._default_action], self._object_actions)

	def run(self) -> (List[StorageSlot], List[PartitionSlot]):
		""" overloaded to allow partitions_to_delete to be returned"""
		# looped to be able to check for errors
		while True:
			result_list = super().run()
			if self.last_choice.value != self._confirm_action:
				self.partitions_to_delete = []
				break
			elif self.last_choice.value == self._confirm_action:
				if self._check_coherence():
					break

		return result_list, self.partitions_to_delete

	def _get_selected_object(self,selection) -> StorageSlot:
		""" generic method to recover the object we want to work with in _handle_action """
		pos = self._data.index(selection)
		return self._data[pos]

	def _check_coherence(self):
		status = True
		forgettable = True
		msg_lines = [str(_("We have found following problems at your setup"))]
		# we always check for space no matter what happens
		disk_list = [item for item in self._data if isinstance(item,DiskSlot)]
		# a disk can have only a boot partition
		for disk in disk_list:
			boot_part = [item.boot for item in disk.partition_list(self._data) if item.boot]
			if len(boot_part) > 1:
				status = False
				forgettable = False
				msg_lines.append(str(_("- Disk {} has defined more than one boot partition").format(disk.device)))

			elif len(boot_part) == 1 and has_uefi():
				if disk.partition_list(self._data)[0].start < 2048 : # TODO 1 MB (sure ¿?)
					status = True
					msg_lines.append(str(_("- Fist partition on boot Disk {} has to start after the 1Mb boundary").format(disk.device)))
		# at least a / partition has to be created
		# partitions shouldn't overlap

		if not status:
			errors = '\n - '.join(msg_lines)
			if forgettable:
				status = self._generic_boolean_editor(str(_('Errors found: \n{} Do you want to proceed anyway?').format(errors)),False)
			else:
				log(errors,fg="red")
				print(_("press any key to return to the list"))
				input()
		return status

	def selected_action_display(self, selection: Any) -> str:
		""" implemented to get different headers depending on the class of the element.
		Could be also implemented as a dataclass property"""
		target = self._get_selected_object(selection)
		if isinstance(target,DiskSlot):
			return f'disk {target.device}'
		elif isinstance(target,GapSlot):
			return f'gap {target.device}@{target.start}'
		elif isinstance(target,PartitionSlot):
			if target.path:
				return f'partition {target.path}'
			else:
				return f'partition {target.device}@{target.start}'
		return selection

	def reformat(self, data: List[StorageSlot]) -> Dict[str, Any]:
		""" implemented. The exact formatting is left to an outside routine """
		return format_to_list_manager(data)

	def handle_action(self, action: Any, entry: Optional[Any], data: List[StorageSlot]) -> List[StorageSlot]:
		""" implemented. the meat is at _exec_action. We always recalculate gaps and return sorted"""
		my_data = create_gap_list(self._exec_action(action, entry, data))
		return my_data

	def filter_options(self, selection: Any, options: List[str]) -> List[str]:
		""" implemented. filter which actions to show for an specific class selection """
		target = self._get_selected_object(selection)
		disk_actions = (0,1,2,5)
		part_actions = (3,4,6)
		match target:
			case DiskSlot():
				return [options[i] for i in disk_actions]
			case GapSlot():
				return [options[1]]
			case PartitionSlot():
				return [options[i] for i in part_actions]
			case _:
				return options

	def _exec_action(self, action: str, target: StorageSlot, data: List[StorageSlot]) -> List[StorageSlot]:
		""" main driver to the implemented actions
		Could be more efficient if data wouldn't be copied back and forth, but such is the standard at ListManager now"""
		# reset
		if action == self._default_action:
			return self._action_reset(target, data)
		# Add disk to installation set',          # 0
		elif action == self._object_actions[0]:
			# load its info and partitions into the list
			return self._action_add_hd_set(target, data)
		# Add partition',                         # 1
		elif action == self._object_actions[1]:
			return self._action_add_partition(target, data)
		# Clear disk (delete disk contents)',     # 2
		elif action == self._object_actions[2]:
			return self._action_clear_disk(target, data)
		# Clear Partition & edit attributes',     # 3
		elif action == self._object_actions[3]:
			return self._action_clear_partition(target, data)
		# Edit partition attributes',             #4
		elif action == self._object_actions[4]:
			return self._action_edit_partition(target, data)
		# Exclude disk from installation set',    # 5
		elif action == self._object_actions[5]:
			return self._action_exclude_disk(target, data)
		# Delete partition'                       # 6
		elif action == self._object_actions[6]:
			return self._action_delete_partition(target, data)
		return data

	def _action_not_implemented(self, target: StorageSlot, data: List[StorageSlot]) -> List[StorageSlot]:
		log('Action still not implemented')
		return data

	def _action_reset(self, target: StorageSlot, data: List[StorageSlot]) -> List[StorageSlot]:
		""" return the original values without any change from editing"""
		self.partitions_to_delete = []
		return self._original_data

	def _action_add_partition(self, target: StorageSlot, data: List[StorageSlot]) -> List[StorageSlot]:
		""" adding a partition """
		disk = parent_from_list(target, data)
		if len(disk.partition_list(data)) == 0:
			is_empty_disk = True
		else:
			is_empty_disk = False
		if isinstance(target,GapSlot):
			part_data = PartitionSlot(target.device,target.startInput,target.sizeInput,wipe=True)
		else:
			part_data = PartitionSlot(target.device, -1, -1, wipe=True)  # Something has to be done with this

		# TODO document argument
		if not storage['arguments'].get('dm_no_add_menu',True):
			add_menu = PartitionMenu(part_data,self)
			add_menu.run()
		else:
			# TODO exit on quit at location
			with PartitionMenu(part_data,self) as add_menu:
				exit_menu = False
				for option in add_menu.list_options():
					if option in ('location','mountpoint','filesystem','subvolumes','boot','encrypted'):
						add_menu.synch(option)
						add_menu.exec_option(option)
						# broken execution here
						if option == 'location':
							selection = add_menu.option('location').get_selection()
							if selection is None:
								exit_menu = True
								break
							elif selection.startInput == -1 or selection.sizeInput == -1:
								exit_menu = False
								break
				if not exit_menu:
					add_menu.run()
				else:
					add_menu.exec_option(add_menu.cancel_action)

		if add_menu.last_choice == add_menu.cancel_action:
			return data
		if part_data:
			part_data.wipe = True
			data.append(part_data)
			if is_empty_disk:
				disk.wipe = True
		return data

	def _action_add_hd_set(self,target: StorageSlot, data: List[StorageSlot]) -> List[StorageSlot]:
		""" add a harddrive to the working set (list)"""
		# recheck the hardware is a bit slow, but avoids needing a global variable
		# TODO ENHANCEMENT check for cheaper alternatives, if any
		actual_hds = [item.device for item in data if isinstance(item,DiskSlot)]
		hw_list = hw_discover()
		missing_hds = [item.device for item in hw_list if isinstance(item,DiskSlot) and item.device not in actual_hds]
		if missing_hds:
			to_append = self._select_additional_harddrives(missing_hds)
			data += [item for item in hw_list if item.device in to_append]
			return sorted(data)
		else:
			return data

	def _action_clear_disk(self, target: StorageSlot, data: List[StorageSlot]) -> List[StorageSlot]:
		""" we set the disk to wipe and delete all children at data"""
		target.wipe = True
		# no need to delete partitions in this disk
		self._ripple_delete(target,data, head=False)
		return data

	def _action_clear_partition(self, target: StorageSlot, data: List[StorageSlot]) -> List[StorageSlot]:
		""" we set the wipe flag, and change the contents"""
		# we don't dare if the partition is in use
		if target.actual_mount():
			log(_("Can not clear and redefine partition {}, because it is in use").format(target.path))
			input()  # only way to let the message be seen
			return data
		my_menu = PartitionMenu(target,self)
		my_menu.run()
		if my_menu.last_choice != my_menu.cancel_action:
			target.wipe = True
		return data

	def _action_delete_partition(self, target: StorageSlot, data: List[StorageSlot]) -> List[StorageSlot]:
		""" mark partitions to be physically deleted and delete the from the list"""
		if target.actual_mount():
			log(_("Can not delete partition {}, because it is in use").format(target.path))
			input()  # only way to let the message be seen
			return data
		elif target.uuid:
			self.partitions_to_delete.append(target)
		key = data.index(target)
		del data[key]
		return data

	def _action_edit_partition(self, target: StorageSlot, data: List[StorageSlot]) -> List[StorageSlot]:
		PartitionMenu(target,self).run()
		return data

	def _action_exclude_disk(self, target: StorageSlot, data: List[StorageSlot]) -> List[StorageSlot]:
		""" we get rid of the disk from the list, but left the phiscial implementation untouched"""
		self._ripple_delete(target,data, head=True)
		return data

	def _ripple_delete(self, target: StorageSlot, data: List[StorageSlot], head: bool) -> List[StorageSlot]:
		""" we get rid of dependant elements of the list.
		if head argument is True we delete also the disk entry
		we need to clean up the partitions_to_delete list, to avoid repetition of actions, with unexpected behavior"""
		if not isinstance(target,DiskSlot):
			return data
		children = target.children(data)
		for child in children:
			idx = data.index(child)
			if isinstance(child,PartitionSlot) and child.uuid:
				try:
					idx_del = self.partitions_to_delete.index(child)
					del self.partitions_to_delete[idx_del]
				except ValueError:
					pass
			del data[idx]
		if head:
			idx = data.index(target)
			del data[idx]
		return data
		# placeholder

	def _select_additional_harddrives(self, missing: List[str] = []) -> List[str]:
		"""
		Asks the user to select one or multiple hard drives

		:return: List of selected hard drives
		:rtype: list
		"""
		options = {f'{option}': option for option in missing}

		title = str(_('Select one or more hard drives to add to the list and configure\n'))

		selected_harddrive = Menu(
			title,
			list(options.keys()),
			preset_values=[],
			multi=True
		).run()

		match selected_harddrive.type_:
			case MenuSelectionType.Ctrl_c:
				return []
			case MenuSelectionType.Esc:
				return []
			case MenuSelectionType.Selection:
				return [options[i] for i in selected_harddrive.value]
